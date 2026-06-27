"""The agentic matcher loop. The agent PROPOSES; humans DISPOSE.

A continuous matcher re-runs the cascade on each new record, ranks candidates,
and produces a plain-language explanation GROUNDED in the actual Fellegi-Sunter
match weights — never a hallucinated reason. Only pairs above the high threshold
are pushed to the human verification queue. The agent cannot confirm a handover.

Two modes:
  * `explain_candidate` builds the explanation deterministically from the weight
    terms (always available, no API needed — this is the honest default and what
    tests assert against).
  * `narrate_candidate` optionally asks Claude to phrase that SAME grounded
    evidence in the family's language for a kiosk/IVR readout. It is given ONLY
    the real weight terms and is instructed not to invent facts. If no
    ANTHROPIC_API_KEY is set it falls back to the deterministic text.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .matching import cascade
from .matching.cascade import Candidate
from .schema import NOTE_MATCH, PersonRecord, make_note

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


@dataclass
class HumanQueueItem:
    query_id: str
    candidate_id: str
    total_weight: float
    probability: float
    explanation: list[str]
    matched_without_name: bool


@dataclass
class MatchRun:
    query_id: str
    candidates: list[Candidate]
    queued: list[HumanQueueItem] = field(default_factory=list)


def explain_candidate(query: PersonRecord, cand: Candidate) -> str:
    """Deterministic, weight-grounded explanation. No hallucination possible —
    every line traces to a WeightTerm produced by the scorer."""
    head = (f"Candidate {cand.record.person_record_id} — "
            f"{cand.total_weight:.1f} bits of evidence "
            f"(~{cand.probability*100:.0f}% match probability), "
            f"disposition: {cand.disposition.upper()}.")
    body = "\n".join(f"  • {line}" for line in cand.explanation)
    return f"{head}\n{body}"


def narrate_candidate(query: PersonRecord, cand: Candidate, *,
                      language: str = "english") -> str:
    """Optionally use Claude to phrase the SAME grounded evidence naturally.
    Falls back to the deterministic explanation with no API key."""
    grounded = explain_candidate(query, cand)
    if not ANTHROPIC_API_KEY:
        return grounded + "\n[narration: deterministic fallback — no ANTHROPIC_API_KEY]"
    try:  # pragma: no cover - needs a live key
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "You are SETU's reunification assistant. Below is the EXACT, "
            "machine-computed evidence for a possible match. Rephrase it in "
            f"simple {language} for a control-room operator. Do NOT add, infer, "
            "or invent any fact not present below. Do not state the match is "
            "confirmed — a human must verify.\n\n" + grounded
        )
        msg = client.messages.create(
            model="claude-opus-4-8", max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:  # fall back rather than fail the demo
        return grounded + f"\n[narration fallback: {e}]"


def run_match(store, query: PersonRecord, *, use_face: bool = True) -> MatchRun:
    """Re-run the cascade for `query` against the store's current pool, record a
    match note for every queued candidate, and build the human queue."""
    pool = store.all_persons()
    cands = cascade.search_candidates(query, pool, use_face=use_face)
    run = MatchRun(query_id=query.person_record_id, candidates=cands)

    for c in cascade.queue_candidates(cands):
        item = HumanQueueItem(
            query_id=query.person_record_id,
            candidate_id=c.record.person_record_id,
            total_weight=c.total_weight,
            probability=c.probability,
            explanation=c.explanation,
            matched_without_name=not c.score_obj.name_present,
        )
        run.queued.append(item)
        # Append-only match note grounded in the real weights.
        store.add_note(make_note(
            query.person_record_id, NOTE_MATCH, store.domain, author="agent-matcher",
            text=f"Proposed match {c.record.person_record_id} "
                 f"({c.total_weight:.1f} bits) — awaiting human verification.",
            linked_person_record_id=c.record.person_record_id,
            payload={"total_weight": c.total_weight, "probability": c.probability,
                     "explanation": c.explanation,
                     "matched_without_name": not c.score_obj.name_present},
        ))
    return run


def rematch_warm(store, *, use_face: bool = True) -> list[MatchRun]:
    """Re-run matching for all 'warm' records — the continuous loop's heartbeat.
    Called whenever a new record arrives so warm records get a fresh chance."""
    from .schema import STATUS_WARM

    runs = []
    for rec in store.all_persons(status=STATUS_WARM):
        run = run_match(store, rec, use_face=use_face)
        if run.queued:
            runs.append(run)
    return runs
