# Gambill Coaching Project Creation

AI-powered coaching app that generates personalized end-to-end data engineering projects from:
- resume
- self-assessment
- target job postings

## Product Goal
Help coaching clients build portfolio-ready projects aligned to the roles they want.

## Core Output
For each client submission, generate a structured SOW including:
- business problem framing
- technical architecture (ingestion/processing/storage/serving)
- medallion implementation plan (Bronze/Silver/Gold)
- milestones with success criteria and estimated hours
- ROI dashboard requirements
- recommended learning resources (including affiliate catalog)
- mentoring recommendation + CTA

## Current Focus
- Coaching-first UX
- Star/Galaxy/Snowflake educational presets
- AI modeling suggestions (PK/FK inference)
- Demo/readiness hardening

## Repo Layout
- `apps/web` — frontend app (intake + project workbench + ERD/teaching tools)
- `apps/api` — backend services and generation scaffolding
- `docs/coaching-project` — coaching-specific plans, resources, pricing, CTA snippets

## Backend Security Controls (Sprint 6)
- Parameterized rate limits (env-driven) with an admin-ready config shape:
  - auth: `10/min per IP`, burst `20`
  - generation: `5/10min per user` + `20/hour per workspace`
  - review actions: `30/min per user`
  - exports: `20/hour per user`
- Admin scaffold endpoints for future console edits:
  - `GET /admin/security/rate-limits`
  - `PUT /admin/security/rate-limits`
- Webhook signature verification endpoint:
  - `POST /coaching/subscription/webhook`
  - HMAC SHA-256 over `{timestamp}.{raw_body}`
  - rejects unsigned/invalid payloads
  - timestamp tolerance: 5 minutes

## Run locally
### API
```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

### Web
```powershell
cd apps/web
npm run runtime:doctor
npm install
npm run dev
```
