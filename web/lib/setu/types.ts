// PFIF-based data model (TypeScript port of setu/schema.py).
// Append-only person + note records; name is OPTIONAL by design.

export type RecordType = "missing" | "found";

export type Status =
  | "warm"
  | "queued"
  | "reunited"
  | "purged"
  | "closed";

export type Sex = "F" | "M" | "U";

export interface PersonRecord {
  person_record_id: string;
  source_date: string; // ISO; CRDT clock
  record_type: RecordType;
  origin_domain: string;

  // reliable fields the cascade blocks + scores on
  age_band: string;
  sex: Sex;
  home_state: string;
  language: string;
  last_seen_zone: string;
  last_seen_time: string; // ISO or ""

  // optional / lower-trust
  full_name?: string | null; // may be absent — signal only, never a gate
  physical_description?: string | null; // QUARANTINED low-trust
  free_text?: string | null;

  // consented, transient photo pointer (embeddings never persisted)
  photo_ref?: string | null;
  photo_consented: boolean;

  // lifecycle / privacy
  status: Status;
  consent_match: boolean;
  consent_pa: boolean;
  expiry_date: string;
  is_minor: boolean;

  entry_date: string;
  author: string;
}

export type NoteType =
  | "match"
  | "dedup_link"
  | "verification"
  | "reunion"
  | "pa_announcement"
  | "status_change"
  | "band_enrolment";

export interface NoteRecord {
  note_record_id: string;
  person_record_id: string;
  source_date: string;
  note_type: NoteType;
  origin_domain: string;
  author: string;
  text: string;
  linked_person_record_id?: string | null;
  payload: Record<string, unknown>;
  entry_date: string;
}

let _counter = 0;
function rand12(): string {
  // deterministic-enough unique-ish id without crypto dependency
  _counter = (_counter + 1) % 1_000_000;
  const t =
    (typeof performance !== "undefined" && performance.now
      ? Math.floor(performance.now() * 1000)
      : 0) + _counter;
  return (t.toString(36) + Math.floor(_seededNoise() * 1e9).toString(36)).slice(
    0,
    12,
  );
}

// A tiny LCG so id generation works identically in node + browser and never
// throws in environments where Math.random is fine (we still want spread).
let _seed = 123456789;
function _seededNoise(): number {
  _seed = (_seed * 1103515245 + 12345) & 0x7fffffff;
  return _seed / 0x7fffffff;
}

export function newId(domain: string): string {
  return `${domain}/${rand12()}`;
}

// Strictly-monotonic CRDT clock: two writes in the same millisecond still get
// distinct, ordered source_dates, so last-writer-wins is unambiguous and an
// append-only version is never dropped on an id+timestamp collision.
let _lastMs = 0;
export function nowIso(): string {
  let ms = Date.now();
  if (ms <= _lastMs) ms = _lastMs + 1;
  _lastMs = ms;
  return new Date(ms).toISOString();
}

export function makePerson(
  partial: Partial<PersonRecord> & {
    record_type: RecordType;
    origin_domain: string;
  },
): PersonRecord {
  return {
    person_record_id: partial.person_record_id ?? newId(partial.origin_domain),
    source_date: partial.source_date ?? nowIso(),
    age_band: partial.age_band ?? "",
    sex: partial.sex ?? "U",
    home_state: partial.home_state ?? "",
    language: partial.language ?? "",
    last_seen_zone: partial.last_seen_zone ?? "",
    last_seen_time: partial.last_seen_time ?? "",
    full_name: partial.full_name ?? null,
    physical_description: partial.physical_description ?? null,
    free_text: partial.free_text ?? null,
    photo_ref: partial.photo_ref ?? null,
    photo_consented: partial.photo_consented ?? false,
    status: partial.status ?? "warm",
    consent_match: partial.consent_match ?? true,
    consent_pa: partial.consent_pa ?? false,
    expiry_date: partial.expiry_date ?? "",
    is_minor: partial.is_minor ?? false,
    entry_date: partial.entry_date ?? nowIso(),
    author: partial.author ?? "intake",
    record_type: partial.record_type,
    origin_domain: partial.origin_domain,
  };
}
