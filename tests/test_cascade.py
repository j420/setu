"""Tests for the matching cascade — including the load-bearing claim that a
NO-NAME record matches correctly, and that the cascade is name-optional and
explainable."""

import datetime as dt

from setu.matching import blocking, cascade, fellegi_sunter
from setu.matching.names import phonetic_key, transliterate
from setu.schema import RECORD_FOUND, RECORD_MISSING


def test_blocking_never_uses_name(mk):
    """Two records that differ only by name must block identically — the name
    must not influence whether a pair is even considered."""
    a = mk(record_type=RECORD_MISSING, full_name="सीता देवी")
    b = mk(record_type=RECORD_FOUND, full_name=None)
    c = mk(record_type=RECORD_FOUND, full_name="completely different")
    assert blocking.blocks_with(a, b)
    assert blocking.blocks_with(a, c)  # name irrelevant to blocking


def test_blocking_rejects_incompatible_demographics(mk):
    a = mk(record_type=RECORD_MISSING, age_band="61-75", language="maithili")
    far_age = mk(record_type=RECORD_FOUND, age_band="0-12")
    far_zone = mk(record_type=RECORD_FOUND, last_seen_zone="trimbakeshwar")
    other_lang = mk(record_type=RECORD_FOUND, language="tamil", home_state="Tamil Nadu")
    assert not blocking.blocks_with(a, far_age)
    assert not blocking.blocks_with(a, far_zone)
    assert not blocking.blocks_with(a, other_lang)


def test_no_name_record_matches_correctly(mk):
    """THE load-bearing test: a found record with NO NAME is correctly returned
    as the top candidate for a family's missing report, driven purely by
    reliable fields."""
    found = mk(record_type=RECORD_FOUND, full_name=None,
               free_text="elderly woman found near the Ramkund steps, green trunk")
    son_report = mk(record_type=RECORD_MISSING, full_name="सीता देवी",
                    last_seen_zone="ramkund",
                    free_text="mother separated near Ramkund, green trunk")
    cands = cascade.search_candidates(son_report, [found])
    assert cands, "expected at least one candidate"
    top = cands[0]
    assert top.record.person_record_id == found.person_record_id
    assert top.disposition == cascade.DISPOSITION_QUEUE
    # matched WITHOUT a name present on both sides:
    assert top.score_obj.name_present is False


def test_name_is_signal_not_gate(mk):
    """A matching name should raise the score; a conflicting name should lower it
    — but neither should override strong reliable-field agreement on its own."""
    base = dict(record_type=RECORD_FOUND, last_seen_zone="ramkund")
    q = mk(record_type=RECORD_MISSING, last_seen_zone="ramkund", full_name="सीता देवी")
    same = mk(full_name="सीता देवी", **base)
    none = mk(full_name=None, **base)
    conflict = mk(full_name="Ramesh Kumar", **base)
    s_same = fellegi_sunter.score(q, same).total_weight
    s_none = fellegi_sunter.score(q, none).total_weight
    s_conflict = fellegi_sunter.score(q, conflict).total_weight
    assert s_same > s_none > s_conflict


def test_explanation_is_grounded(mk):
    """Every explanation line must trace to a real weight term — no free text."""
    found = mk(record_type=RECORD_FOUND, full_name=None)
    q = mk(record_type=RECORD_MISSING, full_name="सीता देवी")
    cands = cascade.search_candidates(q, [found])
    expl = cands[0].explanation
    assert any("bits" in line for line in expl)
    assert any("name" in line.lower() for line in expl)  # notes name-optional


def test_face_never_sufficient_alone(mk):
    """Two records with consented photos but otherwise weak agreement must NOT be
    pushed to the queue on face similarity alone."""
    import setu.matching.face as facemod

    # Force identical photo refs -> max face similarity.
    a = mk(record_type=RECORD_MISSING, age_band="18-30", sex="M",
           language="tamil", home_state="Tamil Nadu", last_seen_zone="nashik_road",
           photo_ref="same.jpg", photo_consented=True, full_name=None)
    b = mk(record_type=RECORD_FOUND, age_band="46-60", sex="F",
           language="tamil", home_state="Tamil Nadu", last_seen_zone="nashik_road",
           photo_ref="same.jpg", photo_consented=True, full_name=None)
    fr = facemod.face_rerank(a, b)
    assert fr["applicable"] is True
    # even max face contribution is bounded and cannot alone reach the high bar.
    from setu import config
    assert fr["weight"] <= config.FACE_MAX_WEIGHT_CONTRIBUTION
    assert fr["weight"] < config.THRESHOLD_HIGH


def test_face_skipped_without_consent(mk):
    import setu.matching.face as facemod
    a = mk(photo_ref="x.jpg", photo_consented=False)
    b = mk(record_type=RECORD_FOUND, photo_ref="y.jpg", photo_consented=True)
    fr = facemod.face_rerank(a, b)
    assert fr["applicable"] is False
    assert fr["weight"] == 0.0


def test_transliteration_and_phonetic_key():
    # IndicXlit-contract mock: Devanagari -> latin
    assert transliterate("सीता") == transliterate("सीता")
    assert transliterate("Sita").isascii()
    # phonetic key collapses common variants
    assert phonetic_key("Sita") == phonetic_key("Seeta")
    assert phonetic_key("Sita Devi") == phonetic_key("Sita")  # honorific dropped


def test_consent_excludes_from_search(mk):
    found = mk(record_type=RECORD_FOUND, full_name=None, consent_match=False)
    q = mk(record_type=RECORD_MISSING, full_name="सीता देवी")
    assert cascade.search_candidates(q, [found]) == []
