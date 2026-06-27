"""PFIF-based data model for SETU.

We follow the People Finder Interchange Format (PFIF) shape: an append-only log
of **person records** and **note records**. Nothing is mutated in place — a
status change or a merge is expressed as a new note record. This is what makes
the store CRDT-friendly (latest source_date wins per field) and audit-safe.

The model is backend-agnostic. The runnable demo uses SQLite (also the real
edge/kiosk store); the production target is Postgres + pgvector. The DDL below
is plain SQL that both accept; the pgvector column is described in store.py.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def new_id(domain: str) -> str:
    """PFIF person_record_id: '<center-domain>/<uuid>' — origin is self-describing."""
    return f"{domain}/{uuid.uuid4().hex[:12]}"


# Record streams. We split intake into two streams so the cascade matches
# missing<->found across centers (the core cross-search the manual centers lack).
RECORD_MISSING = "missing"   # a family is searching for this person
RECORD_FOUND = "found"       # a volunteer/center logged a person they found

# Lifecycle status. Default for a fresh record is "warm": actively matchable.
STATUS_WARM = "warm"
STATUS_QUEUED = "queued"        # a high-confidence pair is awaiting human verify
STATUS_REUNITED = "reunited"    # human-attested reunion
STATUS_PURGED = "purged"        # content auto-purged post-reunion (DPDP)
STATUS_CLOSED = "closed"

NOTE_MATCH = "match"            # cascade proposed a candidate link
NOTE_DEDUP = "dedup_link"       # two records are the same person (8% problem)
NOTE_VERIFICATION = "verification"
NOTE_REUNION = "reunion"
NOTE_PA = "pa_announcement"
NOTE_STATUS = "status_change"
NOTE_ENROLMENT = "band_enrolment"


@dataclass
class PersonRecord:
    """A PFIF person record. `full_name` is OPTIONAL by design — 15% of real
    cases have no name, and the cascade must never depend on it."""

    person_record_id: str
    source_date: str                     # CRDT clock: latest wins per field
    record_type: str                     # RECORD_MISSING | RECORD_FOUND
    origin_domain: str                   # which center node created it

    # --- Reliable fields the cascade BLOCKS and SCORES on -------------------
    age_band: str = ""
    sex: str = "U"
    home_state: str = ""
    language: str = ""
    last_seen_zone: str = ""
    last_seen_time: str = ""             # ISO; when the person was last seen

    # --- Optional / lower-trust fields -------------------------------------
    full_name: Optional[str] = None      # may be absent; signal only, never a gate
    # physical_description is QUARANTINED: the data shows it is unreliable and
    # often describes the wrong person. It is stored but NOT used for blocking
    # or as a strong score signal — only as weak free-text context.
    physical_description: Optional[str] = None
    free_text: Optional[str] = None      # other narrative context (clothes, "lost near the blue tent")

    # --- Consented, transient photo pointer --------------------------------
    # We store only a local pointer/flag. Face EMBEDDINGS are computed on demand
    # and discarded — never persisted as a searchable index (inviolable Rule 2).
    photo_ref: Optional[str] = None
    photo_consented: bool = False

    # --- Lifecycle / privacy ----------------------------------------------
    status: str = STATUS_WARM
    consent_match: bool = True           # consent to be matched/searched
    consent_pa: bool = False             # consent to be named in a PA announcement
    expiry_date: str = ""                # auto-purge deadline (DPDP)
    is_minor: bool = False               # children -> hardened handover path

    entry_date: str = field(default_factory=_now_iso)
    author: str = ""                     # operator/volunteer id

    def to_row(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_row(row: dict) -> "PersonRecord":
        valid = {f.name for f in dataclasses.fields(PersonRecord)}
        return PersonRecord(**{k: v for k, v in row.items() if k in valid})


@dataclass
class NoteRecord:
    """A PFIF note record: append-only annotation on a person record. Matches,
    dedup links, verifications, reunions and PA firings are ALL notes — so the
    full decision history is immutable and replayable for audit."""

    note_record_id: str
    person_record_id: str                # the record this note annotates
    source_date: str
    note_type: str
    origin_domain: str
    author: str = ""
    text: str = ""
    # For link/match/dedup notes, the other record involved:
    linked_person_record_id: Optional[str] = None
    # Arbitrary structured payload (match weights, verifier attestation, etc.)
    payload_json: str = "{}"
    entry_date: str = field(default_factory=_now_iso)

    @property
    def payload(self) -> dict:
        try:
            return json.loads(self.payload_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_row(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_row(row: dict) -> "NoteRecord":
        valid = {f.name for f in dataclasses.fields(NoteRecord)}
        return NoteRecord(**{k: v for k, v in row.items() if k in valid})


def make_note(
    person_record_id: str,
    note_type: str,
    origin_domain: str,
    *,
    author: str = "system",
    text: str = "",
    linked_person_record_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> NoteRecord:
    return NoteRecord(
        note_record_id=new_id(origin_domain),
        person_record_id=person_record_id,
        source_date=_now_iso(),
        note_type=note_type,
        origin_domain=origin_domain,
        author=author,
        text=text,
        linked_person_record_id=linked_person_record_id,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# SQLite DDL. Append-only by convention (we only INSERT person/note rows; the
# "current" view of a record is the latest source_date, resolved in store.py).
# In Postgres, `embedding` becomes `vector(384)` with an HNSW index (pgvector);
# here we keep embeddings out of the hot table and compute on demand.
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS person_records (
    person_record_id      TEXT NOT NULL,
    source_date           TEXT NOT NULL,
    record_type           TEXT NOT NULL,
    origin_domain         TEXT NOT NULL,
    age_band              TEXT,
    sex                   TEXT,
    home_state            TEXT,
    language              TEXT,
    last_seen_zone        TEXT,
    last_seen_time        TEXT,
    full_name             TEXT,
    physical_description  TEXT,
    free_text             TEXT,
    photo_ref             TEXT,
    photo_consented       INTEGER DEFAULT 0,
    status                TEXT DEFAULT 'warm',
    consent_match         INTEGER DEFAULT 1,
    consent_pa            INTEGER DEFAULT 0,
    expiry_date           TEXT,
    is_minor              INTEGER DEFAULT 0,
    entry_date            TEXT,
    author                TEXT,
    PRIMARY KEY (person_record_id, source_date)
);

CREATE TABLE IF NOT EXISTS note_records (
    note_record_id           TEXT PRIMARY KEY,
    person_record_id         TEXT NOT NULL,
    source_date              TEXT NOT NULL,
    note_type                TEXT NOT NULL,
    origin_domain            TEXT NOT NULL,
    author                   TEXT,
    text                     TEXT,
    linked_person_record_id  TEXT,
    payload_json             TEXT,
    entry_date               TEXT
);

CREATE INDEX IF NOT EXISTS idx_person_blocking
    ON person_records (record_type, age_band, language, home_state, last_seen_zone);
CREATE INDEX IF NOT EXISTS idx_notes_person ON note_records (person_record_id);
CREATE INDEX IF NOT EXISTS idx_notes_type ON note_records (note_type);

-- Immutable audit log: every consent capture, match decision, PA firing and
-- purge is appended here and never updated/deleted (privacy.py enforces this).
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id     TEXT PRIMARY KEY,
    ts           TEXT NOT NULL,
    actor        TEXT NOT NULL,
    action       TEXT NOT NULL,
    subject_id   TEXT,
    detail_json  TEXT
);
"""

# Boolean columns stored as INTEGER in SQLite; helper for round-tripping.
_BOOL_FIELDS = {"photo_consented", "consent_match", "consent_pa", "is_minor"}


def encode_person_row(rec: PersonRecord) -> dict:
    row = rec.to_row()
    for b in _BOOL_FIELDS:
        row[b] = 1 if row.get(b) else 0
    return row


def decode_person_row(row: dict) -> PersonRecord:
    row = dict(row)
    for b in _BOOL_FIELDS:
        if b in row:
            row[b] = bool(row[b])
    return PersonRecord.from_row(row)
