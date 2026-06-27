"use client";

import React, { useState } from "react";
import {
  AGE_BANDS,
  CENTERS,
  Candidate,
  HOME_STATES,
  LANGUAGES,
  PersonRecord,
  ZONES,
} from "@/lib/setu";
import { IntakeInput } from "@/lib/useSetu";
import { Empty, Pill, SectionTitle } from "./ui";
import { centerOf, shortId } from "@/lib/views";

const EMPTY: IntakeInput = {
  center: "ramkund",
  record_type: "missing",
  age_band: "61-75",
  sex: "F",
  home_state: "Bihar",
  language: "maithili",
  last_seen_zone: "ramkund",
  full_name: "",
  free_text: "",
  consent_match: true,
  consent_pa: true,
  photo_consented: false,
};

export function IntakeForm({
  onCreate,
}: {
  onCreate: (input: IntakeInput) => { record: PersonRecord; matches: Candidate[]; buffered: boolean };
}) {
  const [form, setForm] = useState<IntakeInput>(EMPTY);
  const [result, setResult] = useState<{ record: PersonRecord; matches: Candidate[]; buffered: boolean } | null>(null);

  function set<K extends keyof IntakeInput>(k: K, v: IntakeInput[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const input = { ...form, full_name: form.full_name?.trim() || null };
    const res = onCreate(input);
    setResult(res);
  }

  return (
    <div className="card">
      <SectionTitle
        icon="🎙️"
        title="Intake — voice-first, name-optional"
        hint="Log a missing or found person. The name field can be left blank — the cascade never depends on it. (In the field this is captured by voice via Bhashini ASR.)"
      />
      <form onSubmit={submit} className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <div>
          <label className="label">Center (node)</label>
          <select className="field" value={form.center} onChange={(e) => set("center", e.target.value)}>
            {Object.entries(CENTERS).map(([k, v]) => (
              <option key={k} value={k}>{v.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Report type</label>
          <select className="field" value={form.record_type} onChange={(e) => set("record_type", e.target.value as "missing" | "found")}>
            <option value="missing">Missing (family searching)</option>
            <option value="found">Found (someone found this person)</option>
          </select>
        </div>
        <div>
          <label className="label">Name <span className="text-muted">(optional)</span></label>
          <input className="field" placeholder="leave blank if unknown" value={form.full_name ?? ""} onChange={(e) => set("full_name", e.target.value)} />
        </div>
        <div>
          <label className="label">Age band</label>
          <select className="field" value={form.age_band} onChange={(e) => set("age_band", e.target.value)}>
            {AGE_BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Sex</label>
          <select className="field" value={form.sex} onChange={(e) => set("sex", e.target.value as "F" | "M" | "U")}>
            <option value="F">F</option><option value="M">M</option><option value="U">Unknown</option>
          </select>
        </div>
        <div>
          <label className="label">Language</label>
          <select className="field" value={form.language} onChange={(e) => set("language", e.target.value)}>
            {Object.entries(LANGUAGES).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Home state</label>
          <select className="field" value={form.home_state} onChange={(e) => set("home_state", e.target.value)}>
            {HOME_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Last seen zone</label>
          <select className="field" value={form.last_seen_zone} onChange={(e) => set("last_seen_zone", e.target.value)}>
            {ZONES.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
        <div className="col-span-2 md:col-span-3">
          <label className="label">Distinctive detail / free text</label>
          <input className="field" placeholder="e.g. green tin trunk, near the Hanuman temple" value={form.free_text ?? ""} onChange={(e) => set("free_text", e.target.value)} />
        </div>
        <label className="col-span-2 flex items-center gap-2 text-xs text-muted md:col-span-3">
          <input type="checkbox" checked={form.consent_pa} onChange={(e) => set("consent_pa", e.target.checked)} />
          Consent to be named in a PA announcement
        </label>
        <div className="col-span-2 md:col-span-3">
          <button type="submit" className="btn btn-primary w-full">Log & run the cascade</button>
        </div>
      </form>

      {result && (
        <div className="mt-4 rounded-xl border border-line bg-ink/40 p-3">
          <div className="flex items-center gap-2 text-sm">
            <Pill tone={result.buffered ? "warn" : "ok"}>
              {result.buffered ? "Buffered offline (store-and-forward)" : "Created & synced"}
            </Pill>
            <span className="text-muted">{shortId(result.record.person_record_id)} · {centerOf(result.record.origin_domain)}</span>
          </div>
          {result.buffered ? (
            <p className="mt-2 text-xs text-warn">
              No connectivity — this record is held locally and will sync (and become
              matchable everywhere) on reconnect.
            </p>
          ) : result.matches.length === 0 ? (
            <Empty>No candidates above threshold yet — kept warm and re-matched on every new record.</Empty>
          ) : (
            <div className="mt-2 space-y-2">
              <div className="text-xs text-muted">Top candidates returned by the cascade:</div>
              {result.matches.slice(0, 3).map((c, i) => (
                <div key={i} className="rounded-lg bg-panel2/50 p-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-ok">{c.total_weight.toFixed(1)} bits</span>
                    <span className="text-muted">{c.record.full_name || "no name"} · {centerOf(c.record.origin_domain)}</span>
                    <Pill tone={c.disposition === "queue" ? "ok" : "warn"}>{c.disposition}</Pill>
                  </div>
                  <ul className="mt-1 space-y-0.5 text-muted">
                    {c.explanation.slice(0, 4).map((l, j) => <li key={j}>{l}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
