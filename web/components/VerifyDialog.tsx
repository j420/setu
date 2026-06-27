"use client";

import React, { useState } from "react";
import { Candidate, PersonRecord } from "@/lib/setu";
import { HumanAttestation, VALID_VERIFICATION_METHODS } from "@/lib/setu/privacy";
import { Pill } from "./ui";
import { shortId } from "@/lib/views";

export function VerifyDialog({
  query,
  candidate,
  cand,
  onClose,
  onConfirm,
}: {
  query: PersonRecord;
  candidate: PersonRecord;
  cand: Candidate;
  onClose: () => void;
  onConfirm: (att: HumanAttestation) => { reunited: string[] } | void;
}) {
  const [method, setMethod] = useState("relationship_question");
  const [verifier, setVerifier] = useState("verifier-01");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const methods = [...VALID_VERIFICATION_METHODS];

  function attempt(passed: boolean) {
    setError(null);
    try {
      onConfirm({ verifier_id: verifier, method, passed, note });
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function attemptBypass() {
    // demonstrate the gate: a score is not a valid method
    setError(null);
    try {
      onConfirm({ verifier_id: verifier, method: "match_score_0.99", passed: true });
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="card w-full max-w-lg">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold">Human verification — the handover gate</h3>
          <button className="text-muted hover:text-white" onClick={onClose}>
            ✕
          </button>
        </div>

        {done ? (
          <div className="space-y-3">
            <Pill tone="ok">Reunion confirmed</Pill>
            <p className="text-sm text-muted">
              Both records were marked reunited and their identifying content was
              auto-purged (DPDP). A non-identifying audit stub remains.
            </p>
            <button className="btn btn-primary w-full" onClick={onClose}>
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="mb-3 rounded-xl border border-line bg-ink/50 p-3 text-xs">
              <div className="flex justify-between">
                <span className="text-muted">Missing report</span>
                <span className="text-muted">Found record</span>
              </div>
              <div className="mt-1 flex justify-between font-medium">
                <span>{query.full_name || "no name"} · {shortId(query.person_record_id)}</span>
                <span>{candidate.full_name || "no name"} · {shortId(candidate.person_record_id)}</span>
              </div>
              <div className="mt-2 text-muted">
                {cand.total_weight.toFixed(1)} bits of evidence — but a score can
                never confirm a handover. A human must verify the family bond.
              </div>
            </div>

            <div className="rounded-xl border border-warn/30 bg-warn/5 p-3 text-xs text-warn">
              Ask a question only the real family could answer, e.g.
              <span className="font-medium"> “What is the name of her youngest grandchild?”</span>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <label className="label">Verifier ID</label>
                <input className="field" value={verifier} onChange={(e) => setVerifier(e.target.value)} />
              </div>
              <div>
                <label className="label">Method</label>
                <select className="field" value={method} onChange={(e) => setMethod(e.target.value)}>
                  {methods.map((m) => (
                    <option key={m} value={m}>
                      {m.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="mt-3">
              <label className="label">Note (what was asked / shown)</label>
              <input className="field" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. named youngest grandchild correctly" />
            </div>

            {error && (
              <div className="mt-3 rounded-xl border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
                🔒 {error}
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <button className="btn btn-primary" onClick={() => attempt(true)}>
                ✓ Family bond verified — confirm reunion
              </button>
              <button className="btn" onClick={() => attempt(false)}>
                ✗ Check failed
              </button>
              <button className="btn !border-danger/40 text-danger" onClick={attemptBypass}>
                Try to bypass with the score
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
