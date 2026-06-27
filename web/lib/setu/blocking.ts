// Blocking (port of blocking.py). Reliable fields only — NEVER name.

import { PersonRecord } from "./types";
import { ageBandsCompatible, zonesAdjacent } from "./config";

export const DEFAULT_TIME_WINDOW_HOURS = 12;

function parseTime(s: string | null | undefined): number | null {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isNaN(t) ? null : t;
}

function timeCompatible(a: PersonRecord, b: PersonRecord, windowHours: number): boolean {
  const ta = parseTime(a.last_seen_time);
  const tb = parseTime(b.last_seen_time);
  if (ta === null || tb === null) return true; // missing time never excludes
  return Math.abs(ta - tb) <= windowHours * 3600 * 1000;
}

export function blocksWith(
  a: PersonRecord,
  b: PersonRecord,
  windowHours = DEFAULT_TIME_WINDOW_HOURS,
): boolean {
  if (!ageBandsCompatible(a.age_band, b.age_band)) return false;
  if (!zonesAdjacent(a.last_seen_zone, b.last_seen_zone)) return false;
  if (!timeCompatible(a, b, windowHours)) return false;
  const sameLang = !!a.language && a.language === b.language;
  const sameState = !!a.home_state && a.home_state === b.home_state;
  if (!sameLang && !sameState) return false;
  return true;
}

export function candidateBlock(
  query: PersonRecord,
  pool: PersonRecord[],
  opts: { oppositeStream?: boolean; windowHours?: number } = {},
): PersonRecord[] {
  const oppositeStream = opts.oppositeStream ?? true;
  const windowHours = opts.windowHours ?? DEFAULT_TIME_WINDOW_HOURS;
  const out: PersonRecord[] = [];
  for (const cand of pool) {
    if (cand.person_record_id === query.person_record_id) continue;
    if (oppositeStream && cand.record_type === query.record_type) continue;
    if (!oppositeStream && cand.record_type !== query.record_type) continue;
    if (!cand.consent_match) continue;
    if (blocksWith(query, cand, windowHours)) out.push(cand);
  }
  return out;
}
