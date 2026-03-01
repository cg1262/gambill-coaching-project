# Gambill Coaching Project Creation — Master Task Plan

Last Updated: 2026-03-01
Owner: Orchestrator (main)

## Objective
Build a coaching app that generates tailored end-to-end data engineering projects from resume + self-assessment + job postings, with business-outcome framing, realistic data sources, medallion implementation plan, ROI dashboard requirements, and curated resources/mentoring CTA.

## Workstreams

### Backend (Agent: backend)
1. Intake API + persistence
   - Create endpoints for applicant intake (resume, self-assessment, job links, preferences)
   - Persist submissions and generation runs
2. Job posting parsing pipeline
   - URL fetch + text extraction + skills/tool/domain signal extraction
3. Project generation service
   - OpenAI orchestration with structured JSON output (SOW schema)
   - Enforce required sections and business-outcome mapping
4. Validation + revision loop
   - Rule checks (medallion completeness, ROI metric, milestones, resource links)
   - Auto-revise once on failed checks
5. Resource matching service
   - Match resources to milestones and learner profile
6. Mentoring recommendation logic
   - Recommend tier based on complexity + skill gap + urgency
7. Export API
   - Markdown/PDF-ready payload generation

### Frontend (Agent: frontend)
1. Multi-step intake UX
   - Resume upload, self-assessment link/input, job links, stack preference
2. Project output viewer
   - Render SOW sections with milestone tracker, architecture, ROI requirements
3. Resource panel
   - Required/Recommended/Optional grouped by milestone
4. Mentoring CTA + plan recommendation module
   - Present suggested tier + pricing card + conversion CTA
5. Export/share UX
   - Download markdown/pdf package
6. Admin/coach view
   - View submissions, generated projects, and status

### Security (Agent: security)
1. Input/file handling hardening
   - Resume file validation/safe storage
2. Secrets/auth hardening
   - API key handling and RBAC guardrails
3. PII/Privacy controls
   - Mask sensitive data in logs and exports
4. Billing/webhook security checklist
   - Stripe/webhook signature validation (if payment enabled)
5. Security test suite
   - Regression checks for auth/rbac/file upload

### Orchestrator (main)
1. Resource library curation
2. Mentoring CTA copy/snippets
3. Pricing positioning and rollout scripts
4. Weekly integration checkpoints + acceptance gate

## Acceptance Criteria (Project MVP)
- Intake -> generation -> validated SOW completes successfully
- Output includes business framing, medallion plan, milestones, ROI dashboard requirements
- Output includes targeted resource links + mentoring CTA
- Export package available
- Coach can review generated output and recommended tier

## Suggested Sequence
Week 1: Backend schema + intake + SOW generation skeleton + frontend intake UI
Week 2: Validation loop + resources matching + output UI render
Week 3: Mentoring recommendation + export + security hardening pass
Week 4: Pilot readiness, QA, and conversion instrumentation
