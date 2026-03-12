# Web App (Next.js + React Flow)

## Runtime / Tooling Baseline
- Node: **20 LTS** (pinned to **20.11.1** via `.nvmrc` + `volta.node`)
- npm: **10.x** (pinned via `packageManager` + `engines` + `volta.npm`)
- `npm` scripts enforce runtime parity before `dev`, `typecheck`, `build`, and `build:clean`.
  - mismatch exits immediately with a remediation message (switch to Node 20.11.1 + npm 10.x).

## Deterministic Build Flow (from clean clone)
From `apps/web`:

```bash
npm run verify:deterministic
```

Equivalent explicit sequence:

```bash
npm run install:ci
npm run typecheck
npm run build
npm run build
```

Expected: all commands pass, including the second build run.

## Recovery Command (one-command clean build)

```bash
npm run build:clean
```

`build:clean` will:
1. clear `.next` and `tsconfig.tsbuildinfo`
2. run `npm run build`
3. if recoverable module/bin corruption is detected (`EISDIR`, missing `next`/`tsc`), remove `node_modules`, run `npm ci`, and retry once.

## Failure Signatures + Next Action
- `EISDIR ... page.tsx` or `EISDIR ... node_modules/next/dist/pages/_app.js`
  - Root cause in this project was runtime drift (host Node 24 / npm 11) against pinned Node 20.11.1 / npm 10.x expectations, which can corrupt install/build paths.
  - Run: switch runtime first, then `npm ci --no-audit --no-fund` and `npm run build:clean`
- `'next' is not recognized` / `Cannot find module 'next'`
  - Run: `npm run build:clean`
- `'tsc' is not recognized` / `Cannot find module 'typescript'`
  - Run: `npm run build:clean`
- lockfile missing
  - Run: `npm install` once to generate `package-lock.json`, commit it, then rerun deterministic flow.
- repeated install/build failure after recovery
  - Run `npm cache verify`, confirm Node/npm versions above, retry on stable local disk context.

## Actionable Runtime Remediation Flow
```bash
npm run runtime:doctor
npm run runtime:check
```
- `runtime:doctor` prints required vs detected versions and exact next commands.
- If runtime check fails:
  1. switch to Node `20.11.1` (`.nvmrc` / Volta pin)
  2. confirm npm is `10.x`
  3. run `npm run install:ci`
  4. run `npm run verify:deterministic`
- If deterministic verification still fails, run `npm run build:clean` for one-pass artifact + module recovery.

## Internal Rate-Limit UX Scaffolding (Admin-ready hook)
- The workbench now handles HTTP **429** responses with actionable retry guidance.
- If backend returns `Retry-After`, UI messaging uses it; otherwise UI uses configurable fallback seconds.
- Hidden/internal config panel is available at:
  - `/intake?internal=1` (or `?admin=1`)
- Panel stores local browser config (`localStorage`) for:
  - fallback retry window (seconds)
  - helper text shown in issue/retry guidance

This is scaffolding for a future centralized admin console/API-backed settings flow.
