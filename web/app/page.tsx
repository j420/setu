"use client";

import React, { useMemo, useState } from "react";
import { useSetu } from "@/lib/useSetu";
import { buildQueue, metrics, hotspots, duplicates } from "@/lib/views";
import { Header } from "@/components/Header";
import { Stat } from "@/components/ui";
import { MatchQueue } from "@/components/MatchQueue";
import { IntakeForm } from "@/components/IntakeForm";
import { PAConsole } from "@/components/PAConsole";
import { DedupView } from "@/components/DedupView";
import { Heatmap } from "@/components/Heatmap";

type Tab = "control" | "intake" | "pa";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "control", label: "Control Room", icon: "🧭" },
  { id: "intake", label: "Intake", icon: "🎙️" },
  { id: "pa", label: "PA Console", icon: "📣" },
];

export default function Page() {
  const setu = useSetu();
  const [tab, setTab] = useState<Tab>("intake");

  const queue = useMemo(() => buildQueue(setu.persons), [setu.persons]);
  const m = useMemo(() => metrics(setu.persons, queue), [setu.persons, queue]);
  const hot = useMemo(() => hotspots(setu.persons), [setu.persons]);
  const dupes = useMemo(() => duplicates(setu.persons), [setu.persons]);

  return (
    <div className="min-h-screen">
      <Header online={setu.online} pendingCount={setu.pendingCount} onToggle={setu.toggleOnline} />

      <main className="mx-auto max-w-7xl px-5 py-6">
        {/* metrics strip */}
        <div className="mb-5 flex flex-wrap gap-3">
          <Stat label="Open records" value={m.total} />
          <Stat label="% elderly (61+)" value={`${m.pct_elderly}%`} accent="accent" />
          <Stat label="% with no name" value={`${m.pct_no_name}%`} accent="warn" />
          <Stat label="Languages" value={m.languages} />
          <Stat label="In match queue" value={m.in_queue} accent="ok" />
          <Stat label="Queued without a name" value={m.queued_no_name} accent="danger" />
          <Stat label="Cross-center matches" value={m.cross_center} accent="accent" />
          <Stat label="Reunited (purged)" value={m.reunited} accent="ok" />
        </div>

        {/* tabs + data controls */}
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <nav className="flex flex-wrap gap-1 rounded-2xl border border-line bg-panel/60 p-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`tab ${tab === t.id ? "tab-active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                <span className="mr-1.5">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2 text-xs text-muted">
            <span>Live data · {setu.persons.length} record(s) on this node</span>
            {setu.persons.length > 0 && (
              <button
                className="btn !py-1 !px-2 text-danger"
                onClick={() => {
                  if (confirm("Clear all records on this node? This cannot be undone.")) setu.clearAll();
                }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {setu.hydrated && setu.persons.length === 0 && tab !== "intake" && (
          <div className="card mb-5 text-center">
            <p className="text-sm">No records yet.</p>
            <p className="mt-1 text-xs text-muted">
              This is live operational data, not a demo — the queue, dedup, and
              heatmap fill in as real missing/found reports are logged.
            </p>
            <button className="btn btn-primary mt-3" onClick={() => setTab("intake")}>
              🎙️ Log the first intake
            </button>
          </div>
        )}

        {tab === "control" && (
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <MatchQueue queue={queue} onConfirm={setu.confirmReunion} />
            </div>
            <div className="space-y-5">
              <Heatmap data={hot} />
              <DedupView pairs={dupes} />
            </div>
          </div>
        )}

        {tab === "intake" && (
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <IntakeForm onCreate={setu.createRecord} />
            </div>
            <div>
              <MatchQueue queue={queue} onConfirm={setu.confirmReunion} />
            </div>
          </div>
        )}

        {tab === "pa" && (
          <div className="grid gap-5 lg:grid-cols-2">
            <PAConsole />
            <Heatmap data={hot} />
          </div>
        )}

        <footer className="mt-10 border-t border-line pt-4 text-center text-xs text-muted">
          Two inviolable rules, structurally enforced: (1) no automated handover — a human
          always verifies the family bond; (2) no standing biometric database — face
          embeddings are transient and never persisted. Records shown are real intake
          on this node, processed live.
        </footer>
      </main>
    </div>
  );
}
