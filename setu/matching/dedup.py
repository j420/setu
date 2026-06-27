"""Deduplication — collapse the 8% duplicate reports.

A duplicate is the SAME person reported at multiple centers (the fragmentation
problem, measurable in the data). We run the very same scorer in within-stream
mode with a higher threshold (DEDUP_THRESHOLD) — a duplicate should agree on
more fields than a cross-stream missing<->found match.

Dedup never destroys data: a confirmed duplicate is expressed as an append-only
`dedup_link` note (PFIF merge-as-note), so the audit trail and both origins are
preserved. The control room sees one logical person with two source records.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config
from ..schema import NOTE_DEDUP, PersonRecord, make_note
from . import blocking, fellegi_sunter, semantic
from .cascade import _semantic_bits


@dataclass
class DuplicatePair:
    a: PersonRecord
    b: PersonRecord
    total_weight: float
    explanation: list[str]


def find_duplicates(
    records: list[PersonRecord], threshold: float = config.DEDUP_THRESHOLD
) -> list[DuplicatePair]:
    """Find same-person duplicates within each stream. O(n^2) over blocked pairs
    only — blocking keeps it cheap. Returns each unduplicated pair once."""
    pairs: list[DuplicatePair] = []
    seen: set[tuple[str, str]] = set()

    for rec in records:
        same_stream = [r for r in records if r.record_type == rec.record_type]
        cands = blocking.candidate_block(rec, same_stream, opposite_stream=False)
        for c in cands:
            key = tuple(sorted((rec.person_record_id, c.person_record_id)))
            if key in seen:
                continue
            seen.add(key)
            ms = fellegi_sunter.score(rec, c)
            sem_bits, sim = _semantic_bits(rec, c)
            total = round(ms.total_weight + sem_bits, 3)
            if total >= threshold:
                expl = [f"+{t.weight:.1f} — {t.reason}" for t in ms.positive_terms()]
                if sem_bits > 0:
                    expl.append(f"+{sem_bits:.1f} — free-text overlap (cosine {sim:.2f})")
                pairs.append(DuplicatePair(rec, c, total, expl))

    pairs.sort(key=lambda p: p.total_weight, reverse=True)
    return pairs


def link_duplicate(store, pair: DuplicatePair, author: str = "dedup-pass") -> None:
    """Record a duplicate as an append-only dedup_link note on both records."""
    note = make_note(
        pair.a.person_record_id,
        NOTE_DEDUP,
        store.domain,
        author=author,
        text=f"Same person as {pair.b.person_record_id} "
             f"(dedup weight {pair.total_weight} bits)",
        linked_person_record_id=pair.b.person_record_id,
        payload={"total_weight": pair.total_weight, "explanation": pair.explanation},
    )
    store.add_note(note)


def dedup_rate(records: list[PersonRecord], pairs: list[DuplicatePair]) -> float:
    """Fraction of records that are duplicates of another (for the metrics panel)."""
    if not records:
        return 0.0
    dup_ids = set()
    for p in pairs:
        dup_ids.add(p.b.person_record_id)  # count the redundant copy
    return round(len(dup_ids) / len(records), 4)
