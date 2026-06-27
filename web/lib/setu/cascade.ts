// The matching cascade (port of cascade.py). Mandatory ordering, two thresholds.

import { PersonRecord } from "./types";
import { THRESHOLD_HIGH, THRESHOLD_LOW, SEMANTIC_MAX_WEIGHT } from "./config";
import { candidateBlock, DEFAULT_TIME_WINDOW_HOURS } from "./blocking";
import {
  MatchScore,
  logistic,
  negativeTerms,
  positiveTerms,
  score,
} from "./fellegiSunter";
import { semanticSimilarity } from "./semantic";
import { faceRerank, FaceInfo } from "./face";

export type Disposition = "queue" | "warm" | "discard";

export interface Candidate {
  record: PersonRecord;
  base_weight: number;
  semantic_weight: number;
  face_weight: number;
  total_weight: number;
  probability: number;
  disposition: Disposition;
  explanation: string[];
  score_obj: MatchScore;
  semantic_similarity: number;
  face_info: FaceInfo;
}

function disposition(total: number): Disposition {
  if (total >= THRESHOLD_HIGH) return "queue";
  if (total < THRESHOLD_LOW) return "discard";
  return "warm";
}

const round3 = (x: number) => Math.round(x * 1000) / 1000;

function semanticBits(q: PersonRecord, c: PersonRecord): [number, number] {
  const sim = semanticSimilarity(q.free_text, c.free_text);
  const bits = round3(Math.max(0, sim) * SEMANTIC_MAX_WEIGHT);
  return [bits, sim];
}

export function scorePair(
  query: PersonRecord,
  cand: PersonRecord,
  useFace = true,
): Candidate {
  const ms = score(query, cand);
  const [semBits, sim] = semanticBits(query, cand);

  let faceInfo: FaceInfo = {
    applicable: false,
    similarity: null,
    weight: 0,
    reason: "face not run",
  };
  if (useFace) faceInfo = faceRerank(query, cand);
  const faceBits = faceInfo.weight ?? 0;

  const total = round3(ms.total_weight + semBits + faceBits);
  const prob = logistic(total);

  const expl: string[] = [];
  for (const t of positiveTerms(ms)) expl.push(`+${t.weight.toFixed(1)} bits — ${t.reason}`);
  if (semBits > 0)
    expl.push(`+${semBits.toFixed(1)} bits — free-text context overlaps (cosine ${sim.toFixed(2)})`);
  if (faceInfo.applicable) expl.push(`+${faceBits.toFixed(1)} bits — ${faceInfo.reason}`);
  else if (useFace) expl.push(`(face: ${faceInfo.reason})`);
  for (const t of negativeTerms(ms)) expl.push(`${t.weight.toFixed(1)} bits — ${t.reason}`);
  if (!ms.name_present)
    expl.push(
      "note: matched WITHOUT a name on at least one record (name-optional — reliable fields carried this match)",
    );

  return {
    record: cand,
    base_weight: ms.total_weight,
    semantic_weight: semBits,
    face_weight: faceBits,
    total_weight: total,
    probability: Math.round(prob * 10000) / 10000,
    disposition: disposition(total),
    explanation: expl,
    score_obj: ms,
    semantic_similarity: sim,
    face_info: faceInfo,
  };
}

export function searchCandidates(
  query: PersonRecord,
  pool: PersonRecord[],
  opts: {
    oppositeStream?: boolean;
    useFace?: boolean;
    limit?: number;
    windowHours?: number;
  } = {},
): Candidate[] {
  const oppositeStream = opts.oppositeStream ?? true;
  const useFace = opts.useFace ?? true;
  const limit = opts.limit ?? 10;
  const windowHours = opts.windowHours ?? DEFAULT_TIME_WINDOW_HOURS;

  const blocked = candidateBlock(query, pool, { oppositeStream, windowHours });
  const scored = blocked.map((c) => scorePair(query, c, useFace));
  const kept = scored.filter((c) => c.disposition !== "discard");
  kept.sort((a, b) => b.total_weight - a.total_weight);
  return kept.slice(0, limit);
}

export function queueCandidates(cands: Candidate[]): Candidate[] {
  return cands.filter((c) => c.disposition === "queue");
}
