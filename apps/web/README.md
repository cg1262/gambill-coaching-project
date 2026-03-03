# Web App (Next.js + React Flow)

## Runtime / Tooling Baseline
- Node: **20 LTS** (pinned to **20.11.1** via `.nvmrc`)
- npm: **10.x** (`packageManager` + `engines` in `package.json`)

## Deterministic Build Flow (from clean clone)
From `apps/web`:

```bash
npm ci --no-audit --no-fund
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
- `EISDIR ... page.tsx` or similar filesystem extraction issue
  - Run: `npm run build:clean`
- `'next' is not recognized` / `Cannot find module 'next'`
  - Run: `npm run build:clean`
- `'tsc' is not recognized` / `Cannot find module 'typescript'`
  - Run: `npm run build:clean`
- lockfile missing
  - Run: `npm install` once to generate `package-lock.json`, commit it, then rerun deterministic flow.
- repeated install/build failure after recovery
  - Run `npm cache verify`, confirm Node/npm versions above, retry on stable local disk context.

## Internal Rate-Limit UX Scaffolding (Admin-ready hook)
- The workbench now handles HTTP **429** responses with actionable retry guidance.
- If backend returns `Retry-After`, UI messaging uses it; otherwise UI uses configurable fallback seconds.
- Hidden/internal config panel is available at:
  - `/intake?internal=1` (or `?admin=1`)
- Panel stores local browser config (`localStorage`) for:
  - fallback retry window (seconds)
  - helper text shown in issue/retry guidance

This is scaffolding for a future centralized admin console/API-backed settings flow.
