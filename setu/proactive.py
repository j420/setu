"""Proactive layer: 'mauli' bands + predictive pre-positioning.

Upstream voice enrolment of at-risk elders/children produces a waterproof QR/NFC
band. CRITICAL: the band stores ONLY a token pointer — never personal data — that
resolves to a group-contact + meeting-point already indexed in the store. So a
volunteer scanning a band gets an instant, name-free reunification path.

Band coverage is a BONUS, never a dependency — the reactive cascade works with
zero bands. Predictive pre-positioning suggests where to stage PA/volunteers by
zone×time using historical case density.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass

from .schema import NOTE_ENROLMENT, PersonRecord, make_note


@dataclass
class BandRecord:
    """What the band physically carries: just a token. The PII lives in the
    store behind this pointer, governed by consent + purge like any record."""
    token_id: str
    group_contact_pointer: str    # opaque ref to the group's contact record
    meeting_point: str


# In-memory band index for the demo (token_id -> BandRecord). In production this
# is a small consented table; the band hardware holds only token_id.
_BAND_INDEX: dict[str, BandRecord] = {}


def enrol_band(
    store,
    *,
    group_contact_pointer: str,
    meeting_point: str,
    enrolled_by: str = "enrolment-kiosk",
    person_record_id: str | None = None,
) -> BandRecord:
    """Pre-index a band so scan_band resolves instantly. Returns the token to be
    written to the physical band."""
    token = f"mauli-{uuid.uuid4().hex[:10]}"
    band = BandRecord(token, group_contact_pointer, meeting_point)
    _BAND_INDEX[token] = band
    if person_record_id:
        store.add_note(make_note(
            person_record_id, NOTE_ENROLMENT, store.domain, author=enrolled_by,
            text=f"Mauli band enrolled (token {token}) -> meeting point {meeting_point}",
            payload={"token_id": token, "meeting_point": meeting_point},
        ))
    return band


def scan_band(token_id: str) -> dict:
    """Resolve a scanned band token to its group-contact pointer + meeting point.
    Returns {found, ...}. No personal data is stored on the band itself."""
    band = _BAND_INDEX.get(token_id)
    if band is None:
        return {"found": False, "token_id": token_id,
                "message": "band not recognised (may be from another deployment)"}
    return {
        "found": True,
        "token_id": token_id,
        "group_contact_pointer": band.group_contact_pointer,
        "meeting_point": band.meeting_point,
    }


def predict_hotspots(records: list[PersonRecord], top: int = 5) -> list[dict]:
    """Rank zones by historical case density for pre-positioning PA/volunteers."""
    counts = Counter(r.last_seen_zone for r in records if r.last_seen_zone)
    return [{"zone": z, "cases": n} for z, n in counts.most_common(top)]
