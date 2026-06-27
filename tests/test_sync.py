"""Tests for the federation/CRDT sync layer and offline store-and-forward."""

from setu.schema import RECORD_FOUND, STATUS_REUNITED
from setu.store import Store, StoreAndForwardBuffer, sync_pair


def test_record_created_at_a_visible_at_b_after_sync(mk):
    a = Store("ramkund")
    b = Store("panchavati")
    rec = mk(record_type=RECORD_FOUND, domain=a.domain, full_name=None)
    a.put_person(rec)
    assert b.get_person(rec.person_record_id) is None
    sync_pair(a, b)
    assert b.get_person(rec.person_record_id) is not None


def test_sync_is_idempotent(mk):
    a = Store("ramkund")
    b = Store("panchavati")
    a.put_person(mk(domain=a.domain))
    first = sync_pair(a, b)
    second = sync_pair(a, b)
    assert first["a_to_b"]["persons_added"] == 1
    assert second["a_to_b"]["persons_added"] == 0  # nothing new the second time


def test_latest_source_date_wins(mk):
    """Last-writer-wins: an updated status syncs and supersedes the old view."""
    a = Store("ramkund")
    b = Store("panchavati")
    rec = mk(domain=a.domain)
    a.put_person(rec)
    sync_pair(a, b)
    a.update_status(rec.person_record_id, STATUS_REUNITED)
    sync_pair(a, b)
    assert b.get_person(rec.person_record_id).status == STATUS_REUNITED


def test_offline_intake_and_reconnect(mk):
    """Intake works with zero connectivity; buffered delta syncs on reconnect."""
    a = Store("ramkund")
    b = Store("panchavati")
    buf = StoreAndForwardBuffer()

    before = a.export_since()["watermark"]
    rec = mk(record_type=RECORD_FOUND, domain=a.domain, full_name=None)
    a.put_person(rec)  # created while "offline"
    buf.queue(a.export_since(since=before))

    assert b.get_person(rec.person_record_id) is None  # not yet visible
    assert len(buf) == 1
    flushed = buf.flush_into(b)
    assert flushed["persons_added"] == 1
    assert b.get_person(rec.person_record_id) is not None
    assert len(buf) == 0
