# Sprint 14 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-06
Sprint Goal: Backend quality-gate enforcement + throughput APIs + operational alert surfacing.

## Epic B — Golden Quality Gates in CI (P0)

### B1. Required golden-suite enforcement
- Owner: Backend
- Status: ✅ Done
- Completed:
  - Added dedicated required gate test `apps/api/tests/test_coaching_sprint14_quality_gates.py`.
  - CI now runs the gate explicitly before full API suite in `.github/workflows/ci.yml`.
  - Gate emits explicit per-scenario drift failures for snapshot/title/milestone and major-deficiency regressions.
- Validation:
  - `python -m pytest -q tests/test_coaching_sprint14_quality_gates.py`

### B2. Seeded sample artifacts
- Owner: Backend
- Status: ✅ Done
- Completed:
  - Added deterministic seeded artifact generator `apps/api/coaching/sprint14_artifacts.py` (3 fake intake scenarios).
  - Committed reviewable output bundle `apps/api/tests/fixtures/sprint14_seeded_artifacts_bundle.json`.
  - Added regression assertions in `apps/api/tests/test_coaching_sprint14_seeded_artifacts.py` to enforce:
    - exactly 3 scenarios,
    - zero major deficiencies,
    - minimum style-alignment threshold,
    - deterministic bundle parity.
- Validation:
  - `python -m pytest -q tests/test_coaching_sprint14_seeded_artifacts.py`

## Epic C — Coach Throughput & UX (P1)

### C1. Batch review/regenerate throughput APIs
- Owner: Backend
- Status: ✅ Done
- Completed:
  - Added `POST /coaching/review/batch-status` for multi-submission review-state updates.
  - Added `POST /coaching/sow/batch-regenerate` for multi-submission regeneration runs.
  - Added coverage in `apps/api/tests/test_coaching_sprint14_throughput_and_alerts.py`.
- Validation:
  - `python -m pytest -q tests/test_coaching_sprint14_throughput_and_alerts.py`

## Epic D — Security/Platform Hygiene (P1)

### D2. Webhook invalid-signature alert routing
- Owner: Security + Backend
- Status: ✅ Done (backend surfacing + routing revalidated)
- Completed:
  - Extended webhook alert tracker to persist recent triggered alerts in-memory.
  - Added best-effort webhook routing hook via `WEBHOOK_INVALID_SIG_ALERT_WEBHOOK_URL`.
  - Added operational visibility endpoint `GET /admin/security/webhook-alerts`.
  - Revalidated end-to-end routing trigger path with explicit security regression (`test_invalid_signature_alert_routes_to_configured_webhook`) to prove threshold-triggered webhook dispatch and secret-safe payload shape.
  - Covered by sprint14 backend test (`invalid_signature_alerts_are_operationally_visible`).

## Required Reporting Format
- Done:
  - Golden gate promoted and made explicit in CI.
  - Seeded artifact generator + committed output bundle added.
  - Batch review/regenerate throughput APIs added.
  - Invalid-signature alerts now queryable operationally and optionally routable via outbound webhook URL.
- Validation:
  - Focused pytest pack (Sprint 14):
    - `tests/test_coaching_sprint14_quality_gates.py`
    - `tests/test_coaching_sprint14_seeded_artifacts.py`
    - `tests/test_coaching_sprint14_throughput_and_alerts.py`
  - Security revalidation pack:
    - `tests/test_auth_contract_security.py`
    - `tests/test_auth_sessions.py`
    - `tests/test_security_rate_limit_webhook.py`
    - `tests/test_rate_limits_and_webhooks.py`
    - `tests/test_coaching_subscription.py`
    - `tests/test_llm_output_security.py`
- Risks:
  - Alert routing is best-effort webhook delivery; production reliability depends on operator-managed downstream receiver.
- Needs from others:
  - Frontend can adopt new batch APIs to reduce per-submission action loops.
  - Ops to set `WEBHOOK_INVALID_SIG_ALERT_WEBHOOK_URL` in production/staging where routing is desired.
- Next:
  - Add retry/backoff telemetry for outbound alert webhook delivery and optional dead-letter persistence.
