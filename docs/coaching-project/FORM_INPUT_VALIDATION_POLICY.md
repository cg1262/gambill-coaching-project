# Coaching Form Input Validation Policy

Last Updated: 2026-03-02
Owner: Security Agent

## Scope
Applies to `POST /coaching/intake` request validation for structured and freeform user inputs.

## Validation Rules
1. **Strict payload shape**
   - Reject unknown top-level fields (`extra="forbid"`).
2. **Structured field constraints**
   - `workspace_id`, `applicant_name`: required, non-empty, max 120 chars.
   - `applicant_email`: optional, max 254 chars.
   - `preferences` keys allowed: `target_role`, `preferred_stack`, `timeline_weeks`.
   - `preferences.target_role`, `preferences.preferred_stack`: max 120 chars.
   - `preferences.timeline_weeks`: integer only, range `1..104`.
3. **Freeform field constraints**
   - `resume_text`, `self_assessment_text`: max 12,000 chars each.
4. **Job link constraints**
   - `job_links` max 20 entries.
   - Each link must be a fully-qualified URL with `http` or `https` scheme.
   - Block unsupported or unsafe schemes (e.g., `javascript:`, `data:`, `file:`).

## Failure Behavior
- Invalid input returns HTTP `422` validation error.
- Error responses should be generic and not include internal implementation details.

## Security Intent
- Prevent script/protocol injection via user-provided links.
- Bound request size and freeform content to reduce abuse risk and processing overhead.
- Preserve predictable typed contracts for downstream persistence/generation paths.
