"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  CENTERS,
  Candidate,
  PersonRecord,
  RecordType,
  Store,
  generate,
  makePerson,
  newId,
  nowIso,
  searchCandidates,
  DEFAULT_RETENTION_DAYS,
} from "./setu";
import { HumanAttestation } from "./setu/privacy";

export interface IntakeInput {
  center: string;
  record_type: RecordType;
  age_band: string;
  sex: "F" | "M" | "U";
  home_state: string;
  language: string;
  last_seen_zone: string;
  full_name?: string | null;
  free_text?: string | null;
  photo_ref?: string | null;
  photo_consented?: boolean;
  consent_match?: boolean;
  consent_pa?: boolean;
  is_minor?: boolean;
  author?: string;
}

function buildRecord(input: IntakeInput): PersonRecord {
  const domain = CENTERS[input.center]?.domain ?? CENTERS.central_control.domain;
  const retentionMs = DEFAULT_RETENTION_DAYS * 24 * 3600 * 1000;
  return makePerson({
    record_type: input.record_type,
    origin_domain: domain,
    person_record_id: newId(domain),
    source_date: nowIso(),
    age_band: input.age_band,
    sex: input.sex,
    home_state: input.home_state,
    language: input.language,
    last_seen_zone: input.last_seen_zone,
    last_seen_time: nowIso(),
    full_name: input.full_name ?? null,
    free_text: input.free_text ?? null,
    photo_ref: input.photo_ref ?? null,
    photo_consented: input.photo_consented ?? false,
    consent_match: input.consent_match ?? true,
    consent_pa: input.consent_pa ?? false,
    is_minor: input.is_minor ?? false,
    expiry_date: new Date(Date.now() + retentionMs).toISOString(),
    author: input.author ?? `${input.center}-operator`,
  });
}

export function useSetu(seedCount = 400) {
  const storeRef = useRef<Store | null>(null);
  const pendingRef = useRef<PersonRecord[]>([]);
  const [online, setOnline] = useState(true);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  if (storeRef.current === null) {
    const store = new Store("central_control");
    const ds = generate(seedCount, 7);
    for (const rec of ds.records) store.putPerson(rec);
    storeRef.current = store;
  }
  const store = storeRef.current;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const persons = useMemo(() => store.allPersons(), [store, tick]);

  const createRecord = useCallback(
    (input: IntakeInput): { record: PersonRecord; matches: Candidate[]; buffered: boolean } => {
      const rec = buildRecord(input);
      if (online) {
        store.putPerson(rec);
        store.appendAudit(rec.author, "create_record", rec.person_record_id, {
          consent_match: rec.consent_match,
        });
        const matches = searchCandidates(rec, store.allPersons(), { limit: 6 });
        refresh();
        return { record: rec, matches, buffered: false };
      }
      // offline: store-and-forward
      pendingRef.current.push(rec);
      refresh();
      return { record: rec, matches: [], buffered: true };
    },
    [online, store, refresh],
  );

  const flushPending = useCallback(() => {
    const flushed = pendingRef.current.length;
    for (const rec of pendingRef.current) {
      store.putPerson(rec);
      store.appendAudit(rec.author, "create_record_synced", rec.person_record_id, {});
    }
    pendingRef.current = [];
    refresh();
    return flushed;
  }, [store, refresh]);

  const toggleOnline = useCallback(
    (next: boolean) => {
      setOnline(next);
      if (next) flushPending();
    },
    [flushPending],
  );

  const confirmReunion = useCallback(
    (caseId: string, linkedId: string, att: HumanAttestation) => {
      const res = store.confirmReunion(caseId, linkedId, att);
      refresh();
      return res;
    },
    [store, refresh],
  );

  const matchesFor = useCallback(
    (rec: PersonRecord) => searchCandidates(rec, store.allPersons(), { limit: 6 }),
    [store],
  );

  return {
    store,
    persons,
    online,
    pendingCount: pendingRef.current.length,
    createRecord,
    toggleOnline,
    flushPending,
    confirmReunion,
    matchesFor,
    refresh,
    tick,
  };
}
