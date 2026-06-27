"use client";

import React, { useState } from "react";
import { QueueItem, shortId, centerOf } from "@/lib/views";
import { Empty, Pill, SectionTitle } from "./ui";
import { VerifyDialog } from "./VerifyDialog";
import { HumanAttestation } from "@/lib/setu/privacy";

export function MatchQueue({
  queue,
  onConfirm,
}: {
  queue: QueueItem[];
  onConfirm: (caseId: string, linkedId: string, att: HumanAttestation) => void;
}) {
  const [active, setActive] = useState<QueueItem | null>(null);

  return (
    <div className="card">
      <SectionTitle
        icon="🧭"
        title="Match queue — agent proposes, human disposes"
        hint="High-confidence pairs the cascade surfaced. No match score can confirm a handover; a human verifies the family bond first."
        right={<Pill tone="accent">{queue.length} pending</Pill>}
      />
      {queue.length === 0 ? (
        <Empty>No high-confidence pairs right now. File an intake to populate the queue.</Empty>
      ) : (
        <div className="space-y-3">
          {queue.map((item, i) => (
            <div key={i} className="rounded-xl border border-line bg-ink/40 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-semibold tabular-nums text-ok">
                    {item.cand.total_weight.toFixed(1)} bits
                  </span>
                  <span className="text-muted">·</span>
                  <span className="text-muted">
                    {Math.round(item.cand.probability * 100)}% match prob.
                  </span>
                  {!item.cand.score_obj.name_present && <Pill tone="danger">no-name match</Pill>}
                  {item.candidate.origin_domain !== item.query.origin_domain && (
                    <Pill tone="accent">cross-center</Pill>
                  )}
                </div>
                <button className="btn btn-primary !py-1.5" onClick={() => setActive(item)}>
                  Verify &amp; reunite →
                </button>
              </div>

              <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg bg-panel2/50 p-2">
                  <div className="text-muted">Missing · {centerOf(item.query.origin_domain)}</div>
                  <div className="font-medium">{item.query.full_name || "— no name —"}</div>
                  <div className="text-muted">
                    {item.query.age_band} · {item.query.language} · {item.query.last_seen_zone}
                  </div>
                </div>
                <div className="rounded-lg bg-panel2/50 p-2">
                  <div className="text-muted">Found · {centerOf(item.candidate.origin_domain)}</div>
                  <div className="font-medium">{item.candidate.full_name || "— no name —"}</div>
                  <div className="text-muted">
                    {item.candidate.age_band} · {item.candidate.language} ·{" "}
                    {item.candidate.last_seen_zone}
                  </div>
                </div>
              </div>

              <details className="mt-2 text-xs">
                <summary className="cursor-pointer text-accent">
                  Why this match? (grounded in match weights)
                </summary>
                <ul className="mt-2 space-y-1 text-muted">
                  {item.cand.explanation.map((line, j) => (
                    <li key={j}>{line}</li>
                  ))}
                </ul>
              </details>
            </div>
          ))}
        </div>
      )}

      {active && (
        <VerifyDialog
          query={active.query}
          candidate={active.candidate}
          cand={active.cand}
          onClose={() => setActive(null)}
          onConfirm={(att) => {
            onConfirm(active.query.person_record_id, active.candidate.person_record_id, att);
          }}
        />
      )}
    </div>
  );
}
