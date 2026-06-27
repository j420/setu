"""FastMCP server — the agent's tool surface.

Tools are few, composable, and outcome-oriented, annotated read-only vs
state-changing. The handover gate is honoured: no tool can confirm a reunion
without a human attestation, and `fire_pa_announcement` requires human approval
for non-templated text.

  search_candidates            [read-only]      ranked, explained shortlist
  create_person_record         [state-changing] federated PFIF record, status warm
  fire_pa_announcement         [state-changing] queue targeted PA (human-approve free text)
  enqueue_for_human_verification [state-changing] cannot itself confirm
  record_reunion_and_purge     [state-changing] only after human attestation; auto-purges
  scan_band                    [state-changing] resolve a pre-indexed band
  get_case_status              [read-only]

Face comparison is an INTERNAL gated sub-step of search_candidates, never a tool.

The tool *logic* lives in plain functions on `SetuService` so the demo and tests
can call them without a running MCP transport. `build_mcp()` wraps them in a
FastMCP server when the library is available.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict

from . import agent, pa, proactive
from .config import CENTERS, DEFAULT_RETENTION_DAYS
from .matching import cascade
from .privacy import HumanAttestation, confirm_reunion
from .schema import (
    NOTE_PA,
    RECORD_FOUND,
    RECORD_MISSING,
    STATUS_QUEUED,
    PersonRecord,
    make_note,
    new_id,
)
from .store import Store


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class SetuService:
    """Holds one center's store and exposes the tool functions."""

    def __init__(self, store: Store):
        self.store = store

    # -- read-only ----------------------------------------------------------
    def search_candidates(self, query_record_id: str, use_face: bool = True) -> dict:
        """[read-only] Run the full cascade for an existing record and return a
        ranked, explained shortlist. Face is an internal gated sub-step here."""
        query = self.store.get_person(query_record_id)
        if query is None:
            return {"error": f"no record {query_record_id}"}
        cands = cascade.search_candidates(
            query, self.store.all_persons(), use_face=use_face)
        return {
            "query_record_id": query_record_id,
            "matched_without_name_possible": query.full_name is None,
            "candidates": [
                {
                    "candidate_id": c.record.person_record_id,
                    "total_weight_bits": c.total_weight,
                    "probability": c.probability,
                    "disposition": c.disposition,
                    "explanation": c.explanation,
                    "name_present": c.score_obj.name_present,
                    "face": c.face_info,
                }
                for c in cands
            ],
        }

    def get_case_status(self, case_id: str) -> dict:
        """[read-only] Current status + the full append-only note history."""
        rec = self.store.get_person(case_id)
        if rec is None:
            return {"error": f"no record {case_id}"}
        notes = self.store.notes_for(case_id)
        return {
            "case_id": case_id,
            "status": rec.status,
            "record_type": rec.record_type,
            "has_name": rec.full_name is not None,
            "language": rec.language,
            "last_seen_zone": rec.last_seen_zone,
            "notes": [{"type": n.note_type, "text": n.text, "ts": n.source_date}
                      for n in notes],
        }

    # -- state-changing -----------------------------------------------------
    def create_person_record(self, intake: dict) -> dict:
        """[state-changing] Create a federated PFIF record (default status warm)
        and trigger an immediate match run (the agent proposes)."""
        domain = self.store.domain
        retention = intake.get("retention_days", DEFAULT_RETENTION_DAYS)
        expiry = (dt.datetime.now(dt.timezone.utc)
                  + dt.timedelta(days=retention)).isoformat()
        rec = PersonRecord(
            person_record_id=new_id(domain),
            source_date=_now_iso(),
            record_type=intake.get("record_type", RECORD_MISSING),
            origin_domain=domain,
            age_band=intake.get("age_band", ""),
            sex=intake.get("sex", "U"),
            home_state=intake.get("home_state", ""),
            language=intake.get("language", ""),
            last_seen_zone=intake.get("last_seen_zone", ""),
            last_seen_time=intake.get("last_seen_time", ""),
            full_name=intake.get("full_name"),
            physical_description=intake.get("physical_description"),
            free_text=intake.get("free_text"),
            photo_ref=intake.get("photo_ref"),
            photo_consented=bool(intake.get("photo_consented", False)),
            consent_match=bool(intake.get("consent_match", True)),
            consent_pa=bool(intake.get("consent_pa", False)),
            is_minor=bool(intake.get("is_minor", False)),
            expiry_date=expiry,
            author=intake.get("author", "intake"),
        )
        self.store.put_person(rec)
        self.store.append_audit(rec.author, "create_record", rec.person_record_id,
                                f'{{"consent_match": {str(rec.consent_match).lower()}}}')
        run = agent.run_match(self.store, rec)
        return {
            "person_record_id": rec.person_record_id,
            "status": rec.status,
            "queued_candidates": [asdict(q) for q in run.queued],
        }

    def fire_pa_announcement(
        self, *, zone: str, language: str, age_band: str = "",
        home_state: str = "", name: str | None = None,
        free_text: str | None = None, approved_by: str | None = None,
        case_id: str | None = None,
    ) -> dict:
        """[state-changing] Queue a targeted PA script. Templated scripts may
        fire directly; non-templated (free_text) scripts REQUIRE `approved_by`
        (human approval) or they are held."""
        script = pa.generate_pa_script(
            zone=zone, language=language, age_band=age_band,
            home_state=home_state, name=name, free_text=free_text)
        if script.requires_human_approval and not approved_by:
            return {
                "fired": False,
                "held_for_approval": True,
                "reason": "non-templated PA text requires human approval",
                "preview": script.native_text,
            }
        if case_id:
            self.store.add_note(make_note(
                case_id, NOTE_PA, self.store.domain,
                author=approved_by or "pa-console",
                text=f"PA fired in {script.language} for zone {script.zone}",
                payload={"native_text": script.native_text,
                         "locale": script.pa_locale, "templated": script.templated}))
        self.store.append_audit(approved_by or "pa-console", "pa_fired",
                                case_id or zone, f'{{"locale": "{script.pa_locale}"}}')
        return {"fired": True, "script": asdict(script)}

    def enqueue_for_human_verification(self, query_id: str, candidate_id: str) -> dict:
        """[state-changing] Move a proposed pair into the human queue. This
        CANNOT confirm anything — it only flags both records as queued."""
        for pid in (query_id, candidate_id):
            self.store.update_status(pid, STATUS_QUEUED)
        return {"queued": [query_id, candidate_id],
                "note": "awaiting human verification — no handover is automated"}

    def record_reunion_and_purge(
        self, *, case_id: str, linked_id: str, verifier_id: str,
        method: str, passed: bool, note: str = "",
    ) -> dict:
        """[state-changing] THE HANDOVER GATE. Confirms a reunion ONLY with a
        passing human attestation, then auto-purges. Raises if attestation is
        missing/invalid/failed (see privacy.confirm_reunion)."""
        attestation = HumanAttestation(
            verifier_id=verifier_id, method=method, passed=passed, note=note)
        return confirm_reunion(self.store, case_id, linked_id, attestation)

    def scan_band(self, token_id: str) -> dict:
        """[state-changing] Resolve a pre-indexed proactive band to its
        group-contact pointer + meeting point."""
        return proactive.scan_band(token_id)


