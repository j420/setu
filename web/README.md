# SETU — Web (Next.js control room)

A polished, offline-first control-room UI for SETU. The **entire matching engine
is ported to TypeScript** (`lib/setu/`) and runs in the browser/edge — no server,
no database — so it deploys cleanly on Vercel and keeps working offline (a core
SETU principle). The Python package at the repo root remains the canonical
reference; this engine is independently verified by its own test suite.

## What's here

- `lib/setu/` — the full cascade in TypeScript: blocking (never on name),
  explainable Fellegi-Sunter, Indic transliteration + phonetic name signal,
  free-text semantic, gated/transient face re-rank, dedup, PA generation,
  the human handover gate, the CRDT store, and the synthetic dataset generator.
- `lib/setu/engine.test.ts` — 25 tests: cascade, no-name matching, handover gate,
  sync, PA, dataset distributions, and edge cases.
- `app/` + `components/` — the dashboard: live metrics, the match queue with
  weight-grounded explanations and the human verification dialog, voice-first
  name-optional intake, the multilingual PA console, dedup view, hotspot
  heatmap, and an online/offline toggle (store-and-forward).

### Real-time inputs

Intake accepts live inputs on this node and matches instantly:
- **Voice input** — a 🎤 button uses the browser Web Speech API to dictate the
  free-text field (Bhashini ASR is the production swap). Graceful fallback to
  typing where unsupported.
- **Photo capture** — upload or take a photo (camera) at intake for *found*
  persons, with explicit consent. Photos are downscaled client-side and stored
  only in the local record (auto-purged on reunion).

### Server-side photo verification (handover step)

At the human verification step, the operator can compare the **found record's
photo** against a **family-provided photo**. The comparison runs **server-side**
at `POST /api/verify-face` (`app/api/verify-face/route.ts` + `lib/faceServer.ts`):
it decodes the real pixels, computes a similarity, and returns a score. It is
**stateless** — no database, no file write, no searchable index (honors "no
standing biometric database") — and the score is **advisory only**: it can never
confirm a handover; a human still does. The current comparator is a perceptual
face-shaped stand-in over real pixels; **ArcFace/InsightFace is the drop-in
production swap behind the same request/response contract.**

### Live data only — no seed, no random data

The deployed app starts **empty**. The queue, dedup view, heatmap and metrics
populate only from **real intake** logged on this node (or, in production, from
ingestion via kiosks/IVR/the federation API). Records entered on a node are
persisted to `localStorage` so the operator's working set survives reloads;
"Clear" wipes them. The synthetic dataset generator (`lib/setu/dataset.ts`) is
retained **only** for the automated test suite — it is never loaded by the app.

## Run locally

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm test           # vitest engine suite
```

## Deploy to Vercel

This app lives in the `web/` subdirectory, so point Vercel at it:

1. Import the repo in Vercel.
2. **Set the project's Root Directory to `web`.** Vercel auto-detects Next.js;
   `web/vercel.json` pins the framework, build and install commands.
3. Deploy. No environment variables are required — the app is fully self-contained
   and runs the engine client-side.

(Using the Vercel CLI: `cd web && vercel`.)

## Why client-side?

- **Offline-first** is a SETU design principle; an engine that runs in the
  browser keeps working with zero connectivity.
- **No biometric database, no PII sink:** there is no backend to store anything.
  Records live in the session; the handover gate and DPDP auto-purge run locally.
- **Perfect Vercel fit:** static + edge, no cold starts, no DB to provision.
