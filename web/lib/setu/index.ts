export * from "./types";
export * from "./config";
export * from "./names";
export * from "./semantic";
export * from "./fellegiSunter";
export * from "./blocking";
export * from "./face";
export * from "./cascade";
export * from "./dedup";
export * from "./pa";
export * from "./privacy";
export * from "./store";
export * from "./dataset";

import { Candidate } from "./cascade";
import { PersonRecord } from "./types";

// Deterministic, weight-grounded explanation (port of agent.explain_candidate).
export function explainCandidate(_query: PersonRecord, cand: Candidate): string {
  const head =
    `Candidate ${cand.record.person_record_id} — ${cand.total_weight.toFixed(1)} bits of ` +
    `evidence (~${Math.round(cand.probability * 100)}% match probability), ` +
    `disposition: ${cand.disposition.toUpperCase()}.`;
  const body = cand.explanation.map((l) => `  • ${l}`).join("\n");
  return `${head}\n${body}`;
}
