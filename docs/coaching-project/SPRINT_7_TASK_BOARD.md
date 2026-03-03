# Sprint 7 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-03
Sprint Goal: Close remaining launch blockers (web deterministic build + runtime parity), finalize pilot gate, and execute first controlled pilot run.

## Done
- Added strict runtime parity guardrails for `apps/web`:
  - New script: `apps/web/scripts/require-runtime.cjs`
  - Enforced before `dev`, `typecheck`, `build`, and `build:clean` via npm pre-scripts in `apps/web/package.json`
  - Guard now fails fast unless runtime is Node `>=20.11.1 <21` and npm `10.x`, with remediation commands.
- Hardened `apps/web/scripts/build-clean.ps1`:
  - Added strict runtime parity assertion with explicit error guidance.
  - Added source-path integrity checks for known build-critical app routes (guards against file/directory corruption signatures that can manifest as `EISDIR/readlink` failures).
- Updated runtime/build troubleshooting docs:
  - `apps/web/README.md` now documents fail-fast parity checks and root-cause framing for prior `EISDIR` behavior under runtime drift.
- Tightened coaching quality-loop UX prompts in `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`:
  - Added diagnostics-to-feedback-tag suggestions.
  - Added human-readable feedback tag labels.
  - Added “Apply suggested tags” action.
  - Added coach review prompt draft text based on diagnostics/tag signals.
- Executed controlled pilot API flow verification (intake -> generate -> export + review approve/send) as deterministic regression evidence.

## Validation
- Runtime parity checks (from `apps/web`) now block mismatched host immediately:
  - `npm run typecheck` -> **fail-fast as designed** on host Node `v24.13.1` / npm `11.8.0`
  - `npm run build` -> **fail-fast as designed** on host Node `v24.13.1` / npm `11.8.0`
  - `npm run build:clean` -> **fail-fast as designed** on host Node `v24.13.1` / npm `11.8.0`
- Controlled pilot backend flow checks (from `apps/api`):
  - `python -m pytest -q tests/test_security_sprint2.py::test_a2_security_regression_flow_intake_generate_validate_export tests/test_coaching_review_endpoints.py::test_review_approve_send_generates_launch_token`
  - Result: **2 passed**, 1 known pydantic warning.

## Risks
- Deterministic **success** build proof (`npm ci`, `npm run typecheck`, `npm run build` twice) is still pending execution under compliant runtime (Node 20.11.1 / npm 10.x) on this host.
- Current host runtime remains out-of-contract (Node 24 / npm 11), so only fail-fast behavior can be validated here.

## Needs from others
- Platform/runtime owner action: install/switch to Node `20.11.1` and npm `10.x` on build host (or provide compliant CI runner).

## Next
1. On compliant runtime, run and capture final deterministic sequence:
   - `npm ci --no-audit --no-fund`
   - `npm run typecheck`
   - `npm run build`
   - `npm run build`
   - `npm run build:clean`
2. Attach clean logs + commit SHA to Sprint 7 evidence packet.
3. If any residual `EISDIR` appears under compliant runtime, capture exact path and add targeted integrity repair (preinstall sanitation) before release gate.

---

## Checkpoint Update (2026-03-03 — Sprint 7 Backend Execution)

## Done
- Tightened webhook/sync idempotency in `apps/api/main.py` by adding `_derive_subscription_event_id(...)`.
- Both `POST /coaching/subscription/sync` and `POST /coaching/subscription/webhook` now:
  - dedupe replay events even when provider `raw_event.id` is missing,
  - return `idempotency_key_source` (`provider_event_id` or `derived`) for pilot observability.
- Verified route-level throttling coverage for operational subscription paths:
  - `POST|GET /coaching/subscription/status`
  - `GET /coaching/subscription/lifecycle-readiness`
  - `GET /coaching/pilot/launch-readiness`
  - `POST /coaching/subscription/sync`
  - `POST /coaching/subscription/webhook`
- Extended parameterized rate-limit tuning in `apps/api/rate_limits.py` with `RATE_LIMIT_SUBSCRIPTION_USER_BURST`.
- Added Sprint 7 backend regression suite `apps/api/tests/test_coaching_sprint7_backend.py` covering:
  - derived idempotency replay behavior,
  - admin override path for subscription rate-limit policy,
  - controlled pilot trace (intake → generate → regenerate → export → review feedback) and conversion/feedback integrity.

## Validation
- Focused security + Sprint 7 backend checks (`apps/api`):
  - `python -m pytest -q tests/test_coaching_sprint7_backend.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py`
  - Result: **17 passed, 1 warning**.
- Full API regression (`apps/api`):
  - `python -m pytest -q`
  - Result: **131 passed, 4 skipped, 1 warning**.

## Risks
- Derived idempotency keys intentionally collapse payload-equivalent no-ID events; if providers emit distinct no-ID events with identical payloads, they will be treated as replay.
- Alerting/automation for repeated invalid webhook signatures is still an operational follow-up (enforcement exists; alert pipeline is not added in this pass).

## Needs from others
- Ops/SRE sign-off on invalid-signature alert thresholds and routing.
- Product decision confirmation on strict no-ID dedupe semantics.

## Next
1. Optionally add windowed/TTL-aware dedupe keying if looser no-ID semantics are desired.
2. Wire repeated invalid-signature detection into production alerting and close checklist item.
3. Include these backend evidence commands/results in pilot launch notes alongside web runtime-parity proof.
