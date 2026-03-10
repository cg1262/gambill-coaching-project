# Gambill Coaching App — Handoff (Critical Goals & Outcomes)

Date: 2026-03-09
Repo: `E:/gde_git/gambill-coaching-project`
Primary branch: `main`

## 1) Product North Star
Build a coaching platform that consistently produces **portfolio-grade, interview-generating data projects** (not generic scaffolds), with a coach workflow that can scale cohort review and conversion into paid coaching.

## 2) Critical Project Goals

### Goal A — High-quality project generation (core value)
- Generate realistic, fictitious business stories with concrete context.
- Require real public data sources + ingestion docs + explicit ingestion instructions.
- Enforce charter-style structure (GlobalMart/VoltStream-like flow).
- Include milestone-level expectations, deliverables, and acceptance checks.
- Reject instruction-echo and generic scaffold language.

### Goal B — Reliable user UX during async operations
- User must always know when app is working vs waiting:
  - busy cursor/state
  - loading button labels
  - top status strip
- Hide stale issue banners; show only current actionable errors.
- Surface generation mode/reason codes when generation fails.

### Goal C — Coach throughput and review operations
- Enable quick templates, batch review actions, and batch regenerate recipes.
- Provide actionable fail reasons tied to one-click correction/regenerate flow.
- Improve intake mapping clarity (skills/domain/keywords/resume signals).

### Goal D — Conversion and funnel visibility
- Track and summarize key journey events:
  - intake complete
  - generate/regenerate
  - export
  - CTA interactions (Discord/coaching)
- Provide weekly summary with stage drop-off insights.

### Goal E — Security and operational hardening
- Keep auth/session/rate-limit/webhook controls green under regression tests.
- Ensure invalid webhook signature alert routing works and is secret-safe.
- Maintain bounded-risk posture for Next remediation until migration decision closes.

## 3) Key Outcomes Delivered (to date)

### Output quality system
- Added quality gates and major-deficiency detection.
- Added instruction-echo and generic-output rejection heuristics.
- Added golden scenario tests and seeded artifact quality checks.
- Added explicit generation metadata:
  - `generation_mode` (`llm`, `revised`, `fallback_scaffold`)
  - deterministic `generation_reason_codes`.

### UX + engagement improvements
- Busy-state cursor + loading labels + top busy strip implemented.
- Intake fixes include explicit fields/ranks for:
  - SQL
  - Data Modeling
  - Domains
  - Project Keywords
- Work platforms placement and form clarity improved.
- Dark mode + panel hierarchy added for better engagement/readability.

### Coach workflow
- Batch review and batch regenerate support implemented.
- Actionable fail-reason UI and correction loops improved.
- Selection/queue productivity enhancements added.

### Conversion/analytics
- Weekly conversion summary and drop-off logic improved.
- Event taxonomy expanded; reporting endpoints matured.

### Security/ops
- Security regression packs remain green in focused runs.
- Invalid-signature alert routing validated and documented.
- Runtime checks hardened; deterministic build proof flow scripted.

## 4) Current Risks / Open Items
- Local Windows environment can still show intermittent npm/node_modules lock/corruption signatures in some shells.
- Next vulnerability remediation remains a tracked platform decision/migration checkpoint.
- Fallback generation may still appear if upstream LLM path is unavailable; now visible via mode/reason codes and should be monitored.

## 5) Operator Checklist (Critical)
1. Start app with runtime-aware launcher:
   - `./run-coaching.ps1`
2. Confirm API + web health.
3. During generation issues, capture and inspect:
   - `generation_mode`
   - `generation_reason_codes`
4. If output quality regresses, run golden/quality suites before merge.
5. Keep `lakebase.duckdb` handling intentional (local artifact behavior as desired by current workflow).

## 6) Recommended Next Outcomes
- Convert current quality bar into strict release gate for all merges touching generation.
- Finish Next remediation decision and execute chosen path.
- Continue tightening “no generic output” loop until repeated manual review passes on real user inputs.

---
Prepared for context reset and fast restart continuity.
