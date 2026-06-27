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
  heatmap, an online/offline toggle (store-and-forward), and a guided end-to-end
  demo (the Sita Devi reunion + offline cut & re-sync + gate-bypass proofs).

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
