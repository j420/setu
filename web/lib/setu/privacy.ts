// Consent, audit, DPDP purge, and the HUMAN HANDOVER GATE (port of privacy.py).
// INVIOLABLE RULE 1: a handover can never be confirmed without a passing
// human attestation. A match score is NOT a valid verification method.

import { PersonRecord, nowIso } from "./types";

export class HandoverGateError extends Error {}

export const VALID_VERIFICATION_METHODS = new Set([
  "relationship_question",
  "safe_word",
  "government_id",
  "family_photo_recognition",
  "other",
]);

export interface HumanAttestation {
  verifier_id: string;
  method: string;
  passed: boolean;
  note?: string;
}

export function validateAttestation(a: HumanAttestation): void {
  if (!a.verifier_id)
    throw new HandoverGateError("handover blocked: no human verifier id");
  if (!VALID_VERIFICATION_METHODS.has(a.method))
    throw new HandoverGateError(
      `handover blocked: '${a.method}' is not a valid human verification method`,
    );
  if (!a.passed)
    throw new HandoverGateError(
      "handover blocked: human verification did NOT pass — no reunion confirmed",
    );
}

export function isHardenedHandover(rec: PersonRecord): boolean {
  return (
    rec.is_minor ||
    (!rec.full_name && (rec.age_band === "0-12" || rec.age_band === "13-17"))
  );
}

// Purge identifying content (DPDP minimisation), keep a non-identifying stub.
export function purgeContent(rec: PersonRecord): PersonRecord {
  return {
    ...rec,
    full_name: null,
    physical_description: null,
    free_text: null,
    photo_ref: null,
    photo_consented: false,
    status: "purged",
    source_date: nowIso(),
  };
}
