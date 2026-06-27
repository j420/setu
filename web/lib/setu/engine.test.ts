import { describe, it, expect } from "vitest";
import {
  blocksWith,
  searchCandidates,
  score,
  generatePaScript,
  findDuplicates,
  generate,
  datasetStats,
  Store,
  syncPair,
  HandoverGateError,
  logistic,
  semanticSimilarity,
  phoneticKey,
  transliterate,
  faceRerank,
  FACE_MAX_WEIGHT_CONTRIBUTION,
  THRESHOLD_HIGH,
  LANGUAGES,
} from "./index";
import { PersonRecord, makePerson } from "./types";

function mk(over: Partial<PersonRecord> & { record_type: "missing" | "found" }): PersonRecord {
  return makePerson({
    origin_domain: "ramkund.setu",
    age_band: "61-75",
    sex: "F",
    home_state: "Bihar",
    language: "maithili",
    last_seen_zone: "ramkund",
    last_seen_time: new Date(Date.now() - 40 * 60000).toISOString(),
    full_name: null,
    ...over,
  });
}

describe("blocking", () => {
  it("never uses the name", () => {
    const a = mk({ record_type: "missing", full_name: "सीता देवी" });
    const b = mk({ record_type: "found", full_name: null });
    const c = mk({ record_type: "found", full_name: "totally different" });
    expect(blocksWith(a, b)).toBe(true);
    expect(blocksWith(a, c)).toBe(true);
  });
  it("rejects incompatible demographics", () => {
    const a = mk({ record_type: "missing" });
    expect(blocksWith(a, mk({ record_type: "found", age_band: "0-12" }))).toBe(false);
    expect(blocksWith(a, mk({ record_type: "found", last_seen_zone: "trimbakeshwar" }))).toBe(false);
    expect(
      blocksWith(a, mk({ record_type: "found", language: "tamil", home_state: "Tamil Nadu" })),
    ).toBe(false);
  });
});

describe("no-name matching (the load-bearing claim)", () => {
  it("returns the no-name found record at the top", () => {
    const found = mk({
      record_type: "found",
      full_name: null,
      free_text: "elderly woman found near Ramkund steps, green trunk",
    });
    const son = mk({
      record_type: "missing",
      full_name: "सीता देवी",
      free_text: "mother separated near Ramkund, green trunk",
    });
    const cands = searchCandidates(son, [found]);
    expect(cands.length).toBeGreaterThan(0);
    expect(cands[0].record.person_record_id).toBe(found.person_record_id);
    expect(cands[0].disposition).toBe("queue");
    expect(cands[0].score_obj.name_present).toBe(false);
  });
});

describe("name is signal, not gate", () => {
  it("matching name > absent > conflicting", () => {
    const q = mk({ record_type: "missing", full_name: "सीता देवी" });
    const base = { record_type: "found" as const, last_seen_zone: "ramkund" };
    const same = score(q, mk({ ...base, full_name: "सीता देवी" })).total_weight;
    const none = score(q, mk({ ...base, full_name: null })).total_weight;
    const conflict = score(q, mk({ ...base, full_name: "Ramesh Kumar" })).total_weight;
    expect(same).toBeGreaterThan(none);
    expect(none).toBeGreaterThan(conflict);
  });
});

describe("face gate", () => {
  it("is never sufficient alone and capped", () => {
    const a = mk({ record_type: "missing", age_band: "18-30", sex: "M", photo_ref: "x.jpg", photo_consented: true });
    const b = mk({ record_type: "found", age_band: "46-60", photo_ref: "x.jpg", photo_consented: true });
    const fr = faceRerank(a, b);
    expect(fr.applicable).toBe(true);
    expect(fr.weight).toBeLessThanOrEqual(FACE_MAX_WEIGHT_CONTRIBUTION);
    expect(fr.weight).toBeLessThan(THRESHOLD_HIGH);
  });
  it("is skipped without consent", () => {
    const fr = faceRerank(
      mk({ record_type: "missing", photo_ref: "a.jpg", photo_consented: false }),
      mk({ record_type: "found", photo_ref: "b.jpg", photo_consented: true }),
    );
    expect(fr.applicable).toBe(false);
    expect(fr.weight).toBe(0);
  });
});

