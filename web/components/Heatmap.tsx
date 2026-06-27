"use client";

import React from "react";
import { Empty, SectionTitle } from "./ui";

export function Heatmap({ data }: { data: { zone: string; cases: number }[] }) {
  const max = data.reduce((m, d) => Math.max(m, d.cases), 0) || 1;
  return (
    <div className="card">
      <SectionTitle
        icon="🗺️"
        title="Hotspot heatmap — cases by zone"
        hint="Drives predictive pre-positioning of volunteers and PA by zone × time."
      />
      {data.length === 0 ? (
        <Empty>No data.</Empty>
      ) : (
        <div className="space-y-2">
          {data.map((d) => (
            <div key={d.zone} className="flex items-center gap-3 text-xs">
              <div className="w-28 shrink-0 text-muted">{d.zone}</div>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/5">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-accent to-danger"
                  style={{ width: `${(100 * d.cases) / max}%` }}
                />
              </div>
              <div className="w-8 text-right tabular-nums">{d.cases}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
