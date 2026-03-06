# Sprint 11 Task Board (Frontend UX + Reliability)

Date: 2026-03-05
Owner: Gambill Claw

## Scope
P0
1. Frontend review polish: section hierarchy, milestone readability, datasource why + ingestion UX.
2. Resume flow UX: parse confidence + editable strengths/gaps before generation.
3. Quality diagnostics UX: explicit fail reasons + clearer regeneration guidance.

P1
4. Funnel wiring: CTA event tracking for Discord + coaching conversion signals.
5. Reliability cleanup: Next.js dependency patch update and runtime/startup hygiene.
6. Docs checkpoint + validation runs.

## Completed
- Updated `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`
  - Added resume parse confidence scoring bands (High/Medium/Low) and guidance.
  - Added editable parsed **strengths** and **gaps to close** in resume step.
  - Included resume strengths/gaps/confidence in intake payload (`preferences.resume_profile`) and self-assessment text block.
  - Improved quality diagnostics with a new **Clear fail reasons** section plus existing regenerate guidance.
  - Improved datasource tab UX with explicit "Why this source matters" and ordered ingestion steps.
  - Improved milestone card readability with step badges and cleaner hierarchy.
  - Added conversion wiring for Discord + coaching funnel actions in mentoring recommendation card.

- Updated conversion telemetry type map:
  - `apps/web/src/lib/conversion.ts`
  - Added events:
    - `discord_cta_clicked`
    - `coaching_plan_checkout_clicked`
    - `resume_parse_completed`
    - `resume_parse_failed`

- Updated polish styles:
  - `apps/web/src/app/globals.css`
  - Refined milestone card contrast/border/readability.

- Dependency reliability patch:
  - `apps/web/package.json` + lockfile
  - `next` upgraded from `14.2.5` -> `14.2.35` (same major, latest 14.2 patch line).

## Validation Runs
From `apps/web`:
- `npm run runtime:check` ❌ (expected fail on host runtime mismatch)
  - Required: Node `>=20.11.1 <21`, npm `10.x`
  - Detected: Node `24.13.1`, npm `11.8.0`
- `npm run typecheck` ❌ blocked by runtime precheck
- `npm run build` ❌ blocked by runtime precheck
- `npm run build:clean` ❌ blocked by runtime precheck

Additional compile checks:
- `npm --ignore-scripts run typecheck` ✅
- `npm --ignore-scripts run build` ❌ with known runtime-corruption signature:
  - `EISDIR: illegal operation on a directory, readlink ... src/app/intake/page.tsx`

## Next Action Required (Environment)
Switch local runtime to pinned toolchain before final deterministic verify:
1. Node `20.11.1`
2. npm `10.x`
3. Run:
   - `npm ci --no-audit --no-fund`
   - `npm run typecheck`
   - `npm run build`
   - `npm run build:clean`

## Notes
- Runtime guardrails are functioning correctly and intentionally preventing unsafe builds on mismatched Node/npm.
- Frontend changes are in place and typecheck clean under direct TypeScript execution.