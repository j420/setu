// Client-side store + federation simulation (port of store.py + the gated
// reunion flow). Append-only; current view = latest source_date per id.
// Offline-first: everything runs in the browser, no server required.

import {
  NoteRecord,
  PersonRecord,
  RecordType,
  Status,
  makePerson,
  newId,
  nowIso,
} from "./types";
import { CENTERS, DEFAULT_RETENTION_DAYS } from "./config";
import {
  HandoverGateError,
  HumanAttestation,
  purgeContent,
  validateAttestation,
} from "./privacy";

export interface AuditEntry {
  audit_id: string;
  ts: string;
  actor: string;
  action: string;
  subject_id: string;
  detail: Record<string, unknown>;
}

export class Store {
  centerKey: string;
  domain: string;
  // append-only version log keyed by id -> versions (latest wins)
  private versions = new Map<string, PersonRecord[]>();
  notes: NoteRecord[] = [];
  audit: AuditEntry[] = [];

  constructor(centerKey: string) {
    if (!(centerKey in CENTERS)) throw new Error(`unknown center: ${centerKey}`);
    this.centerKey = centerKey;
    this.domain = CENTERS[centerKey].domain;
  }

  putPerson(rec: PersonRecord): PersonRecord {
    const list = this.versions.get(rec.person_record_id) ?? [];
    // idempotent on (id, source_date)
    if (!list.some((v) => v.source_date === rec.source_date)) list.push(rec);
    this.versions.set(rec.person_record_id, list);
    return rec;
  }

  getPerson(id: string): PersonRecord | null {
    const list = this.versions.get(id);
    if (!list || list.length === 0) return null;
    return list.reduce((a, b) => (a.source_date >= b.source_date ? a : b));
  }

  allPersons(filter: { record_type?: RecordType; status?: Status } = {}): PersonRecord[] {
    const out: PersonRecord[] = [];
    for (const id of this.versions.keys()) {
      const rec = this.getPerson(id);
      if (!rec) continue;
      if (filter.record_type && rec.record_type !== filter.record_type) continue;
      if (filter.status && rec.status !== filter.status) continue;
      out.push(rec);
    }
    return out;
  }

  updateStatus(id: string, status: Status): PersonRecord | null {
    const rec = this.getPerson(id);
    if (!rec) return null;
    return this.putPerson({ ...rec, status, source_date: nowIso() });
  }

  addNote(note: NoteRecord): NoteRecord {
    if (!this.notes.some((n) => n.note_record_id === note.note_record_id))
      this.notes.push(note);
    return note;
  }

  notesFor(id: string): NoteRecord[] {
    return this.notes
      .filter((n) => n.person_record_id === id)
      .sort((a, b) => a.source_date.localeCompare(b.source_date));
  }

  appendAudit(actor: string, action: string, subject: string, detail: Record<string, unknown>) {
    this.audit.push({
      audit_id: newId(this.domain),
      ts: nowIso(),
      actor,
      action,
      subject_id: subject,
      detail,
    });
  }

  // create a federated PFIF record (default status warm)
  createRecord(intake: Partial<PersonRecord> & { record_type: RecordType }): PersonRecord {
    const retentionMs = DEFAULT_RETENTION_DAYS * 24 * 3600 * 1000;
    const rec = makePerson({
      ...intake,
      origin_domain: this.domain,
      person_record_id: newId(this.domain),
      source_date: nowIso(),
      expiry_date: new Date(Date.now() + retentionMs).toISOString(),
    });
    this.putPerson(rec);
    this.appendAudit(rec.author, "create_record", rec.person_record_id, {
      consent_match: rec.consent_match,
    });
    return rec;
  }

  // THE HANDOVER GATE: confirm a reunion ONLY with a passing human attestation.
  confirmReunion(caseId: string, linkedId: string, att: HumanAttestation) {
    validateAttestation(att); // throws HandoverGateError unless a human passed a real check

    this.addNote(this.makeNote(caseId, "verification", {
      author: att.verifier_id,
      text: `Human verification via ${att.method}: PASSED. ${att.note ?? ""}`,
      linked: linkedId,
      payload: { ...att },
    }));
    for (const id of [caseId, linkedId]) this.updateStatus(id, "reunited");
    this.addNote(this.makeNote(caseId, "reunion", {
      author: att.verifier_id,
      text: `Reunion confirmed by ${att.verifier_id} via ${att.method}.`,
      linked: linkedId,
      payload: { verifier_id: att.verifier_id, method: att.method },
    }));
    this.appendAudit(att.verifier_id, "reunion_confirmed", caseId, { linkedId });

    const purged: string[] = [];
    for (const id of [caseId, linkedId]) {
      const rec = this.getPerson(id);
      if (rec) {
        this.putPerson(purgeContent(rec));
        this.appendAudit(att.verifier_id, "auto_purge", id, {
          reason: "post-reunion DPDP minimisation",
        });
        purged.push(id);
      }
    }
    return { reunited: [caseId, linkedId], purged };
  }

  makeNote(
    personId: string,
    type: NoteRecord["note_type"],
    opts: {
      author?: string;
      text?: string;
      linked?: string | null;
      payload?: Record<string, unknown>;
    } = {},
  ): NoteRecord {
    return {
      note_record_id: newId(this.domain),
      person_record_id: personId,
      source_date: nowIso(),
      note_type: type,
      origin_domain: this.domain,
      author: opts.author ?? "system",
      text: opts.text ?? "",
      linked_person_record_id: opts.linked ?? null,
      payload: opts.payload ?? {},
      entry_date: nowIso(),
    };
  }

  // federation: export/import deltas (last-writer-wins, idempotent)
  exportAll() {
    const persons: PersonRecord[] = [];
    for (const list of this.versions.values()) persons.push(...list);
    return { persons, notes: this.notes.slice() };
  }

  importRecords(delta: { persons: PersonRecord[]; notes: NoteRecord[] }) {
    let p = 0,
      n = 0;
    for (const rec of delta.persons) {
      const list = this.versions.get(rec.person_record_id) ?? [];
      if (!list.some((v) => v.source_date === rec.source_date)) {
        list.push(rec);
        this.versions.set(rec.person_record_id, list);
        p++;
      }
    }
    for (const note of delta.notes) {
      if (!this.notes.some((x) => x.note_record_id === note.note_record_id)) {
        this.notes.push(note);
        n++;
      }
    }
    return { persons_added: p, notes_added: n };
  }
}

export { HandoverGateError };

export function syncPair(a: Store, b: Store) {
  const aToB = b.importRecords(a.exportAll());
  const bToA = a.importRecords(b.exportAll());
  return { a_to_b: aToB, b_to_a: bToA };
}
