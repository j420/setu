"use client";

import React from "react";
import { Pill } from "./ui";

export function Header({
  online,
  pendingCount,
  onToggle,
}: {
  online: boolean;
  pendingCount: number;
  onToggle: (next: boolean) => void;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink/70 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent2 text-lg">🌉</div>
          <div>
            <h1 className="text-base font-semibold leading-tight">
              SETU <span className="text-muted">· Reunification Control Room</span>
            </h1>
            <p className="text-[11px] text-muted">
              Nashik–Trimbakeshwar Kumbh 2027 · name-optional · PA-first · human-gated · live data
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {pendingCount > 0 && <Pill tone="warn">{pendingCount} buffered offline</Pill>}
          <button
            className={`btn !py-1.5 ${online ? "!border-ok/40 text-ok" : "!border-danger/40 text-danger"}`}
            onClick={() => onToggle(!online)}
            title="Toggle connectivity to demo offline-first store-and-forward"
          >
            <span className={`h-2 w-2 rounded-full ${online ? "bg-ok" : "bg-danger"}`} />
            {online ? "Online" : "Offline"}
          </button>
        </div>
      </div>
    </header>
  );
}
