# Squarespace Integration Implementation Plan

Last Updated: 2026-03-01
Project: Gambill Coaching Project Creation

## Objective
Integrate the coaching app into a Squarespace-based coaching business with a members-only experience and subscription-aware access control.

## Integration Strategy (Recommended)
Use Squarespace as the marketing + membership front door, and host the coaching app on a dedicated subdomain.

- Main site: `www.gambilldataengineering.com` (Squarespace)
- Coaching app: `coach.gambilldataengineering.com` (hosted app)
- Access model: Members-only Squarespace page + app-side subscription verification

---

## User Journey
1. Visitor lands on Squarespace sales page.
2. User purchases/subscribes (Squarespace/Stripe flow).
3. User gets access to members-only "Coaching Program" area.
4. User clicks "Launch Project Builder".
5. User is redirected to `coach.gambilldataengineering.com`.
6. Coaching app verifies account/subscription status.
7. User uses intake -> generation -> exports inside coaching app.

---

## Phase 1: Infrastructure + Routing

### Tasks
- Provision hosting for app frontend/backend (Vercel/Render/Azure).
- Configure custom subdomain `coach.gambilldataengineering.com`.
- Set DNS CNAME/A records.
- Enable HTTPS and enforce secure cookies.

### Acceptance Criteria
- App reachable at `https://coach.gambilldataengineering.com`.
- API reachable with secure origin/CORS settings.

---

## Phase 2: Access Control + Identity

## MVP (fast path)
- Squarespace members page acts as gate to launch link.
- App uses its own login + session.
- App enforces active subscription flag via backend check.

## Next (improved UX)
- Add launch token handoff from Squarespace page to app.
- Token maps to known user email and session bootstrap.

### Acceptance Criteria
- Non-subscribers cannot access generator routes.
- Subscribers can access and generate projects.

---

## Phase 3: Billing & Subscription Verification

### Recommended
- Keep billing in current Squarespace/Stripe stack.
- Backend sync job or webhook ingestion stores subscription state in app DB.

### Data model (minimum)
- `coaching_accounts`
  - email
  - plan_tier
  - subscription_status
  - renewal_date
  - provider_customer_id

### Acceptance Criteria
- App reflects active/inactive status within acceptable delay.
- Tier-aware features can be toggled (future-ready).

---

## Phase 4: Squarespace UI Integration

### Member area page sections
- Welcome + quick-start video
- "Launch Project Builder" button
- FAQ and support link
- Mentoring upgrade CTA

### Optional embedding
- iframe embed only if host headers allow and UX is acceptable.
- Fallback should always be direct open in new tab.

### Acceptance Criteria
- Member can launch app in one click.
- Launch experience is understandable and stable.

---

## Phase 5: Security & Compliance Baseline

### Required controls
- Secure session cookies / token handling
- PII-safe logs
- Resume upload validation & storage controls
- Rate limiting on auth/intake endpoints
- Affiliate transparency text in generated outputs

### Acceptance Criteria
- Security checklist passes baseline tests.
- No sensitive payload leakage in logs.

---

## Phase 6: Analytics & Conversion Tracking

### Track
- Member page clicks -> app launch rate
- Intake completion rate
- Project generation success rate
- Export usage
- Mentoring CTA click-through and conversion

### Acceptance Criteria
- Dashboard/report exists for core funnel metrics.

---

## Agent Task Assignment

### Backend Agent
- Implement account/subscription model and access guards.
- Add endpoint for subscription status checks.
- Build webhook/sync stub for Squarespace/Stripe subscription state.

### Frontend Agent
- Create coaching auth gate UI + subscription-required states.
- Add launch/landing page states for member journey.
- Add tier/plan display and upgrade prompt placement.

### Security Agent
- Threat model for hosted coaching app + member access flow.
- Verify logging/PII masking in new auth/billing paths.
- Add tests for unauthorized access and token misuse.

---

## Go-Live Checklist
- [ ] DNS + HTTPS active
- [ ] Members page live in Squarespace
- [ ] Subscription enforcement verified
- [ ] Critical flows tested (login, intake, generate, export)
- [ ] Error handling + support path documented
- [ ] Funnel tracking validated

---

## Notes
Start with reliability and access control before deep SSO complexity. A clear members-only launch flow with stable app auth is enough for initial rollout and revenue testing.