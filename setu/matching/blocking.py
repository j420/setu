"""Blocking: cheaply restrict the comparison space to plausible candidate pairs.

This is step 1 of the cascade and it is the most important privacy/robustness
choice in the system: we block ONLY on reliable fields and we NEVER block on
name. The blocking predicate is deliberately permissive (favours recall) because
the Fellegi-Sunter scorer downstream does the precise discrimination.

A candidate passes the block if ALL of:
  * compatible age_band (within 1 band of slack — intake age is an estimate),
  * zone-adjacency (same or walking-distance-neighbour zone),
  * time-window overlap (last-seen times within the window),
  * same language OR same home_state (at least one strong demographic anchor).

We block missing<->found (the cross-stream search the manual centers lack). The
same predicate, applied within a single stream, drives dedup.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

from .. import config
from ..schema import PersonRecord

# How far apart two "last seen" times can be and still block. People are found
# hours after they go missing, so the default window is generous.
DEFAULT_TIME_WINDOW_HOURS = 12.0


def _parse_time(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def _time_compatible(a: PersonRecord, b: PersonRecord, window_hours: float) -> bool:
    ta, tb = _parse_time(a.last_seen_time), _parse_time(b.last_seen_time)
    if ta is None or tb is None:
        return True  # missing time should not exclude a candidate
    # Normalise to aware/naive consistently.
    if ta.tzinfo and not tb.tzinfo:
        tb = tb.replace(tzinfo=ta.tzinfo)
    if tb.tzinfo and not ta.tzinfo:
        ta = ta.replace(tzinfo=tb.tzinfo)
    return abs((ta - tb).total_seconds()) <= window_hours * 3600


def blocks_with(
    a: PersonRecord, b: PersonRecord, window_hours: float = DEFAULT_TIME_WINDOW_HOURS
) -> bool:
    """True if (a, b) survive blocking and should be scored. Name is ignored."""
    if not config.age_bands_compatible(a.age_band, b.age_band):
        return False
    if not config.zones_adjacent(a.last_seen_zone, b.last_seen_zone):
        return False
    if not _time_compatible(a, b, window_hours):
        return False
    # At least one strong demographic anchor must agree.
    same_lang = bool(a.language) and a.language == b.language
    same_state = bool(a.home_state) and a.home_state == b.home_state
    if not (same_lang or same_state):
        return False
    return True


def candidate_block(
    query: PersonRecord,
    pool: Iterable[PersonRecord],
    *,
    opposite_stream: bool = True,
    window_hours: float = DEFAULT_TIME_WINDOW_HOURS,
) -> list[PersonRecord]:
    """Return the blocked candidate set for `query` from `pool`.

    opposite_stream=True  -> missing<->found matching (default).
    opposite_stream=False -> within-stream comparison for dedup.
    """
    out = []
    for cand in pool:
        if cand.person_record_id == query.person_record_id:
            continue
        if opposite_stream and cand.record_type == query.record_type:
            continue
        if not opposite_stream and cand.record_type != query.record_type:
            continue
        if not cand.consent_match:
            continue  # respect consent: not searchable
        if blocks_with(query, cand, window_hours):
            out.append(cand)
    return out
