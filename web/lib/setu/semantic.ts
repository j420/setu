// Free-text semantic matching (port of semantic.py).
// Runnable hashed-n-gram embedding (MOCK of a real multilingual embedder);
// the contract is text -> unit vector, similarity = cosine.

const DIM = 256;

function tokens(text: string): string[] {
  const lower = text.toLowerCase();
  const words = lower.match(/[a-zऀ-෿]+/g) ?? [];
  const grams: string[] = [];
  for (const w of words) {
    grams.push(w);
    for (let i = 0; i < w.length - 2; i++) grams.push(w.slice(i, i + 3));
  }
  return grams;
}

// FNV-1a 32-bit hash (deterministic, no deps).
function hash32(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function embed(text: string | null | undefined): number[] {
  const vec = new Array(DIM).fill(0);
  if (!text) return vec;
  for (const tok of tokens(text)) {
    const h = hash32(tok);
    const idx = h % DIM;
    const sign = (h >> 8) & 1 ? 1 : -1;
    vec[idx] += sign;
  }
  let norm = 0;
  for (const v of vec) norm += v * v;
  norm = Math.sqrt(norm);
  if (norm > 0) for (let i = 0; i < DIM; i++) vec[i] /= norm;
  return vec;
}

export function cosine(a: number[], b: number[]): number {
  let dot = 0;
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
  return dot;
}

export function semanticSimilarity(
  a: string | null | undefined,
  b: string | null | undefined,
): number {
  if (!a || !b) return 0;
  const sim = cosine(embed(a), embed(b));
  return Math.round(sim * 10000) / 10000;
}
