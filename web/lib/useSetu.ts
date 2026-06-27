"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CENTERS,
  Candidate,
  NoteRecord,
  PersonRecord,
  RecordType,
  Store,
  makePerson,
  newId,
  nowIso,
  searchCandidates,
  DEFAULT_RETENTION_DAYS,
} from "./setu";
import { HumanAttestation } from "./setu/privacy";

// Real records entered at this node are persisted locally so the operator's
// working set survives reloads. NO synthetic/seed/random data is ever loaded —
// the store starts empty and is populated only by real intake (or, in
// production, by ingestion from kiosks/IVR/the federation API).
const STORAGE_KEY = "setu.records.v1";

interface Persisted {
  persons: PersonRecord[];
  notes: NoteRecord[];
}

function loadPersisted(store: Store) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw) as Persisted;
    store.importRecords({ persons: data.persons ?? [], notes: data.notes ?? [] });
  } catch {
    /* ignore corrupt cache */
  }
}

function savePersisted(store: Store) {
  if (typeof window === "undefined") return;
  try {
    const { persons, notes } = store.exportAll();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ persons, notes }));
  } catch {
    /* quota / serialization issues are non-fatal */
  }
}

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

export function useSetu() {
  const storeRef = useRef<Store | null>(null);
  const pendingRef = useRef<PersonRecord[]>([]);
  const [online, setOnline] = useState(true);
  const [tick, setTick] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  // Start EMPTY — no seed, no random data.
  if (storeRef.current === null) {
    storeRef.current = new Store("central_control");
  }
  const store = storeRef.current;

  // Hydrate real records from localStorage on the client (post-SSR), then
  // persist on every change.
  useEffect(() => {
    loadPersisted(store);
    setHydrated(true);
    refresh();
  }, [store, refresh]);

  useEffect(() => {
    if (hydrated) savePersisted(store);
  }, [store, hydrated, tick]);

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

  const clearAll = useCallback(() => {
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
    storeRef.current = new Store("central_control");
    pendingRef.current = [];
    refresh();
  }, [refresh]);

  return {
    store,
    persons,
    online,
    hydrated,
    pendingCount: pendingRef.current.length,
    createRecord,
    toggleOnline,
    flushPending,
    confirmReunion,
    matchesFor,
    clearAll,
    refresh,
    tick,
  };
}
