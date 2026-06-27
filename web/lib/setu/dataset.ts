// Synthetic dataset generator (port of data/generate_dataset.py). SYNTHETIC DATA,
// reproducing the real distributions (58% elderly, ~15% no-name, 10 languages,
// 8% duplicates). Deterministic under a fixed seed. Truth labels are kept OUT of
// the matching path so metrics can be measured honestly.

import { CENTERS, ZONES, ADJACENCY } from "./config";
import { PersonRecord, RecordType, makePerson } from "./types";

export interface Dataset {
  records: PersonRecord[];
  truth: Record<string, string>; // person_record_id -> truth group
  duplicateIds: Set<string>;
}

// Mulberry32 seeded PRNG — deterministic across node + browser.
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NAMES: Record<string, string[]> = {
  maithili: ["सीता देवी", "राम बाबू", "सुनीता", "गंगा देवी", "मोहन झा"],
  hindi: ["रमेश", "गीता देवी", "श्याम लाल", "कमला", "सुरेश कुमार"],
  bhojpuri: ["राजू", "फूलमती", "बिरजू", "सरिता", "हरि"],
  awadhi: ["रामखेलावन", "सावित्री", "बैजनाथ", "कौशल्या"],
  bengali: ["অমিত", "রিনা", "সুবল", "মমতা দেবী"],
  gujarati: ["રમેશભાઈ", "જયા બેન", "મનુ", "કોકિલા"],
  marathi: ["विठ्ठल", "लक्ष्मीबाई", "साईनाथ", "मंगल"],
  kannada: ["ರಮೇಶ", "ಗೌರಮ್ಮ", "ಶಿವಣ್ಣ", "ಲಕ್ಷ್ಮಿ"],
  telugu: ["వెంకట్", "లక్ష్మమ్మ", "రాజు", "సరళ"],
  tamil: ["முருகன்", "கமலா", "செல்வம்", "மீனா"],
};

const LANG_STATE: Record<string, string> = {
  maithili: "Bihar", bhojpuri: "Bihar", awadhi: "Uttar Pradesh",
  hindi: "Madhya Pradesh", bengali: "West Bengal", gujarati: "Gujarat",
  marathi: "Maharashtra", kannada: "Karnataka", telugu: "Telangana",
  tamil: "Tamil Nadu",
};

const DESCRIPTORS = [
  "wearing a green saree", "white kurta and dhoti", "carrying a cloth bag",
  "red shawl, walking with a stick", "blue blouse", "barefoot, orange scarf",
  "spectacles, grey hair", "yellow sari with gold border",
];

const DETAILS = [
  "green tin trunk", "red walking stick", "yellow cloth bundle",
  "Hanuman temple side", "near the blue water tank", "by the marigold stalls",
  "carrying a brass pot", "torn jute bag", "saffron headscarf",
  "near the south gate", "by the tea stall", "missing one slipper",
];

