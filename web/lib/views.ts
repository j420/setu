// Derived views for the dashboard, computed from the live record set.

import {
  Candidate,
  PersonRecord,
  findDuplicates,
  searchCandidates,
} from "./setu";

export interface QueueItem {
  query: PersonRecord;
  candidate: PersonRecord;
  cand: Candidate;
}

export function buildQueue(persons: PersonRecord[], max = 12): QueueItem[] {
  const missing = persons.filter((r) => r.record_type === "missing" && r.status === "warm");
  const items: QueueItem[] = [];
  const seen = new Set<string>();
  for (const q of missing) {
    const cs = searchCandidates(q, persons, { limit: 1 });
    for (const c of cs) {
      if (c.disposition !== "queue") continue;
      const key = [q.person_record_id, c.record.person_record_id].sort().join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({ query: q, candidate: c.record, cand: c });
    }
  }
  items.sort((a, b) => b.cand.total_weight - a.cand.total_weight);
  return items.slice(0, max);
}

export function metrics(persons: PersonRecord[], queue: QueueItem[]) {
  const total = persons.length;
  const elderly = persons.filter((r) => r.age_band === "61-75" || r.age_band === "76+").length;
  const noName = persons.filter((r) => !r.full_name).length;
  const reunited = persons.filter((r) => r.status === "reunited" || r.status === "purged").length;
  const queuedNoName = queue.filter((q) => !q.cand.score_obj.name_present).length;
  const crossCenter = queue.filter(
    (q) => q.candidate.origin_domain !== q.query.origin_domain,
  ).length;
  return {
    total,
    pct_elderly: total ? Math.round((1000 * elderly) / total) / 10 : 0,
    pct_no_name: total ? Math.round((1000 * noName) / total) / 10 : 0,
    languages: new Set(persons.map((r) => r.language).filter(Boolean)).size,
    in_queue: queue.length,
    queued_no_name: queuedNoName,
    cross_center: crossCenter,
    reunited,
  };
}

export function hotspots(persons: PersonRecord[], top = 8) {
  const counts = new Map<string, number>();
  for (const r of persons) {
    if (!r.last_seen_zone) continue;
    counts.set(r.last_seen_zone, (counts.get(r.last_seen_zone) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([zone, cases]) => ({ zone, cases }))
    .sort((a, b) => b.cases - a.cases)
    .slice(0, top);
}

export function duplicates(persons: PersonRecord[], max = 10) {
  return findDuplicates(persons).slice(0, max);
}

export function shortId(id: string): string {
  return id.split("/").pop() ?? id;
}

export function centerOf(domain: string): string {
  return domain.replace(/\.setu$/, "");
}
