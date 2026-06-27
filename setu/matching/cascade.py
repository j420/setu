"""The matching cascade — the brain. Mandatory ordering, two thresholds.

    1. BLOCK on reliable fields only (never name)            -> blocking.py
    2. SCORE with Fellegi-Sunter, explainable weights         -> fellegi_sunter.py
    3. NAME signal only if present (transliterate + phonetic)  -> folded into (2)
    4. FREE-TEXT semantic match (embeddings / cosine)          -> semantic.py
    5. FACE re-rank LAST, optional, consented, gated, low      -> face.py
    6. Two thresholds: high -> human queue; low -> discard;
       between -> keep "warm" and auto-re-match on new records.

The cascade PROPOSES ranked, fully-explained candidates. It NEVER confirms a
handover — that is a human-gated step in privacy.py / the MCP tool surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import config
from ..schema import PersonRecord
from . import blocking, face, fellegi_sunter, semantic

# Semantic similarity contributes at most this many bits — a modest nudge.
SEMANTIC_MAX_WEIGHT = 2.0

DISPOSITION_QUEUE = "queue"      # >= HIGH: push to human verification
DISPOSITION_WARM = "warm"        # between: keep warm, re-match later
DISPOSITION_DISCARD = "discard"  # < LOW: discard


@dataclass
class Candidate:
    record: PersonRecord
    base_weight: float                 # reliable fields + name (Fellegi-Sunter)
    semantic_weight: float
    face_weight: float
    total_weight: float
    probability: float
    disposition: str
    explanation: list[str] = field(default_factory=list)
    score_obj: object = None           # the underlying MatchScore (for the agent)
    semantic_similarity: float = 0.0
    face_info: dict = field(default_factory=dict)


def _disposition(total: float) -> str:
    if total >= config.THRESHOLD_HIGH:
        return DISPOSITION_QUEUE
    if total < config.THRESHOLD_LOW:
        return DISPOSITION_DISCARD
    return DISPOSITION_WARM


def _semantic_bits(query: PersonRecord, cand: PersonRecord) -> tuple[float, float]:
    """Free-text semantic contribution, capped. Uses intentional free_text only;
    physical_description stays quarantined."""
    sim = semantic.semantic_similarity(query.free_text, cand.free_text)
    # Only positive similarity adds evidence; cap it low.
    bits = round(max(0.0, sim) * SEMANTIC_MAX_WEIGHT, 3)
    return bits, sim


def score_pair(query: PersonRecord, cand: PersonRecord, *, use_face: bool = True) -> Candidate:
    """Run steps 2-5 on a single already-blocked pair and build the explanation."""
    ms = fellegi_sunter.score(query, cand)
    sem_bits, sim = _semantic_bits(query, cand)

    face_info = {"applicable": False, "weight": 0.0, "reason": "face not run"}
    if use_face:
        face_info = face.face_rerank(query, cand)
    face_bits = face_info.get("weight", 0.0)

    total = round(ms.total_weight + sem_bits + face_bits, 3)
    prob = fellegi_sunter._logistic(total)

    # Build a plain-language, weight-grounded explanation (no hallucinated reasons).
    expl: list[str] = []
    for t in ms.positive_terms():
        expl.append(f"+{t.weight:.1f} bits — {t.reason}")
    if sem_bits > 0:
        expl.append(f"+{sem_bits:.1f} bits — free-text context overlaps (cosine {sim:.2f})")
    if face_info.get("applicable"):
        expl.append(f"+{face_bits:.1f} bits — {face_info['reason']}")
    elif use_face:
        expl.append(f"(face: {face_info['reason']})")
    for t in ms.negative_terms():
        expl.append(f"{t.weight:.1f} bits — {t.reason}")
    if not ms.name_present:
        expl.append("note: matched WITHOUT a name on at least one record "
                    "(name-optional — reliable fields carried this match)")

    return Candidate(
        record=cand,
        base_weight=ms.total_weight,
        semantic_weight=sem_bits,
        face_weight=face_bits,
        total_weight=total,
        probability=round(prob, 4),
        disposition=_disposition(total),
        explanation=expl,
        score_obj=ms,
        semantic_similarity=sim,
        face_info=face_info,
    )


def search_candidates(
    query: PersonRecord,
    pool: list[PersonRecord],
    *,
    opposite_stream: bool = True,
    use_face: bool = True,
    limit: int = 10,
    window_hours: float = blocking.DEFAULT_TIME_WINDOW_HOURS,
) -> list[Candidate]:
    """Full cascade for one query record against a pool.

    Returns a ranked shortlist (highest total weight first), each with a
    weight-grounded explanation and a disposition. Records below THRESHOLD_LOW
    are dropped entirely."""
    blocked = blocking.candidate_block(
        query, pool, opposite_stream=opposite_stream, window_hours=window_hours
    )
    scored = [score_pair(query, c, use_face=use_face) for c in blocked]
    kept = [c for c in scored if c.disposition != DISPOSITION_DISCARD]
    kept.sort(key=lambda c: c.total_weight, reverse=True)
    return kept[:limit]


def queue_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Subset that crossed the high threshold — eligible for the human queue."""
    return [c for c in candidates if c.disposition == DISPOSITION_QUEUE]
