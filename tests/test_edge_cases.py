"""Real-world robustness: the cascade and tools must never crash on messy input
and must degrade sensibly. These mirror the edge cases the TS web engine is also
tested against (web/lib/setu/__tests__)."""

import datetime as dt

import pytest

from setu import pa
from setu.matching import blocking, cascade, fellegi_sunter, semantic
from setu.matching.names import name_agreement, phonetic_key, transliterate
from setu.mcp_server import SetuService
from setu.schema import RECORD_FOUND, RECORD_MISSING
from setu.store import Store


def test_empty_pool_returns_no_candidates(mk):
    q = mk(record_type=RECORD_MISSING, full_name="सीता देवी")
    assert cascade.search_candidates(q, []) == []


def test_all_fields_blank_does_not_crash():
    from setu.schema import PersonRecord, new_id
    blank_a = PersonRecord(person_record_id=new_id("ramkund.setu"),
                           source_date=dt.datetime.now(dt.timezone.utc).isoformat(),
                           record_type=RECORD_MISSING, origin_domain="ramkund.setu")
    blank_b = PersonRecord(person_record_id=new_id("panchavati.setu"),
                           source_date=dt.datetime.now(dt.timezone.utc).isoformat(),
                           record_type=RECORD_FOUND, origin_domain="panchavati.setu")
    # blank records have no demographic anchor -> should not block, no crash
    assert blocking.blocks_with(blank_a, blank_b) is False
    cands = cascade.search_candidates(blank_a, [blank_b])
    assert cands == []
    ms = fellegi_sunter.score(blank_a, blank_b)  # scoring blank pair is safe
    assert isinstance(ms.total_weight, float)


def test_unknown_language_and_zone_are_handled(mk):
    q = mk(record_type=RECORD_MISSING, language="klingon", last_seen_zone="atlantis",
           home_state="Bihar")
    c = mk(record_type=RECORD_FOUND, language="klingon", last_seen_zone="atlantis",
           home_state="Bihar")
    # zones_adjacent treats unknown zones as only self-adjacent -> same string ok
    cands = cascade.search_candidates(q, [c])
    assert isinstance(cands, list)  # no crash; may or may not match
    # PA falls back to a default template for an unknown language
    script = pa.generate_pa_script(zone="atlantis", language="klingon",
                                   age_band="61-75")
    assert script.native_text


def test_malformed_timestamps_do_not_crash(mk):
    a = mk(record_type=RECORD_MISSING, last_seen_time="not-a-date",
           full_name="सीता देवी")
    b = mk(record_type=RECORD_FOUND, last_seen_time="", full_name=None)
    assert isinstance(blocking.blocks_with(a, b), bool)
    ms = fellegi_sunter.score(a, b)
    assert isinstance(ms.total_weight, float)


def test_naive_and_aware_times_compare(mk):
    naive = dt.datetime.now().isoformat()                       # no tz
    aware = dt.datetime.now(dt.timezone.utc).isoformat()        # tz-aware
    a = mk(record_type=RECORD_MISSING, last_seen_time=naive, full_name="सीता देवी")
    b = mk(record_type=RECORD_FOUND, last_seen_time=aware, full_name=None)
    assert isinstance(blocking.blocks_with(a, b), bool)
    fellegi_sunter.score(a, b)  # must not raise on mixed tz


def test_logistic_is_numerically_stable():
    assert 0.0 <= fellegi_sunter._logistic(-1e6) <= 1.0
    assert 0.0 <= fellegi_sunter._logistic(1e6) <= 1.0
    assert abs(fellegi_sunter._logistic(0.0) - 0.5) < 1e-9


def test_very_long_and_mixed_script_freetext(mk):
    long_text = ("green trunk near Ramkund " * 500) + "हरी पेटी रामकुंड"
    a = mk(record_type=RECORD_MISSING, free_text=long_text, full_name=None)
    b = mk(record_type=RECORD_FOUND, free_text=long_text, full_name=None)
    sim = semantic.semantic_similarity(a.free_text, b.free_text)
    assert 0.0 <= sim <= 1.0001


def test_phonetic_key_handles_empty_and_symbols():
    assert phonetic_key("") == ""
    assert phonetic_key("123 !!!") == ""
    assert name_agreement(None, "x")["present"] is False
    assert name_agreement("", "")["present"] is False


def test_self_match_excluded(mk):
    rec = mk(record_type=RECORD_MISSING, full_name="सीता देवी")
    # a record never matches itself even if present in the pool
    assert cascade.search_candidates(rec, [rec]) == []


def test_duplicate_creation_is_idempotent_on_id(mk):
    store = Store("ramkund")
    rec = mk(record_type=RECORD_FOUND, domain=store.domain, full_name=None)
    store.put_person(rec)
    store.put_person(rec)  # same id+source_date -> replace, not duplicate
    assert len([r for r in store.all_persons()
                if r.person_record_id == rec.person_record_id]) == 1


def test_create_record_with_minimal_intake():
    store = Store("ramkund")
    svc = SetuService(store)
    res = svc.create_person_record({})  # empty intake must still create a record
    assert "person_record_id" in res
    assert res["status"] == "warm"


def test_search_unknown_record_id_returns_error():
    store = Store("ramkund")
    svc = SetuService(store)
    assert "error" in svc.search_candidates("does-not-exist")
    assert "error" in svc.get_case_status("does-not-exist")


def test_pa_all_languages_no_name_safe():
    from setu.config import LANGUAGES
    for lang in LANGUAGES:
        s = pa.generate_pa_script(zone="ramkund", language=lang, name=None)
        assert s.native_text and s.pa_locale
