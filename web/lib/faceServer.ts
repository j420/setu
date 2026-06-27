// SERVER-ONLY image/face comparison. Runs in a Vercel Node serverless function.
//
// Honesty + the inviolable rules:
//  * This compares the ACTUAL pixels of two photos and returns a similarity in
//    [0,1]. It is a real, server-side computation — not a string hash.
//  * It is a PERCEPTUAL/face-shaped stand-in (intensity-embedding cosine + dHash).
//    The PRODUCTION SWAP is ArcFace/InsightFace embeddings; the request/response
//    contract here is identical, so swapping the model is a drop-in.
//  * NOTHING is persisted: images and descriptors live only for the duration of
//    one request and are then garbage-collected. There is no database, no file
//    write, no searchable index (RULE 2: no standing biometric database).
//  * The score is an AID only — it can never confirm a handover (RULE 1).
//
// This module imports pure-JS decoders (jpeg-js / pngjs) and must only be used
// from server code (route handlers), never bundled into the client.

import jpeg from "jpeg-js";
import { PNG } from "pngjs";

const GRID = 64; // intensity descriptor is GRID x GRID grayscale

interface Decoded {
  width: number;
  height: number;
  rgba: Uint8Array | Buffer;
}

function decodeDataUrl(dataUrl: string): Decoded {
  const m = /^data:(image\/[a-zA-Z.+-]+);base64,(.*)$/s.exec(dataUrl);
  if (!m) throw new Error("expected a base64 image data URL");
  const mime = m[1].toLowerCase();
  const buf = Buffer.from(m[2], "base64");
  if (mime.includes("png")) {
    const png = PNG.sync.read(buf);
    return { width: png.width, height: png.height, rgba: png.data };
  }
  if (mime.includes("jpeg") || mime.includes("jpg")) {
    const img = jpeg.decode(buf, { useTArray: true, maxMemoryUsageInMB: 256 });
    return { width: img.width, height: img.height, rgba: img.data };
  }
  throw new Error(`unsupported image type: ${mime} (use JPEG or PNG)`);
}

// Nearest-neighbour downsample to a w x h grayscale float array (0..255).
function toGray(d: Decoded, w: number, h: number): number[] {
  const out = new Array(w * h);
  for (let y = 0; y < h; y++) {
    const sy = Math.min(d.height - 1, Math.floor((y / h) * d.height));
    for (let x = 0; x < w; x++) {
      const sx = Math.min(d.width - 1, Math.floor((x / w) * d.width));
      const i = (sy * d.width + sx) * 4;
      const r = d.rgba[i], g = d.rgba[i + 1], b = d.rgba[i + 2];
      out[y * w + x] = 0.299 * r + 0.587 * g + 0.114 * b;
    }
  }
  return out;
}

// L2-normalised, mean-subtracted intensity vector (lighting-robust embedding).
function intensityVector(gray: number[]): number[] {
  const mean = gray.reduce((a, b) => a + b, 0) / gray.length;
  const v = gray.map((x) => x - mean);
  let norm = Math.sqrt(v.reduce((a, b) => a + b * b, 0));
  if (norm === 0) norm = 1;
  return v.map((x) => x / norm);
}

function cosine(a: number[], b: number[]): number {
  let dot = 0;
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
  return dot; // both unit vectors
}

// dHash: 9x8 grayscale -> 8x8 "is pixel brighter than its right neighbour" bits.
function dHash(d: Decoded): boolean[] {
  const g = toGray(d, 9, 8);
  const bits: boolean[] = [];
  for (let y = 0; y < 8; y++)
    for (let x = 0; x < 8; x++) bits.push(g[y * 9 + x] > g[y * 9 + x + 1]);
  return bits;
}

function hammingSimilarity(a: boolean[], b: boolean[]): number {
  let same = 0;
  for (let i = 0; i < a.length; i++) if (a[i] === b[i]) same++;
  return same / a.length;
}

export interface FaceCompareResult {
  similarity: number; // 0..1, blended
  intensity_cosine: number; // 0..1
  hash_similarity: number; // 0..1
  method: string;
  persisted: false;
  note: string;
}

export function compareImages(dataUrlA: string, dataUrlB: string): FaceCompareResult {
  const a = decodeDataUrl(dataUrlA);
  const b = decodeDataUrl(dataUrlB);

  const cos = cosine(
    intensityVector(toGray(a, GRID, GRID)),
    intensityVector(toGray(b, GRID, GRID)),
  );
  const cos01 = Math.max(0, Math.min(1, (cos + 1) / 2));
  const hash = hammingSimilarity(dHash(a), dHash(b));

  const similarity = Math.round((0.5 * cos01 + 0.5 * hash) * 10000) / 10000;

  // descriptors fall out of scope here — nothing is stored.
  return {
    similarity,
    intensity_cosine: Math.round(cos01 * 10000) / 10000,
    hash_similarity: Math.round(hash * 10000) / 10000,
    method: "perceptual-stand-in (production swap: ArcFace/InsightFace, same contract)",
    persisted: false,
    note: "advisory only — a human must verify the family bond; a score can never confirm a handover",
  };
}