describe("handover gate (INVIOLABLE)", () => {
  function setup() {
    const store = new Store("panchavati");
    const a = store.createRecord({ record_type: "missing", full_name: "सीता देवी", age_band: "61-75" });
    const b = store.createRecord({ record_type: "found", full_name: null, age_band: "61-75" });
    return { store, a: a.person_record_id, b: b.person_record_id };
  }
  it("requires a verifier", () => {
    const { store, a, b } = setup();
    expect(() => store.confirmReunion(a, b, { verifier_id: "", method: "relationship_question", passed: true })).toThrow(HandoverGateError);
  });
  it("rejects a score as a method", () => {
    const { store, a, b } = setup();
    expect(() => store.confirmReunion(a, b, { verifier_id: "v", method: "match_score_0.99", passed: true })).toThrow(HandoverGateError);
  });
  it("rejects a failed check", () => {
    const { store, a, b } = setup();
    expect(() => store.confirmReunion(a, b, { verifier_id: "v", method: "safe_word", passed: false })).toThrow(HandoverGateError);
  });
  it("confirms + purges with a valid attestation", () => {
    const { store, a, b } = setup();
    const res = store.confirmReunion(a, b, { verifier_id: "v7", method: "relationship_question", passed: true });
    expect(res.reunited.sort()).toEqual([a, b].sort());
    for (const id of [a, b]) {
      const rec = store.getPerson(id)!;
      expect(rec.status).toBe("purged");
      expect(rec.full_name).toBeNull();
    }
    const actions = store.audit.map((e) => e.action);
    expect(actions).toContain("reunion_confirmed");
    expect(actions).toContain("auto_purge");
  });
});

describe("federation / sync", () => {
  it("record at A is visible at B after sync, idempotently", () => {
    const a = new Store("ramkund");
    const b = new Store("panchavati");
    const rec = a.createRecord({ record_type: "found", full_name: null, age_band: "61-75" });
    expect(b.getPerson(rec.person_record_id)).toBeNull();
    const first = syncPair(a, b);
    expect(first.a_to_b.persons_added).toBeGreaterThanOrEqual(1);
    expect(b.getPerson(rec.person_record_id)).not.toBeNull();
    const second = syncPair(a, b);
    expect(second.a_to_b.persons_added).toBe(0);
  });
});

describe("PA generation", () => {
  it("uses the no-name template when no name", () => {
    const named = generatePaScript({ zone: "ramkund", language: "maithili", age_band: "61-75", home_state: "Bihar", name: "सीता देवी" });
    const noname = generatePaScript({ zone: "ramkund", language: "maithili", age_band: "61-75", home_state: "Bihar", name: null });
    expect(named.native_text).toContain("सीता देवी");
    expect(noname.native_text).not.toContain("सीता देवी");
    expect(named.pa_locale).toBe("mai-IN");
    expect(named.requires_human_approval).toBe(false);
  });
  it("free text requires human approval", () => {
    const s = generatePaScript({ zone: "ramkund", language: "hindi", free_text: "urgent" });
    expect(s.requires_human_approval).toBe(true);
    expect(s.templated).toBe(false);
  });
  it("has a template for every language", () => {
    for (const lang of Object.keys(LANGUAGES)) {
      expect(generatePaScript({ zone: "ramkund", language: lang }).native_text).toBeTruthy();
    }
  });
});

