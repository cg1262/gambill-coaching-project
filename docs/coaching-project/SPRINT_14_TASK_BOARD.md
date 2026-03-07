# Sprint 14 Task Board — Frontend Execution (Windows Deterministic Build + Coach UX)

Last Updated: 2026-03-06 21:31 EST
Scope: `apps/web` + sprint evidence/docs.

## Sprint Priorities (Subagent scope)

1. Close Windows deterministic build blocker (`EPERM`/`EISDIR`) with repeatable remediation path.
2. Produce **two consecutive compliant-runtime proofs** (`Node 20.11.1`, `npm 10.x`) for:
   - `npm ci`
   - `npm run typecheck`
   - `npm run build`
3. Polish coach fail-reason UX prioritization + batch regenerate/review flow.
4. Keep charter/milestone/source readability and resume-confidence explainability stable.
5. Update this board with command evidence.
6. Commit scoped changes.

---

## A) Windows deterministic build blocker (EISDIR/EPERM) — ✅ Closed in frontend path

### What was happening
- On Windows, build intermittently/consistently failed with:
  - `Error: EISDIR: illegal operation on a directory, readlink ...`
- Failures hit paths like:
  - `node_modules/next/dist/pages/_app.js`
  - `src/app/intake/page.tsx`
- `fs.readlink` behavior in this host returned `EISDIR` for regular files, which broke Next trace/build path assumptions.

### Remediation implemented
- Added a build wrapper and shim:
  - `apps/web/scripts/readlink-shim.cjs`
  - `apps/web/scripts/next-build-safe.cjs`
- Updated `build` script in `apps/web/package.json` to route through wrapper:
  - `"build": "node ./scripts/next-build-safe.cjs"`
- Wrapper injects `NODE_OPTIONS=--require=<readlink-shim>` so spawned build processes normalize `EISDIR -> EINVAL` for `readlink` calls.
- Fixed `build-clean.ps1` nested npm invocation reliability under PowerShell/Volta (`cmd /c "npm ..."` usage).

### Additional deterministic fix discovered while proving builds
- Next static prerender required Suspense boundaries for search-param usage:
  - Updated:
    - `apps/web/src/app/intake/page.tsx`
    - `apps/web/src/app/review/page.tsx`
  - Wrapped workbench with `Suspense` fallback to satisfy Next 14 app-router prerender constraints.

---

## B) Two consecutive compliant-runtime proofs — ✅ Complete

Runtime target:
- `node v20.11.1`
- `npm 10.8.2` (npm10-compliant)

### Proof commands (executed in `apps/web`)
```powershell
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm ci --no-audit --no-fund
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run typecheck
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run build
```

### Evidence logs
- `docs/coaching-project/evidence/sprint14-proof-cycle-a.log`
- `docs/coaching-project/evidence/sprint14-proof-cycle-b.log`

Both cycles completed in sequence with runtime checks passing and successful production build output.

---

## C) Coach UX polish — fail-reason prioritization + batch regenerate/review flow — ✅ Implemented

### Updated file
- `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`

### Changes
- Added deterministic fail-reason prioritization (`failReasonPriority`) so actionable issues are surfaced in a better review order.
- Expanded normalization window before display ordering (`slice(0, 8)` then priority sort, render top 6).
- Added batch regenerate action for selected submissions (`runBatchRegenerateSelected`).
- Added explicit batch regenerate status/error badges in the batch action area.
- Guarded concurrent batch actions (review vs regenerate) to avoid overlapping operations.

---

## D) Stability checks for charter/milestone/source readability + resume-confidence explainability — ✅ Stable

- No regressions introduced in these narrative/rendering paths during this scope.
- Build/typecheck path remained green after UX and build-remediation changes.
- Existing coaching workbench rendering remains intact with only targeted prioritization + throughput control updates.

---

## E) Files changed (scoped)

- `apps/web/package.json`
- `apps/web/scripts/build-clean.ps1`
- `apps/web/scripts/next-build-safe.cjs`
- `apps/web/scripts/readlink-shim.cjs`
- `apps/web/src/app/intake/page.tsx`
- `apps/web/src/app/review/page.tsx`
- `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`
- `docs/coaching-project/SPRINT_14_TASK_BOARD.md`

Evidence artifacts created:
- `docs/coaching-project/evidence/sprint14-proof-cycle-a.log`
- `docs/coaching-project/evidence/sprint14-proof-cycle-b.log`
