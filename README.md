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
npm install
npm run dev
```
