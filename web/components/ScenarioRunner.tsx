"use client";

import React, { useState } from "react";
import {
  Store,
  searchCandidates,
  generatePaScript,
  explainCandidate,
  syncPair,
} from "@/lib/setu";
import { HandoverGateError } from "@/lib/setu/store";
import { Pill, SectionTitle } from "./ui";

interface Step {
  title: string;
  detail: string;
  tone: "ok" | "warn" | "danger" | "accent" | "muted";
}

export function ScenarioRunner() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    const log: Step[] = [];
    const push = (s: Step) => {
      log.push(s);
      setSteps([...log]);
    };
    const wait = () => new Promise((r) => setTimeout(r, 550));

    const ramkund = new Store("ramkund");
    const panchavati = new Store("panchavati");

    push({
      title: "1 · Voice intake at Ramkund — NO NAME",
      detail:
        'Bhashini ASR (Maithili): “हमर सासु हेरा गेली अछि… रामकुंड लग… बिहार सँ छी।” ' +
        "Operator logs a FOUND record with the name left blank.",
      tone: "accent",
    });
    const found = ramkund.createRecord({
      record_type: "found",
      age_band: "61-75",
      sex: "F",
      home_state: "Bihar",
      language: "maithili",
      last_seen_zone: "ramkund",
      last_seen_time: new Date(Date.now() - 40 * 60000).toISOString(),
      full_name: null,
      free_text: "elderly woman found near the Ramkund ghat steps, disoriented",
      consent_pa: true,
      author: "ramkund-volunteer-07",
    });
    await wait();

    syncPair(ramkund, panchavati);
    push({
      title: "2 · Federated sync — visible at Panchavati in seconds",
      detail: `Record ${found.person_record_id.split("/").pop()} created at Ramkund is now replicated to the Panchavati node.`,
      tone: "ok",
    });
    await wait();

    const missing = panchavati.createRecord({
      record_type: "missing",
      age_band: "61-75",
      sex: "F",
      home_state: "Bihar",
      language: "maithili",
      last_seen_zone: "ramkund",
      last_seen_time: new Date(Date.now() - 50 * 60000).toISOString(),
      full_name: "सीता देवी",
      free_text: "my mother got separated near the Ramkund ghat steps",
      consent_pa: true,
      author: "panchavati-desk-02",
    });
    syncPair(ramkund, panchavati);
    push({
      title: "3 · Her son files a MISSING report at Panchavati",
      detail: "He files at Panchavati but reports she was last seen at Ramkund. Name known on the family side only.",
      tone: "accent",
    });
    await wait();

    const cands = searchCandidates(missing, panchavati.allPersons());
    const top = cands[0];
    push({
      title: "4 · Cascade returns her at the top — matched WITHOUT a name",
      detail: explainCandidate(missing, top),
      tone: "ok",
    });
    await wait();

    const script = generatePaScript({
      zone: "ramkund",
      language: "maithili",
      age_band: "61-75",
      home_state: "Bihar",
      name: "सीता देवी",
    });
    push({
      title: "5 · Maithili PA script generated for the Ramkund zone",
      detail: `${script.native_text}\n${script.announcer_latin}`,
      tone: "accent",
    });
    await wait();

    push({
      title: "6 · Human verifier confirms via a relationship question",
      detail: 'Verifier asks the son: “What is your mother’s youngest grandchild’s name?” — answer matches.',
      tone: "warn",
    });
    panchavati.confirmReunion(missing.person_record_id, found.person_record_id, {
      verifier_id: "verifier-pan-01",
      method: "relationship_question",
      passed: true,
      note: "named youngest grandchild correctly",
    });
    await wait();

    const recAfter = panchavati.getPerson(missing.person_record_id)!;
    push({
      title: "7 · Reunion recorded → records auto-purged (DPDP)",
      detail: `Status: ${recAfter.status}. Name after purge: ${recAfter.full_name ?? "null"}. Identifying content wiped; a non-identifying audit stub remains. Both parties notified.`,
      tone: "ok",
    });
    await wait();

    // 8 · gate bypass proofs
    const proofs: string[] = [];
    const tryBlock = (label: string, fn: () => void) => {
      try {
        fn();
        proofs.push(`✗ FAIL — ${label} was NOT blocked!`);
      } catch (e) {
        if (e instanceof HandoverGateError) proofs.push(`✓ blocked — ${e.message}`);
        else throw e;
      }
    };
    const a = ramkund.createRecord({ record_type: "missing", full_name: "x", age_band: "61-75" });
    const b = ramkund.createRecord({ record_type: "found", full_name: null, age_band: "61-75" });
    tryBlock("no verifier", () =>
      ramkund.confirmReunion(a.person_record_id, b.person_record_id, { verifier_id: "", method: "relationship_question", passed: true }),
    );
    tryBlock("a match score as method", () =>
      ramkund.confirmReunion(a.person_record_id, b.person_record_id, { verifier_id: "v", method: "match_score_99", passed: true }),
    );
    tryBlock("a failed check", () =>
      ramkund.confirmReunion(a.person_record_id, b.person_record_id, { verifier_id: "v", method: "safe_word", passed: false }),
    );
    push({
      title: "8 · The handover gate cannot be bypassed",
      detail: proofs.join("\n"),
      tone: "danger",
    });
    await wait();

    // 9-10 offline
    const off = ramkund.createRecord({
      record_type: "found",
      age_band: "76+",
      sex: "M",
      home_state: "Uttar Pradesh",
      language: "awadhi",
      last_seen_zone: "tapovan",
      full_name: null,
      free_text: "elderly man found near Tapovan, no name",
      author: "ramkund-volunteer-09",
    });
    push({
      title: "9 · NETWORK CUT — offline intake continues",
      detail: `Record ${off.person_record_id.split("/").pop()} created on Ramkund with zero connectivity (held in store-and-forward). Panchavati cannot see it yet: ${panchavati.getPerson(off.person_record_id) === null}.`,
      tone: "warn",
    });
    await wait();

    const res = syncPair(ramkund, panchavati);
    push({
      title: "10 · RECONNECT — buffered record syncs everywhere",
      detail: `On reconnect, ${res.a_to_b.persons_added} record(s) flushed to Panchavati. Now visible: ${panchavati.getPerson(off.person_record_id) !== null}.`,
      tone: "ok",
    });

    setRunning(false);
  }

  return (
    <div className="card">
      <SectionTitle
        icon="🎬"
        title="Guided demo — the Sita Devi reunion, end to end"
        hint="Runs the full story on a fresh two-node network: no-name voice intake → cross-center match → Maithili PA → human-gated reunion → auto-purge → offline cut & re-sync."
        right={
          <button className="btn btn-primary" onClick={run} disabled={running}>
            {running ? "Running…" : steps.length ? "Run again" : "▶ Run the demo"}
          </button>
        }
      />
      {steps.length === 0 ? (
        <p className="py-6 text-center text-xs text-muted">
          Press “Run the demo” to watch SETU reunite a no-name case across centers and survive a network cut.
        </p>
      ) : (
        <ol className="space-y-2">
          {steps.map((s, i) => (
            <li key={i} className="rounded-xl border border-line bg-ink/40 p-3">
              <div className="mb-1 flex items-center gap-2">
                <Pill tone={s.tone}>{i + 1}</Pill>
                <span className="text-sm font-medium">{s.title}</span>
              </div>
              <pre className="whitespace-pre-wrap text-xs leading-relaxed text-muted">{s.detail}</pre>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
