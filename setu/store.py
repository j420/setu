"""Edge-node store + federation.

Each center runs a `Store` backed by SQLite (the same store used at kiosks).
The store is append-only: we only INSERT person/note rows. The *current* view of
a person record is the row with the latest `source_date` (a per-record Lamport-ish
clock). Merges are link-notes, not destructive updates.

Federation is CRDT-flavoured: `export_since`/`import_records` ship rows between
nodes; on import we keep the latest `source_date` (last-writer-wins per record).
Because every row is content-addressed by (id, source_date) and notes by id,
sync is idempotent and order-independent — so it works online (seconds) or via
store-and-forward when a node was offline, and reconciles cleanly on reconnect.

This is a runnable stand-in for the production design (Postgres + pgvector with
logical replication / a CRDT layer). The interface — export a delta, import a
delta, last-writer-wins — is the contract that production must honour.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Iterable, Optional

from . import config
from .schema import (
    SCHEMA_SQL,
    NoteRecord,
    PersonRecord,
    decode_person_row,
    encode_person_row,
)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Store:
    """A single edge node's replica."""

    def __init__(self, center_key: str, path: str = ":memory:"):
        if center_key not in config.CENTERS:
            raise ValueError(f"unknown center: {center_key}")
        self.center_key = center_key
        self.domain = config.CENTERS[center_key]["domain"]
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # -- writes -------------------------------------------------------------
    def put_person(self, rec: PersonRecord) -> PersonRecord:
        """Append a person-record version (a new version == a new source_date)."""
        row = encode_person_row(rec)
        cols = ", ".join(row.keys())
        ph = ", ".join("?" for _ in row)
        self.conn.execute(
            f"INSERT OR REPLACE INTO person_records ({cols}) VALUES ({ph})",
            list(row.values()),
        )
        self.conn.commit()
        return rec

    def add_note(self, note: NoteRecord) -> NoteRecord:
        row = note.to_row()
        cols = ", ".join(row.keys())
        ph = ", ".join("?" for _ in row)
        self.conn.execute(
            f"INSERT OR REPLACE INTO note_records ({cols}) VALUES ({ph})",
            list(row.values()),
        )
        self.conn.commit()
        return note

    def update_status(self, person_record_id: str, status: str) -> Optional[PersonRecord]:
        rec = self.get_person(person_record_id)
        if rec is None:
            return None
        rec.status = status
        rec.source_date = _now_iso()  # advance the CRDT clock so the change wins
        return self.put_person(rec)

    # -- reads (current view == latest source_date per id) ------------------
    def get_person(self, person_record_id: str) -> Optional[PersonRecord]:
        cur = self.conn.execute(
            """SELECT * FROM person_records WHERE person_record_id = ?
               ORDER BY source_date DESC LIMIT 1""",
            (person_record_id,),
        )
        r = cur.fetchone()
        return decode_person_row(dict(r)) if r else None

    def all_persons(
        self, record_type: Optional[str] = None, status: Optional[str] = None
    ) -> list[PersonRecord]:
        """Current view of every person record (latest version per id)."""
        cur = self.conn.execute("SELECT DISTINCT person_record_id FROM person_records")
        ids = [r[0] for r in cur.fetchall()]
        out = []
        for pid in ids:
            rec = self.get_person(pid)
            if rec is None:
                continue
            if record_type and rec.record_type != record_type:
                continue
            if status and rec.status != status:
                continue
            out.append(rec)
        return out

    def notes_for(self, person_record_id: str) -> list[NoteRecord]:
        cur = self.conn.execute(
            "SELECT * FROM note_records WHERE person_record_id = ? ORDER BY source_date",
            (person_record_id,),
        )
        return [NoteRecord.from_row(dict(r)) for r in cur.fetchall()]

    def all_notes(self, note_type: Optional[str] = None) -> list[NoteRecord]:
        q = "SELECT * FROM note_records"
        args: tuple = ()
        if note_type:
            q += " WHERE note_type = ?"
            args = (note_type,)
        cur = self.conn.execute(q + " ORDER BY source_date", args)
        return [NoteRecord.from_row(dict(r)) for r in cur.fetchall()]

    # -- federation (CRDT delta sync) ---------------------------------------
    def export_since(self, since: Optional[str] = None) -> dict:
        """Export all rows newer than `since` (a watermark). Idempotent payload."""
        pq = "SELECT * FROM person_records"
        nq = "SELECT * FROM note_records"
        pargs: tuple = ()
        nargs: tuple = ()
        if since:
            pq += " WHERE source_date > ?"
            nq += " WHERE source_date > ?"
            pargs = (since,)
            nargs = (since,)
        persons = [dict(r) for r in self.conn.execute(pq, pargs).fetchall()]
        notes = [dict(r) for r in self.conn.execute(nq, nargs).fetchall()]
        return {"persons": persons, "notes": notes, "watermark": _now_iso()}

    def import_records(self, delta: dict) -> dict:
        """Import a delta from a peer. Last-writer-wins per (id, source_date):
        we INSERT versions we don't already have; existing versions are no-ops.
        Returns counts so the sync demo can show what crossed the wire."""
        added_p = added_n = 0
        for prow in delta.get("persons", []):
            exists = self.conn.execute(
                "SELECT 1 FROM person_records WHERE person_record_id=? AND source_date=?",
                (prow["person_record_id"], prow["source_date"]),
            ).fetchone()
            if exists:
                continue
            cols = ", ".join(prow.keys())
            ph = ", ".join("?" for _ in prow)
            self.conn.execute(
                f"INSERT INTO person_records ({cols}) VALUES ({ph})", list(prow.values())
            )
            added_p += 1
        for nrow in delta.get("notes", []):
            exists = self.conn.execute(
                "SELECT 1 FROM note_records WHERE note_record_id=?",
                (nrow["note_record_id"],),
            ).fetchone()
            if exists:
                continue
            cols = ", ".join(nrow.keys())
            ph = ", ".join("?" for _ in nrow)
            self.conn.execute(
                f"INSERT INTO note_records ({cols}) VALUES ({ph})", list(nrow.values())
            )
            added_n += 1
        self.conn.commit()
        return {"persons_added": added_p, "notes_added": added_n}

    # -- audit --------------------------------------------------------------
    def append_audit(self, actor: str, action: str, subject_id: str, detail_json: str):
        import uuid

        self.conn.execute(
            "INSERT INTO audit_log (audit_id, ts, actor, action, subject_id, detail_json)"
            " VALUES (?,?,?,?,?,?)",
            (uuid.uuid4().hex, _now_iso(), actor, action, subject_id, detail_json),
        )
        self.conn.commit()

    def audit_entries(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM audit_log ORDER BY ts")
        return [dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()


def sync_pair(a: Store, b: Store) -> dict:
    """Bidirectional one-shot sync between two nodes (used by the demo)."""
    a_to_b = b.import_records(a.export_since())
    b_to_a = a.import_records(b.export_since())
    return {"a_to_b": a_to_b, "b_to_a": b_to_a}


class StoreAndForwardBuffer:
    """Holds outbound deltas while a node is offline; flushes on reconnect.
    This is what lets intake keep working with zero connectivity."""

    def __init__(self):
        self._queued: list[dict] = []

    def queue(self, delta: dict):
        self._queued.append(delta)

    def flush_into(self, peer: Store) -> dict:
        total_p = total_n = 0
        for delta in self._queued:
            res = peer.import_records(delta)
            total_p += res["persons_added"]
            total_n += res["notes_added"]
        self._queued.clear()
        return {"persons_added": total_p, "notes_added": total_n}

    def __len__(self):
        return len(self._queued)
