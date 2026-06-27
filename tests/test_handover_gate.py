"""Tests for INVIOLABLE RULE 1: a handover can never be automated. There must be
NO code path that confirms a reunion without a passing human attestation."""

import pytest

from setu.mcp_server import SetuService
from setu.privacy import (
    HandoverGateError,
    HumanAttestation,
    confirm_reunion,
)
from setu.schema import RECORD_FOUND, RECORD_MISSING, STATUS_PURGED, STATUS_REUNITED
from setu.store import Store


@pytest.fixture
def service_with_pair(mk):
    store = Store("panchavati")
    a = mk(record_type=RECORD_MISSING, domain=store.domain, full_name="सीता देवी")
    b = mk(record_type=RECORD_FOUND, domain=store.domain, full_name=None)
    store.put_person(a)
    store.put_person(b)
    return SetuService(store), a.person_record_id, b.person_record_id


def test_reunion_requires_verifier(service_with_pair):
    svc, a, b = service_with_pair
    with pytest.raises(HandoverGateError):
        svc.record_reunion_and_purge(case_id=a, linked_id=b, verifier_id="",
                                     method="relationship_question", passed=True)


def test_score_is_not_a_valid_verification_method(service_with_pair):
    """A match score — however high — is not a human verification method."""
    svc, a, b = service_with_pair
    with pytest.raises(HandoverGateError):
        svc.record_reunion_and_purge(case_id=a, linked_id=b, verifier_id="v1",
                                     method="match_score_0.99", passed=True)


def test_failed_check_blocks_reunion(service_with_pair):
    svc, a, b = service_with_pair
    with pytest.raises(HandoverGateError):
        svc.record_reunion_and_purge(case_id=a, linked_id=b, verifier_id="v1",
                                     method="relationship_question", passed=False)


def test_valid_human_attestation_confirms_and_purges(service_with_pair):
    svc, a, b = service_with_pair
    res = svc.record_reunion_and_purge(
        case_id=a, linked_id=b, verifier_id="verifier-7",
        method="relationship_question", passed=True,
        note="named youngest grandchild correctly")
    assert set(res["reunited"]) == {a, b}
    # both records purged of identifying content
    for pid in (a, b):
        rec = svc.store.get_person(pid)
        assert rec.status == STATUS_PURGED
        assert rec.full_name is None
        assert rec.free_text is None
        assert rec.photo_ref is None


def test_enqueue_cannot_confirm(service_with_pair):
    """enqueue_for_human_verification only flags; it must not reunite/purge."""
    svc, a, b = service_with_pair
    svc.enqueue_for_human_verification(a, b)
    for pid in (a, b):
        rec = svc.store.get_person(pid)
        assert rec.status != STATUS_REUNITED
        assert rec.status != STATUS_PURGED
        assert rec.full_name is not None or pid == b  # content intact


def test_no_attestation_overload_exists():
    """There is no confirm_reunion variant that accepts a score instead of a
    HumanAttestation — guard against a future regression."""
    import inspect
    from setu import privacy

    sig = inspect.signature(privacy.confirm_reunion)
    assert "attestation" in sig.parameters
    # the attestation type must be the human-gate object
    assert "score" not in sig.parameters
    assert "match_weight" not in sig.parameters


def test_audit_log_records_reunion(service_with_pair):
    svc, a, b = service_with_pair
    svc.record_reunion_and_purge(case_id=a, linked_id=b, verifier_id="verifier-7",
                                 method="safe_word", passed=True)
    actions = [e["action"] for e in svc.store.audit_entries()]
    assert "reunion_confirmed" in actions
    assert "auto_purge" in actions
