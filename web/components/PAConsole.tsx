"use client";

import React, { useState } from "react";
import { AGE_BANDS, HOME_STATES, LANGUAGES, ZONES, generatePaScript, PAScript } from "@/lib/setu";
import { Pill, SectionTitle } from "./ui";

export function PAConsole() {
  const [zone, setZone] = useState("ramkund");
  const [language, setLanguage] = useState("maithili");
  const [age, setAge] = useState("61-75");
  const [state, setState] = useState("Bihar");
  const [name, setName] = useState("");
  const [free, setFree] = useState("");
  const [script, setScript] = useState<PAScript | null>(null);
  const [fired, setFired] = useState(false);

  function gen() {
    setScript(
      generatePaScript({
        zone,
        language,
        age_band: age,
        home_state: state,
        name: name.trim() || null,
        free_text: free.trim() || null,
      }),
    );
    setFired(false);
  }

  return (
    <div className="card">
      <SectionTitle
        icon="📣"
        title="PA console — zone-targeted, own-language"
        hint="Loudspeaker announcements are the highest-leverage reunification lever. Templated scripts fire directly; free-text scripts require human approval."
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <div>
          <label className="label">Zone</label>
          <select className="field" value={zone} onChange={(e) => setZone(e.target.value)}>
            {ZONES.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Language</label>
          <select className="field" value={language} onChange={(e) => setLanguage(e.target.value)}>
            {Object.entries(LANGUAGES).map(([k, v]) => <option key={k} value={k}>{v.name} · {v.native}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Age band</label>
          <select className="field" value={age} onChange={(e) => setAge(e.target.value)}>
            {AGE_BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Home state</label>
          <select className="field" value={state} onChange={(e) => setState(e.target.value)}>
            {HOME_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Name (optional)</label>
          <input className="field" placeholder="blank = no-name script" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Free text (needs approval)</label>
          <input className="field" placeholder="optional extra" value={free} onChange={(e) => setFree(e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary mt-3 w-full" onClick={gen}>Generate PA script</button>

      {script && (
        <div className="mt-3 space-y-2 rounded-xl border border-line bg-ink/50 p-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Pill tone="accent">{script.pa_locale}</Pill>
            <Pill tone={script.templated ? "ok" : "warn"}>
              {script.templated ? "templated" : "free-text"}
            </Pill>
            {script.requires_human_approval && <Pill tone="warn">needs human approval</Pill>}
          </div>
          <div className="text-base leading-relaxed">{script.native_text}</div>
          <div className="text-xs text-muted">{script.announcer_latin}</div>
          <div className="text-[11px] text-muted">
            🔊 Bhashini TTS (mock): mock-audio://{script.pa_locale}/announcement.wav
          </div>
          <button className="btn !py-1.5" onClick={() => setFired(true)}>
            {fired
              ? "✓ Queued to loudspeakers"
              : script.requires_human_approval
                ? "Approve & fire (supervisor)"
                : "Fire to loudspeakers"}
          </button>
        </div>
      )}
    </div>
  );
}