describe("edge cases", () => {
  it("empty pool returns nothing", () => {
    expect(searchCandidates(mk({ record_type: "missing", full_name: "x" }), [])).toEqual([]);
  });
  it("blank records do not crash and do not block", () => {
    const a = makePerson({ record_type: "missing", origin_domain: "ramkund.setu" });
    const b = makePerson({ record_type: "found", origin_domain: "panchavati.setu" });
    expect(blocksWith(a, b)).toBe(false);
    expect(searchCandidates(a, [b])).toEqual([]);
    expect(typeof score(a, b).total_weight).toBe("number");
  });
  it("unknown language/zone handled", () => {
    const q = mk({ record_type: "missing", language: "klingon", last_seen_zone: "atlantis" });
    const c = mk({ record_type: "found", language: "klingon", last_seen_zone: "atlantis" });
    expect(Array.isArray(searchCandidates(q, [c]))).toBe(true);
    expect(generatePaScript({ zone: "atlantis", language: "klingon" }).native_text).toBeTruthy();
  });
  it("malformed timestamps do not crash", () => {
    const a = mk({ record_type: "missing", last_seen_time: "not-a-date", full_name: "x" });
    const b = mk({ record_type: "found", last_seen_time: "", full_name: null });
    expect(typeof blocksWith(a, b)).toBe("boolean");
    expect(typeof score(a, b).total_weight).toBe("number");
  });
  it("logistic is numerically stable", () => {
    expect(logistic(-1e6)).toBeGreaterThanOrEqual(0);
    expect(logistic(1e6)).toBeLessThanOrEqual(1);
    expect(Math.abs(logistic(0) - 0.5)).toBeLessThan(1e-9);
  });
  it("very long + mixed-script free text", () => {
    const t = "green trunk near Ramkund ".repeat(500) + "हरी पेटी रामकुंड";
    const sim = semanticSimilarity(t, t);
    expect(sim).toBeGreaterThan(0.99);
  });
  it("phonetic key handles empty/symbols", () => {
    expect(phoneticKey("")).toBe("");
    expect(phoneticKey("123 !!!")).toBe("");
    expect(phoneticKey("Sita")).toBe(phoneticKey("Seeta"));
    expect(transliterate("सीता")).toBe(transliterate("सीता"));
  });
  it("self-match excluded", () => {
    const rec = mk({ record_type: "missing", full_name: "x" });
    expect(searchCandidates(rec, [rec])).toEqual([]);
  });
});

describe("dataset distributions + dedup", () => {
  it("reproduces the real distributions deterministically", () => {
    const ds = generate(2500, 42);
    const s = datasetStats(ds);
    expect(s.total).toBe(2500);
    expect(s.languages).toBe(10);
    expect(s.pct_elderly).toBeGreaterThan(50);
    expect(s.pct_no_name).toBeGreaterThan(8);
    // determinism
    expect(datasetStats(generate(2500, 42)).pct_elderly).toBe(s.pct_elderly);
  });
  it("recall@5 on answerable records is high", () => {
    const ds = generate(1200, 7);
    const byGroup: Record<string, PersonRecord[]> = {};
    for (const r of ds.records) (byGroup[ds.truth[r.person_record_id]] ??= []).push(r);
    const missing = ds.records.filter((r) => r.record_type === "missing");
    const answerable = missing.filter((r) =>
      byGroup[ds.truth[r.person_record_id]].some(
        (o) => o.record_type === "found" && o.person_record_id !== r.person_record_id,
      ),
    );
    const sample = answerable.slice(0, 120);
    let recall = 0;
    for (const q of sample) {
      const g = ds.truth[q.person_record_id];
      const cs = searchCandidates(q, ds.records, { limit: 5 });
      if (cs.some((c) => ds.truth[c.record.person_record_id] === g)) recall++;
    }
    expect(recall / sample.length).toBeGreaterThan(0.8);
  });
  it("finds duplicates with reasonable precision", () => {
    const ds = generate(1200, 7);
    const pairs = findDuplicates(ds.records);
    expect(pairs.length).toBeGreaterThan(0);
    const truePairs = pairs.filter(
      (p) => ds.truth[p.a.person_record_id] === ds.truth[p.b.person_record_id],
    );
    expect(truePairs.length / pairs.length).toBeGreaterThan(0.4);
  });
});
