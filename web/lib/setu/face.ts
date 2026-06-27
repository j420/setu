// Face re-rank (port of face.py): LAST, OPTIONAL, CONSENTED, gated, capped low.
// Transient embeddings, never persisted, never a candidate generator.

import { PersonRecord } from "./types";
import { FACE_MAX_WEIGHT_CONTRIBUTION } from "./config";

// MOCK ArcFace embedding from the photo ref (deterministic; computed on demand).
function transientEmbedding(ref: string): number[] {
  const v: number[] = [];
  let h = 0x811c9dc5;
  for (let i = 0; i < 64; i++) {
    for (let j = 0; j < ref.length; j++) {
      h ^= ref.charCodeAt(j) + i;
      h = Math.imul(h, 0x01000193);
    }
    v.push(((h >>> 0) % 256) / 255);
  }
  return v;
}

function cos(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return na && nb ? dot / (Math.sqrt(na) * Math.sqrt(nb)) : 0;
}

export interface FaceInfo {
  applicable: boolean;
  similarity: number | null;
  weight: number;
  reason: string;
}

export function faceRerank(a: PersonRecord, b: PersonRecord): FaceInfo {
  if (
    !(a.photo_ref && a.photo_consented && b.photo_ref && b.photo_consented)
  ) {
    return {
      applicable: false,
      similarity: null,
      weight: 0,
      reason: "no consented photo on one or both records — face skipped",
    };
  }
  const sim = cos(transientEmbedding(a.photo_ref), transientEmbedding(b.photo_ref));
  // embeddings go out of scope here — nothing persisted.
  const weight =
    Math.round(Math.max(0, sim) * FACE_MAX_WEIGHT_CONTRIBUTION * 1000) / 1000;
  return {
    applicable: true,
    similarity: Math.round(sim * 10000) / 10000,
    weight,
    reason: `consented photo similarity ${sim.toFixed(2)} (capped at ${FACE_MAX_WEIGHT_CONTRIBUTION} bits, never decisive)`,
  };
}
