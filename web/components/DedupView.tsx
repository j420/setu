"use client";

import React from "react";
import { DuplicatePair } from "@/lib/setu";
import { Empty, Pill, SectionTitle } from "./ui";
import { centerOf, shortId } from "@/lib/views";

export function DedupView({ pairs }: { pairs: DuplicatePair[] }) {
  return (
    <div className="card">
      <SectionTitle
        icon="🔁"
        title="Dedup view — same person, two centers"
        hint="The 8% duplicate problem. Flagged as append-only link-notes, never destructively merged."
        right={<Pill tone="accent">{pairs.length}</Pill>}
      />
      {pairs.length === 0 ? (
        <Empty>No duplicates detected in the current set.</Empty>
      ) : (
        <div className="space-y-2">
          {pairs.map((p, i) => (
            <div key={i} className="flex items-center justify-between rounded-xl border border-line bg-ink/40 p-3 text-xs">
              <div>
                <div className="font-medium">{p.a.full_name || "no name"}</div>
                <div className="text-muted">
                  {centerOf(p.a.origin_domain)} ↔ {centerOf(p.b.origin_domain)} · {p.a.last_seen_zone}
                </div>
                <div className="text-muted">
                  {shortId(p.a.person_record_id)} · {shortId(p.b.person_record_id)}
                </div>
              </div>
              <Pill tone="ok">{p.total_weight.toFixed(1)} bits</Pill>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
