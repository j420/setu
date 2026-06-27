# 🌉 SETU — name-optional, PA-first reunification for Kumbh Mela 2027

> *Setu* = "bridge". A missing-person reunification system for the
> Nashik–Trimbakeshwar Simhastha Kumbh 2027, built for the Claude Impact Lab
> Mumbai hackathon.

80M+ pilgrims; thousands separated daily — **58% of them elderly**, often
non-literate and not speaking the local language. Today's ~10 lost-and-found
centers have **no cross-search**: a person found at Center A is invisible to a
family searching at Center B. SETU closes that gap — reactively and proactively —
while never automating a handover and never building a biometric dragnet.

---

## What the real data proves (and how SETU answers it)

| Reality in the data | SETU design response |
|---|---|
| 58% elderly, 11.5% children | Voice-first intake; finer elderly age bands; design for non-literate elders |
| 15% of cases have **no name** | **Name-optional** matching — blocking & scoring never depend on a name |
| Physical descriptions unreliable | `physical_description` **quarantined** as low-trust, never a strong signal |
| 10 languages, even split | 10-language PA scripts + Bhashini ASR/TTS contract |
| 8% **duplicate** reports | Same scorer in dedup mode → append-only link-notes |
| PA loudspeakers reunite the most | **PA-first**: targeted, own-language scripts are the operational heart |
| Reunions need a human bond check | **Inviolable handover gate** — no score can confirm a reunion |

> At Prayagraj 2025 the manual loudspeaker camp reunited **19,274** people while
> facial recognition had **no audited reunifications**. SETU augments the
> loudspeaker; it does not try to replace the human.

---

## Two inviolable rules (structurally enforced)

1. **Never automate a handover.** `record_reunion_and_purge` / `confirm_reunion`
   *require* a passing `HumanAttestation` (verifier id + a real check such as a
   relationship question or safe-word). A match score is **not** a valid
   verification method and there is no code path around the gate. See
   `setu/privacy.py` and `tests/test_handover_gate.py`.
2. **Never build a standing biometric database.** Face embeddings are computed
   on demand from *consented* photos, held transiently for one 1-to-few
   comparison, and discarded. No CCTV scan, no mass enrolment, no searchable
   face index. See `setu/matching/face.py`.

---

## The matching cascade (the brain — `setu/matching/`)

Mandatory ordering; each step is explainable:

1. **Block** on reliable fields only — age band + zone *adjacency* + time window
   + language/home-state. **Never blocks on name.** (`blocking.py`)
2. **Score** candidate pairs with **Fellegi-Sunter** probabilistic linkage —
   per-field `log2(m/u)` weights in bits, summed. Hand-implemented for full
   transparency; **Splink** is the production swap. (`fellegi_sunter.py`)
3. **Name signal — only if present.** Transliterate (AI4Bharat IndicXlit
   contract) + an Indic phonetic key; the name **raises or lowers** the score,
   never gates it. (`names.py`)
4. **Free-text semantic** match via embeddings + cosine (pgvector/HNSW
   contract). (`semantic.py`)
5. **Face re-rank — last, optional, consented, capped low.** Never a candidate
   generator, never decisive alone. (`face.py`)
6. **Two thresholds** — high → human queue; low → discard; between → keep
   **warm** and re-match on every new record. Same scorer runs in **dedup**
   mode. (`cascade.py`, `dedup.py`)

The `m`/`u` priors are deliberately conditioned on *having passed blocking*: in a
crowd of elderly Bihari Maithili pilgrims "both speak Maithili" is weak evidence,
so the real discriminators are exact zone, exact time, name and distinctive
free-text. This is what keeps precision honest instead of rewarding correlated
demographics twice.

---

## Architecture at a glance

```
voice / kiosk / mobile / IVR            ← interfaces (multilingual, name-optional)
        │
        ▼
  FastMCP tool surface  (setu/mcp_server.py)   ← agent PROPOSES; humans DISPOSE
   search_candidates · create_person_record · fire_pa_announcement
   enqueue_for_human_verification · record_reunion_and_purge · scan_band ·
   get_case_status                         (face = internal gated sub-step)
        │
        ▼
  matching cascade ─┬─ blocking ─ Fellegi-Sunter ─ names ─ semantic ─ face
        │           └─ dedup (8% problem)
        ▼
  PFIF append-only store (setu/store.py, SQLite edge nodes)
        │   CRDT latest-source_date-wins · store-and-forward offline sync
        ▼
  privacy/audit (setu/privacy.py): consent · immutable logs · DPDP auto-purge
                                   · handover gate · hardened minor path
```

Federation: every center is an edge node holding a full replica. A record made
at Center A is visible at Center B in seconds online, or via store-and-forward
when offline — reconciling idempotently on reconnect.

---

## Run it (no setup, no keys, stdlib only)

```bash
# 1) the full end-to-end demo: the Sita Devi reunion + offline re-sync + metrics
python -m demo.run_demo

# 2) the control-room dashboard  →  http://localhost:8000
python -m dashboard.app

# 3) the tests (cascade + handover gate + sync + dedup/PA)
pip install -r requirements-dev.txt
python -m pytest

# 4) inspect the synthetic dataset distributions
python -m data.generate_dataset -n 2500
```

### The demo scenario (`demo/run_demo.py`)

> *Sita Devi, ~68, Maithili-speaking, from Bihar, last seen Ramkund ~40 min ago*
> is logged **by voice with no name** at the Ramkund node → instantly visible at
> Panchavati where her son files → the cascade returns her at the top with a
> plain-language, **weight-grounded** explanation → a Maithili PA script is
> generated for the Ramkund zone → a human verifier confirms via a relationship
> question → reunion recorded → records **auto-purged** → both notified. Then
> the network is cut to show offline intake and re-sync.

It also prints three proofs that the handover gate cannot be bypassed.

---

## Honest metrics (measured against ground truth, not asserted)

On the 2,500-case synthetic dataset (`python -m demo.run_demo`):

- **recall@5 ≈ 94%** — the true found-partner is in the top-5 shortlist the
  verifier reviews.
- **top-1 rank ≈ 67%** — true partner ranked #1 of all candidates
  (≈ 68% for named queries, lower for no-name — harder, by design).
- **a large majority of correct matches are cross-center** — exactly the gap the
  manual centers cannot close today.
- **dedup** surfaces duplicate pairs as reviewable link-notes (never destructive
  merges).

No-name cases in a dense same-demographic crowd inherently surface more
candidates — which is *why* the human gate is inviolable. We report this
honestly rather than hide it behind an inflated precision number.

---

## What is real vs. mocked

Everything in the cascade, store, sync, dedup, PA generation, privacy/handover
gate, MCP tool logic, dashboard and tests is **real and runnable**. Mocked
against their **real interface contracts** (swap at the noted call site):

- **Bhashini** ASR/TTS — `setu/bhashini.py` (pre-recorded clips / pseudo-audio)
- **IndicXlit** transliteration — `setu/matching/names.py`
- **ArcFace/InsightFace** — `setu/matching/face.py` (transient, gated)
- **Splink** EM-trained weights — `setu/matching/fellegi_sunter.py`
- **pgvector/HNSW** embeddings — `setu/matching/semantic.py`
- **Claude** narration — `setu/agent.py` (deterministic fallback without a key)
- **Dataset** — `data/generate_dataset.py` is **synthetic**, reproducing the
  real distributions; clearly labelled.

## Khoji.in

Out of scope for this MVP and intentionally so: it is only ever an optional,
async, one-way feed-**out** sink for unresolved *adult* records, behind a flag,
off the critical path, with children/non-consented records walled off. SETU
never reads from it into matching.
