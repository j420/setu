"""Consent, audit, DPDP auto-purge, and the human handover gate.

This module structurally enforces the two inviolable rules:

  RULE 1 — NEVER automate a handover. `confirm_reunion` REQUIRES a human
  attestation object (verifier id + the verification method actually used, e.g. a
  relationship question or safe-word). There is NO code path that confirms a
  reunion from a match score. A `HandoverGateError` is raised if anyone tries.

  RULE 2 — NEVER persist biometrics. Enforced in matching/face.py (transient
  embeddings); here we additionally ensure purge wipes any photo pointer.

Auto-purge: on a confirmed reunion we purge identifying content (DPDP data
minimisation) while keeping a non-identifying audit stub, so we can still report
"a reunion happened" without retaining personal data.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

from .schema import (
    NOTE_REUNION,
    NOTE_VERIFICATION,
    STATUS_PURGED,
    STATUS_REUNITED,
    PersonRecord,
    make_note,
)


class HandoverGateError(Exception):
    """Raised when something tries to confirm a reunion without human attestation."""


# Verification methods a human verifier may use. Free-text 'other' is allowed but
# must be described. A score is NOT in this list — by construction.
VALID_VERIFICATION_METHODS = {
    "relationship_question",  # "what is the name of her youngest grandchild?"
    "safe_word",
    "government_id",
    "family_photo_recognition",
    "other",
}


@dataclass
class HumanAttestation:
    verifier_id: str            # the human accountable for this decision
    method: str                 # one of VALID_VERIFICATION_METHODS
    passed: bool                # did the family pass the check?
    note: str = ""              # e.g. the question asked / id type seen
    ts: str = ""

    def validate(self) -> None:
        if not self.verifier_id:
            raise HandoverGateError("handover blocked: no human verifier id")
        if self.method not in VALID_VERIFICATION_METHODS:
            raise HandoverGateError(
                f"handover blocked: '{self.method}' is not a valid human "
                f"verification method")
        if not self.passed:
            raise HandoverGateError(
                "handover blocked: human verification did NOT pass — "
                "no reunion confirmed")


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def record_verification(store, person_record_id: str, linked_id: str,
                        attestation: HumanAttestation) -> None:
    """Append an immutable verification note + audit entry. Does NOT itself
    confirm the reunion — it records that a human ran a check."""
    attestation.ts = attestation.ts or _now_iso()
    note = make_note(
        person_record_id, NOTE_VERIFICATION, store.domain,
        author=attestation.verifier_id,
        text=f"Human verification via {attestation.method}: "
             f"{'PASSED' if attestation.passed else 'FAILED'}. {attestation.note}",
        linked_person_record_id=linked_id,
        payload={"method": attestation.method, "passed": attestation.passed,
                 "note": attestation.note, "verifier_id": attestation.verifier_id},
    )
    store.add_note(note)
    store.append_audit(attestation.verifier_id, "verification", person_record_id,
                       json.dumps(note.payload))


def confirm_reunion(store, case_id: str, linked_id: str,
                    attestation: HumanAttestation) -> dict:
    """THE HANDOVER GATE. Confirms a reunion ONLY with a passing human
    attestation, then triggers auto-purge. Raises HandoverGateError otherwise.

    There is intentionally no overload that takes a match score."""
    attestation.validate()  # raises unless a human passed a real check

    record_verification(store, case_id, linked_id, attestation)

    # Mark both records reunited (append-only status change via store).
    for pid in (case_id, linked_id):
        rec = store.get_person(pid)
        if rec is not None:
            store.update_status(pid, STATUS_REUNITED)

    reunion_note = make_note(
        case_id, NOTE_REUNION, store.domain,
        author=attestation.verifier_id,
        text=f"Reunion confirmed by {attestation.verifier_id} "
             f"via {attestation.method}.",
        linked_person_record_id=linked_id,
        payload={"verifier_id": attestation.verifier_id, "method": attestation.method},
    )
    store.add_note(reunion_note)
    store.append_audit(attestation.verifier_id, "reunion_confirmed", case_id,
                       json.dumps({"linked_id": linked_id}))

    purged = [purge_record(store, pid, attestation.verifier_id)
              for pid in (case_id, linked_id)]
    return {"reunited": [case_id, linked_id], "purged": purged}


def purge_record(store, person_record_id: str, actor: str) -> str:
    """DPDP auto-purge: wipe identifying content, keep a non-identifying stub.
    Appends a purged version (append-only) so history shows the purge happened."""
    rec = store.get_person(person_record_id)
    if rec is None:
        return person_record_id
    # Wipe identifying fields; retain only band-level non-PII for metrics.
    rec.full_name = None
    rec.physical_description = None
    rec.free_text = None
    rec.photo_ref = None
    rec.photo_consented = False
    rec.status = STATUS_PURGED
    rec.source_date = _now_iso()
    store.put_person(rec)
    store.append_audit(actor, "auto_purge", person_record_id,
                       json.dumps({"reason": "post-reunion DPDP minimisation"}))
    return person_record_id


def purge_expired(store, now: dt.datetime | None = None) -> list[str]:
    """Sweep records past their consent-driven expiry_date and purge them."""
    now = now or dt.datetime.now(dt.timezone.utc)
    purged = []
    for rec in store.all_persons():
        if rec.status == STATUS_PURGED or not rec.expiry_date:
            continue
        try:
            exp = dt.datetime.fromisoformat(rec.expiry_date)
        except ValueError:
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=dt.timezone.utc)
        if exp <= now:
            purge_record(store, rec.person_record_id, "retention-sweep")
            purged.append(rec.person_record_id)
    return purged


def is_hardened_handover(rec: PersonRecord) -> bool:
    """Children & unidentified records take the hardened path: verifiable
    guardian consent + anti-trafficking checks, never an external sink."""
    return rec.is_minor or (not rec.full_name and rec.age_band in ("0-12", "13-17"))
