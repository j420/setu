"use client";

import React from "react";

export function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: "ok" | "warn" | "danger" | "accent";
}) {
  const color =
    accent === "ok"
      ? "text-ok"
      : accent === "warn"
        ? "text-warn"
        : accent === "danger"
          ? "text-danger"
          : accent === "accent"
            ? "text-accent"
            : "text-head";
  return (
    <div className="card !p-4 min-w-[140px] flex-1">
      <div className={`text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
      <div className="mt-0.5 text-xs text-muted">{label}</div>
    </div>
  );
}

export function Pill({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "ok" | "warn" | "danger" | "muted" | "accent";
}) {
  const map: Record<string, string> = {
    ok: "bg-ok/15 text-ok",
    warn: "bg-warn/15 text-warn",
    danger: "bg-danger/15 text-danger",
    accent: "bg-accent/20 text-accent",
    muted: "bg-white/5 text-muted",
  };
  return <span className={`pill ${map[tone]}`}>{children}</span>;
}

export function SectionTitle({
  icon,
  title,
  hint,
  right,
}: {
  icon: string;
  title: string;
  hint?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div>
        <h2 className="flex items-center gap-2 text-sm font-semibold text-head">
          <span>{icon}</span>
          {title}
        </h2>
        {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      </div>
      {right}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-xs text-muted">{children}</p>;
}