def build_mcp(service: SetuService):
    """Wrap a SetuService in a FastMCP server. Importing fastmcp is optional so
    the rest of SETU runs without it."""
    try:
        from fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "fastmcp not installed — `pip install fastmcp`. The SetuService "
            "functions work without it.") from e

    mcp = FastMCP("setu")

    @mcp.tool(annotations={"readOnlyHint": True})
    def search_candidates(query_record_id: str, use_face: bool = True) -> dict:
        """Ranked, explained shortlist for a record (face is an internal sub-step)."""
        return service.search_candidates(query_record_id, use_face)

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_case_status(case_id: str) -> dict:
        """Current status + append-only note history for a case."""
        return service.get_case_status(case_id)

    @mcp.tool(annotations={"readOnlyHint": False})
    def create_person_record(intake: dict) -> dict:
        """Create a federated PFIF record (status warm) and run matching."""
        return service.create_person_record(intake)

    @mcp.tool(annotations={"readOnlyHint": False})
    def fire_pa_announcement(zone: str, language: str, age_band: str = "",
                             home_state: str = "", name: str | None = None,
                             free_text: str | None = None,
                             approved_by: str | None = None,
                             case_id: str | None = None) -> dict:
        """Queue a targeted PA script; free text requires human approval."""
        return service.fire_pa_announcement(
            zone=zone, language=language, age_band=age_band, home_state=home_state,
            name=name, free_text=free_text, approved_by=approved_by, case_id=case_id)

    @mcp.tool(annotations={"readOnlyHint": False})
    def enqueue_for_human_verification(query_id: str, candidate_id: str) -> dict:
        """Flag a proposed pair for human verification (cannot confirm)."""
        return service.enqueue_for_human_verification(query_id, candidate_id)

    @mcp.tool(annotations={"readOnlyHint": False})
    def record_reunion_and_purge(case_id: str, linked_id: str, verifier_id: str,
                                 method: str, passed: bool, note: str = "") -> dict:
        """Confirm a reunion ONLY with passing human attestation; then purge."""
        return service.record_reunion_and_purge(
            case_id=case_id, linked_id=linked_id, verifier_id=verifier_id,
            method=method, passed=passed, note=note)

    @mcp.tool(annotations={"readOnlyHint": False})
    def scan_band(token_id: str) -> dict:
        """Resolve a pre-indexed proactive band to a group-contact pointer."""
        return service.scan_band(token_id)

    return mcp