export function generate(
  n = 2500,
  seed = 42,
  truePairFraction = 0.25,
): Dataset {
  const r = rng(seed);
  const pick = <T>(arr: T[]): T => arr[Math.floor(r() * arr.length)];
  const centers = Object.keys(CENTERS);
  const langs = Object.keys(NAMES);
  const ds: Dataset = { records: [], truth: {}, duplicateIds: new Set() };

  const windowStart = Date.now() - 36 * 3600 * 1000;
  const WINDOW_MS = 36 * 3600 * 1000;
  const randTime = () => new Date(windowStart + Math.floor(r() * WINDOW_MS)).toISOString();

  const ageBand = (): string => {
    const x = r();
    if (x < 0.115) return pick(["0-12", "13-17"]);
    if (x < 0.115 + 0.58) return pick(["61-75", "76+"]);
    return pick(["18-30", "31-45", "46-60"]);
  };

  let groupSeq = 0;
  let produced = 0;

  const mk = (
    record_type: RecordType,
    lang: string,
    ab: string,
    zone: string,
    seenTime: string,
    withName: boolean,
    photo: boolean,
  ): PersonRecord =>
    makePerson({
      record_type,
      origin_domain: "",
      age_band: ab,
      sex: pick(["F", "M"]) as "F" | "M",
      home_state: LANG_STATE[lang],
      language: lang,
      last_seen_zone: zone,
      last_seen_time: seenTime,
      full_name: withName ? pick(NAMES[lang]) : null,
      physical_description: pick(DESCRIPTORS),
      photo_ref: photo ? `photo://synthetic/${Math.floor(r() * 9000 + 1000)}.jpg` : null,
      photo_consented: photo,
      consent_match: true,
      consent_pa: r() < 0.6,
      is_minor: ab === "0-12" || ab === "13-17",
      author: "synthetic-seed",
    });

  const assign = (centerKey: string, rec: PersonRecord, group: string): PersonRecord => {
    const domain = CENTERS[centerKey].domain;
    rec.origin_domain = domain;
    rec.person_record_id = `${domain}/${(groupSeq * 7 + ds.records.length)
      .toString(36)
      .padStart(8, "0")}`;
    ds.truth[rec.person_record_id] = group;
    return rec;
  };

  const nPairs = Math.floor((n * truePairFraction) / 2);
  for (let i = 0; i < nPairs; i++) {
    groupSeq++;
    const group = `g${groupSeq}`;
    const lang = pick(langs);
    const ab = ageBand();
    const zone = pick(ZONES);
    const foundZone = r() < 0.7 ? zone : pick(ADJACENCY[zone] ?? [zone]);
    const noName = r() < 0.15;
    const photo = r() < 0.3;

    const tMissing = randTime();
    const tFound = new Date(
      Date.parse(tMissing) + (5 + Math.floor(r() * 85)) * 60 * 1000,
    ).toISOString();
    const detail = pick(DETAILS);

    const missing = mk("missing", lang, ab, zone, tMissing, !(noName && r() < 0.5), false);
    const found = mk("found", lang, ab, foundZone, tFound, !(noName && r() < 0.5), photo);
    if (missing.full_name && found.full_name) {
      const shared = pick(NAMES[lang]);
      missing.full_name = shared;
      found.full_name = shared;
    }
    missing.free_text = `separated near ${zone}, ${detail}`;
    found.free_text = `found near ${foundZone}, ${detail}`;
    const cm = pick(centers);
    let cf = pick(centers);
    while (cf === cm) cf = pick(centers);
    ds.records.push(assign(cm, missing, group));
    ds.records.push(assign(cf, found, group));
    produced += 2;
  }

  // 8% duplicates of existing found records
  const foundRecords = ds.records.filter((r2) => r2.record_type === "found");
  const nDupes = Math.floor(n * 0.08);
  for (let i = 0; i < Math.min(nDupes, foundRecords.length); i++) {
    const orig = pick(foundRecords);
    const group = ds.truth[orig.person_record_id];
    let dupeCenter = pick(centers);
    while (CENTERS[dupeCenter].domain === orig.origin_domain) dupeCenter = pick(centers);
    const dupe = mk(
      "found",
      orig.language,
      orig.age_band,
      orig.last_seen_zone,
      orig.last_seen_time,
      orig.full_name != null,
      false,
    );
    dupe.full_name = orig.full_name ?? null;
    dupe.home_state = orig.home_state;
    dupe.free_text = orig.free_text ?? null;
    assign(dupeCenter, dupe, group);
    ds.records.push(dupe);
    ds.duplicateIds.add(dupe.person_record_id);
    produced++;
  }

  // singletons (long tail / noise)
  while (produced < n) {
    groupSeq++;
    const group = `s${groupSeq}`;
    const lang = pick(langs);
    const ab = ageBand();
    const zone = pick(ZONES);
    const rtype: RecordType = r() < 0.5 ? "missing" : "found";
    const rec = mk(rtype, lang, ab, zone, randTime(), r() > 0.15, r() < 0.1);
    rec.free_text = `last seen near the ${zone} ghat steps`;
    ds.records.push(assign(pick(centers), rec, group));
    produced++;
  }

  return ds;
}

export function datasetStats(ds: Dataset) {
  const recs = ds.records;
  const total = recs.length;
  const elderly = recs.filter((r) => r.age_band === "61-75" || r.age_band === "76+").length;
  const children = recs.filter((r) => r.age_band === "0-12" || r.age_band === "13-17").length;
  const noName = recs.filter((r) => !r.full_name).length;
  const missing = recs.filter((r) => r.record_type === "missing").length;
  return {
    total,
    pct_elderly: Math.round((1000 * elderly) / total) / 10,
    pct_children: Math.round((1000 * children) / total) / 10,
    pct_no_name: Math.round((1000 * noName) / total) / 10,
    missing_stream: missing,
    found_stream: total - missing,
    languages: new Set(recs.map((r) => r.language)).size,
  };
}
