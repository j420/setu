// Deduplication (port of dedup.py): collapse the 8% duplicate reports as
// append-only link-notes, never destructive merges.

import { PersonRecord } from "./types";
import { DEDUP_THRESHOLD, SEMANTIC_MAX_WEIGHT } from "./config";
import { candidateBlock } from "./blocking";
import { positiveTerms, score } from "./fellegiSunter";
import { semanticSimilarity } from "./semantic";

export interface DuplicatePair {
  a: PersonRecord;
  b: PersonRecord;
  total_weight: number;
  explanation: string[];
}

const round3 = (x: number) => Math.round(x * 1000) / 1000;

export function findDuplicates(
  records: PersonRecord[],
  threshold = DEDUP_THRESHOLD,
): DuplicatePair[] {
  const pairs: DuplicatePair[] = [];
  const seen = new Set<string>();

  for (const rec of records) {
    const sameStream = records.filter((r) => r.record_type === rec.record_type);
    const cands = candidateBlock(rec, sameStream, { oppositeStream: false });
    for (const c of cands) {
      const key = [rec.person_record_id, c.person_record_id].sort().join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      const ms = score(rec, c);
      const sim = semanticSimilarity(rec.free_text, c.free_text);
      const semBits = round3(Math.max(0, sim) * SEMANTIC_MAX_WEIGHT);
      const total = round3(ms.total_weight + semBits);
      if (total >= threshold) {
        const expl = positiveTerms(ms).map((t) => `+${t.weight.toFixed(1)} — ${t.reason}`);
        if (semBits > 0) expl.push(`+${semBits.toFixed(1)} — free-text overlap (cosine ${sim.toFixed(2)})`);
        pairs.push({ a: rec, b: c, total_weight: total, explanation: expl });
      }
    }
  }
  pairs.sort((x, y) => y.total_weight - x.total_weight);
  return pairs;
}
