// Canonical configuration (TypeScript port of setu/config.py).

export interface CenterInfo {
  name: string;
  domain: string;
}

export const CENTERS: Record<string, CenterInfo> = {
  adgaon: { name: "Adgaon", domain: "adgaon.setu" },
  rajur_bahula: { name: "Rajur Bahula", domain: "rajurbahula.setu" },
  panchavati: { name: "Panchavati", domain: "panchavati.setu" },
  ramkund: { name: "Ramkund", domain: "ramkund.setu" },
  bharat_bharati: { name: "Bharat Bharati Control Room", domain: "bharatbharati.setu" },
  trimbakeshwar: { name: "Trimbakeshwar", domain: "trimbakeshwar.setu" },
  central_control: { name: "Central Control Room", domain: "central.setu" },
  nashik_road: { name: "Nashik Road", domain: "nashikroad.setu" },
  sadhugram: { name: "Sadhugram", domain: "sadhugram.setu" },
  police_control: { name: "Police Main Control Room", domain: "police.setu" },
};

export const ZONES: string[] = [
  "ramkund", "panchavati", "tapovan", "sadhugram", "trimbakeshwar",
  "adgaon", "rajur_bahula", "nashik_road", "gangapur", "kalaram",
];

export const ADJACENCY: Record<string, string[]> = {
  ramkund: ["panchavati", "kalaram", "gangapur"],
  panchavati: ["ramkund", "kalaram", "tapovan"],
  kalaram: ["ramkund", "panchavati"],
  tapovan: ["panchavati", "sadhugram"],
  sadhugram: ["tapovan", "adgaon"],
  adgaon: ["sadhugram", "nashik_road"],
  nashik_road: ["adgaon", "gangapur"],
  gangapur: ["ramkund", "nashik_road", "rajur_bahula"],
  rajur_bahula: ["gangapur", "trimbakeshwar"],
  trimbakeshwar: ["rajur_bahula"],
};

export function zonesAdjacent(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  return (ADJACENCY[a] ?? []).includes(b) || (ADJACENCY[b] ?? []).includes(a);
}

export interface LanguageInfo {
  name: string;
  native: string;
  pa_locale: string;
}

export const LANGUAGES: Record<string, LanguageInfo> = {
  hindi: { name: "Hindi", native: "हिन्दी", pa_locale: "hi-IN" },
  bengali: { name: "Bengali", native: "বাংলা", pa_locale: "bn-IN" },
  kannada: { name: "Kannada", native: "ಕನ್ನಡ", pa_locale: "kn-IN" },
  maithili: { name: "Maithili", native: "मैथिली", pa_locale: "mai-IN" },
  gujarati: { name: "Gujarati", native: "ગુજરાતી", pa_locale: "gu-IN" },
  telugu: { name: "Telugu", native: "తెలుగు", pa_locale: "te-IN" },
  bhojpuri: { name: "Bhojpuri", native: "भोजपुरी", pa_locale: "bho-IN" },
  awadhi: { name: "Awadhi", native: "अवधी", pa_locale: "awa-IN" },
  tamil: { name: "Tamil", native: "தமிழ்", pa_locale: "ta-IN" },
  marathi: { name: "Marathi", native: "मराठी", pa_locale: "mr-IN" },
};

export const AGE_BANDS = ["0-12", "13-17", "18-30", "31-45", "46-60", "61-75", "76+"];
export const CHILD_BANDS = new Set(["0-12", "13-17"]);
export const ELDERLY_BANDS = new Set(["61-75", "76+"]);

const BAND_INDEX: Record<string, number> = Object.fromEntries(
  AGE_BANDS.map((b, i) => [b, i]),
);

export function ageBandsCompatible(a: string, b: string, slack = 1): boolean {
  if (!(a in BAND_INDEX) || !(b in BAND_INDEX)) return false;
  return Math.abs(BAND_INDEX[a] - BAND_INDEX[b]) <= slack;
}

export const HOME_STATES = [
  "Bihar", "West Bengal", "Karnataka", "Uttar Pradesh", "Gujarat",
  "Telangana", "Jharkhand", "Tamil Nadu", "Maharashtra", "Madhya Pradesh",
  "Rajasthan", "Odisha", "Assam", "Punjab", "Andhra Pradesh",
];

export const THRESHOLD_HIGH = 6.0;
export const THRESHOLD_LOW = 0.0;
export const DEDUP_THRESHOLD = 9.0;
export const DEFAULT_RETENTION_DAYS = 30;
export const FACE_MAX_WEIGHT_CONTRIBUTION = 1.5;
export const SEMANTIC_MAX_WEIGHT = 2.0;
