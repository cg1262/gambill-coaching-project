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
