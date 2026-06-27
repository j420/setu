"""Face re-rank — LAST, OPTIONAL, CONSENTED, gated. (Step 5 of the cascade.)

INVIOLABLE RULE 2: SETU never builds a standing biometric database. So this
module:
  * is NEVER a candidate generator — it only re-ranks an already-blocked,
    already-textually-scored shortlist (1-to-few, not 1-to-many);
  * never scans CCTV and never enrols faces en masse;
  * computes embeddings ONLY from consented photos already in our store, holds
    them transiently in memory for the comparison, and DISCARDS them — nothing
    is persisted as a searchable index;
  * is weighted low and is never sufficient alone to confirm anything.

If either record has no consented photo, face is skipped and the system still
matches on everything else (face is a bonus, never a dependency).

Production: ArcFace / InsightFace embeddings compared by cosine. The CONTRACT is
`embedding(photo) -> vector`, similarity = cosine. Here it is a labelled MOCK
(deterministic hash of the photo ref) so the gating logic is fully exercised
without shipping a face model or any real biometric data.
"""

from __future__ import annotations

import hashlib

from .. import config
from ..schema import PersonRecord


def _transient_embedding(photo_ref: str) -> list[float]:
    """MOCK ArcFace embedding. Computed on demand, returned, never stored.
    Real swap: InsightFace `model.get(img).embedding`."""
    h = hashlib.sha256(photo_ref.encode("utf-8")).digest()
    return [b / 255.0 for b in h[:64]]


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def face_rerank(a: PersonRecord, b: PersonRecord) -> dict:
    """Return a gated face contribution for the pair.

    Result: {applicable, similarity, weight, reason}. `applicable` is False
    (weight 0) unless BOTH records carry a consented photo. The weight is capped
    at config.FACE_MAX_WEIGHT_CONTRIBUTION so face can only nudge the score."""
    if not (a.photo_ref and a.photo_consented and b.photo_ref and b.photo_consented):
        return {"applicable": False, "similarity": None, "weight": 0.0,
                "reason": "no consented photo on one or both records — face skipped"}

    # Transient: embeddings live only inside this function call.
    ea = _transient_embedding(a.photo_ref)
    eb = _transient_embedding(b.photo_ref)
    sim = _cosine(ea, eb)
    del ea, eb  # explicit: nothing persisted

    # Map similarity (0..1) to a bounded, low weight. Even a perfect face match
    # contributes at most FACE_MAX_WEIGHT_CONTRIBUTION bits — never enough alone
    # to cross the high-confidence threshold.
    weight = round(max(0.0, sim) * config.FACE_MAX_WEIGHT_CONTRIBUTION, 3)
    return {
        "applicable": True,
        "similarity": round(sim, 4),
        "weight": weight,
        "reason": f"consented photo similarity {sim:.2f} "
                  f"(capped at {config.FACE_MAX_WEIGHT_CONTRIBUTION} bits, never decisive)",
    }
