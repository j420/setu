"""Tests for dedup (the 8% problem), PA generation, proactive bands and purge."""

import datetime as dt

from setu import pa, proactive
from setu.matching import dedup
from setu.privacy import purge_expired
from setu.schema import RECORD_FOUND, STATUS_PURGED
from setu.store import Store


def test_dedup_links_same_person_without_destroying(mk):
    store = Store("ramkund")
    f1 = mk(record_type=RECORD_FOUND, domain=store.domain, full_name="सीता देवी",
            free_text="green trunk near Ramkund")
    # same person re-reported at a second center (copy of key fields)
    f2 = mk(record_type=RECORD_FOUND, domain="panchavati.setu", full_name="सीता देवी",
            last_seen_zone=f1.last_seen_zone, last_seen_time=f1.last_seen_time,
            free_text="green trunk near Ramkund")
    store.put_person(f1)
    store.put_person(f2)
    pairs = dedup.find_duplicates([f1, f2])
    assert pairs, "expected the duplicate to be detected"
    dedup.link_duplicate(store, pairs[0])
    # both original records still exist (append-only, never destructively merged)
    assert store.get_person(f1.person_record_id) is not None
    assert store.get_person(f2.person_record_id) is not None
    notes = store.notes_for(f1.person_record_id)
    assert any(n.note_type == "dedup_link" for n in notes)


def test_pa_name_optional_uses_noname_template():
    named = pa.generate_pa_script(zone="ramkund", language="maithili",
                                  age_band="61-75", home_state="Bihar",
                                  name="सीता देवी")
    noname = pa.generate_pa_script(zone="ramkund", language="maithili",
                                   age_band="61-75", home_state="Bihar", name=None)
    assert "सीता देवी" in named.native_text
    assert "सीता देवी" not in noname.native_text
    assert named.pa_locale == "mai-IN"
    assert named.templated and not named.requires_human_approval


def test_freetext_pa_requires_human_approval():
    script = pa.generate_pa_script(zone="ramkund", language="hindi",
                                   age_band="61-75", free_text="please rush, urgent")
    assert script.requires_human_approval is True
    assert script.templated is False


def test_all_ten_languages_have_templates():
    from setu.config import LANGUAGES
    for lang in LANGUAGES:
        s = pa.generate_pa_script(zone="ramkund", language=lang, age_band="61-75")
        assert s.native_text  # a script exists for every language


def test_band_stores_only_pointer_and_resolves():
    store = Store("ramkund")
    band = proactive.enrol_band(store, group_contact_pointer="group://family-42",
                                meeting_point="Lost & Found tent, Ramkund")
    res = proactive.scan_band(band.token_id)
    assert res["found"] is True
    assert res["group_contact_pointer"] == "group://family-42"
    # unknown token resolves gracefully
    assert proactive.scan_band("mauli-unknown")["found"] is False


def test_expired_records_are_purged(mk):
    store = Store("ramkund")
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
    rec = mk(record_type=RECORD_FOUND, domain=store.domain, full_name="X",
             expiry_date=past)
    store.put_person(rec)
    purged = purge_expired(store)
    assert rec.person_record_id in purged
    assert store.get_person(rec.person_record_id).status == STATUS_PURGED
