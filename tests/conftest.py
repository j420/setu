import datetime as dt

import pytest

from setu.schema import PersonRecord, RECORD_FOUND, RECORD_MISSING, new_id


def _now_off(minutes: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)).isoformat()


@pytest.fixture
def mk():
    """Factory for PersonRecords with sensible defaults."""
    def _mk(record_type=RECORD_MISSING, domain="ramkund.setu", **kw):
        base = dict(
            person_record_id=new_id(domain),
            source_date=dt.datetime.now(dt.timezone.utc).isoformat(),
            record_type=record_type,
            origin_domain=domain,
            age_band="61-75",
            sex="F",
            home_state="Bihar",
            language="maithili",
            last_seen_zone="ramkund",
            last_seen_time=_now_off(40),
            full_name=None,
        )
        base.update(kw)
        return PersonRecord(**base)
    return _mk
