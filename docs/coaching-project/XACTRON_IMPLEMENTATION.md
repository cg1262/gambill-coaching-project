# Xactron / Cron Implementation Notes

## What was implemented
- Added machine-readable schedule spec:
  - `docs/coaching-project/XACTRON_TASK_SPECS.yaml`
- Includes 6 high-value business automations with exact cron expressions, outputs, and thresholds.

## How to activate
Use your scheduler UI (OpenClaw Control UI cron or Xactron equivalent) and create tasks from YAML entries:
1. id
2. schedule
3. task prompt/steps
4. destination channel (Discord DM)

## Recommended rollout order
1. `calendar_prep_brief`
2. `revenue_pipeline_watch`
3. `coaching_client_risk_monitor`
4. `weekly_kpi_digest`
5. `content_repurposing_queue`
6. `invoice_payment_anomaly_check`

## Safety/quality guardrails
- Max output: top 3 actions unless urgent.
- Avoid late-night pings unless urgent payment/risk issue.
- For content drafts: always require approval before posting.

## Future enhancement
Add a structured state file (last-run timestamps + sent item hashes) to reduce duplicate alerts.
