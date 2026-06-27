// Fellegi-Sunter probabilistic record linkage (port of fellegi_sunter.py).
// Explainable per-field log2(m/u) weights; hand-implemented so every bit of
// evidence is inspectable. `u` is conditioned on having passed blocking.

import { PersonRecord } from "./types";
import { ageBandsCompatible } from "./config";
import { nameAgreement } from "./names";

export const MU: Record<string, { m: number; u: number }> = {
  age_band: { m: 0.9, u: 0.4 },
  sex: { m: 0.97, u: 0.5 },
  language: { m: 0.95, u: 0.7 },
  home_state: { m: 0.95, u: 0.65 },
  zone_exact: { m: 0.65, u: 0.15 },
  time_close: { m: 0.8, u: 0.3 },
};

export const NAME_WEIGHT_EXACT = 4.0;
export const NAME_WEIGHT_PHONETIC = 2.5;
export const NAME_WEIGHT_CONFLICT = -3.0;

const log2 = (x: number) => Math.log(x) / Math.log(2);

function agreeWeight(k: string): number {
  const p = MU[k];
  return log2(p.m / p.u);
}
function disagreeWeight(k: string): number {
  const p = MU[k];
  return log2((1 - p.m) / (1 - p.u));
}

export interface WeightTerm {
  field: string;
  agreed: boolean;
  weight: number;
  reason: string;
}

export interface MatchScore {
  total_weight: number;
  probability: number;
  terms: WeightTerm[];
  name_present: boolean;
}

export function logistic(bits: number): number {
  const x = Math.max(-60, Math.min(60, -bits / 2));
  return 1 / (1 + Math.exp(x));
}

function parseTime(s: string | null | undefined): number | null {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isNaN(t) ? null : t;
}

function timeClose(a: PersonRecord, b: PersonRecord, hours = 2): boolean | null {
  const ta = parseTime(a.last_seen_time);
  const tb = parseTime(b.last_seen_time);
  if (ta === null || tb === null) return null;
  return Math.abs(ta - tb) <= hours * 3600 * 1000;
}

const round3 = (x: number) => Math.round(x * 1000) / 1000;

export function score(a: PersonRecord, b: PersonRecord): MatchScore {
  const terms: WeightTerm[] = [];
  const add = (
    key: string,
    agreed: boolean,
    labelAgree: string,
    labelDisagree: string,
  ) => {
    const w = agreed ? agreeWeight(key) : disagreeWeight(key);
    terms.push({
      field: key,
      agreed,
      weight: round3(w),
      reason: agreed ? labelAgree : labelDisagree,
    });
  };

  const ageOk = ageBandsCompatible(a.age_band, b.age_band);
  add("age_band", ageOk,
    `age band ${a.age_band}≈${b.age_band}`,
    `age bands differ (${a.age_band} vs ${b.age_band})`);

  if ((a.sex === "F" || a.sex === "M") && (b.sex === "F" || b.sex === "M")) {
    add("sex", a.sex === b.sex, `both ${a.sex}`, `sex differs (${a.sex} vs ${b.sex})`);
  }
  if (a.language && b.language) {
    add("language", a.language === b.language,
      `both speak ${a.language}`, `language differs (${a.language} vs ${b.language})`);
  }
  if (a.home_state && b.home_state) {
    add("home_state", a.home_state === b.home_state,
      `both from ${a.home_state}`, "home state differs");
  }
  if (a.last_seen_zone && b.last_seen_zone && a.last_seen_zone === b.last_seen_zone) {
    add("zone_exact", true, `same zone (${a.last_seen_zone})`, "");
  }
  const tc = timeClose(a, b);
  if (tc !== null) {
    add("time_close", tc, "last seen within ~2h", "last seen hours apart");
  }

  const ni = nameAgreement(a.full_name, b.full_name);
  if (ni.present) {
    if (ni.exact)
      terms.push({ field: "name", agreed: true, weight: NAME_WEIGHT_EXACT,
        reason: `names match exactly (${a.full_name}≈${b.full_name})` });
    else if (ni.phonetic)
      terms.push({ field: "name", agreed: true, weight: NAME_WEIGHT_PHONETIC,
        reason: `names phonetically equal (${ni.key_a})` });
    else
      terms.push({ field: "name", agreed: false, weight: NAME_WEIGHT_CONFLICT,
        reason: `names differ (${a.full_name} vs ${b.full_name})` });
  }

  const total = round3(terms.reduce((s, t) => s + t.weight, 0));
  return {
    total_weight: total,
    probability: Math.round(logistic(total) * 10000) / 10000,
    terms,
    name_present: ni.present,
  };
}

export function positiveTerms(ms: MatchScore): WeightTerm[] {
  return ms.terms.filter((t) => t.weight > 0).sort((x, y) => y.weight - x.weight);
}
export function negativeTerms(ms: MatchScore): WeightTerm[] {
  return ms.terms.filter((t) => t.weight < 0).sort((x, y) => x.weight - y.weight);
}
