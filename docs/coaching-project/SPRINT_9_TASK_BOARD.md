# Sprint 9 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-04
Sprint Goal: Improve project-generation quality with resume-aware personalization and strict charter-flow structure.

## Epic A — Resume Upload + Parsing Pipeline (P0)

### A1. Intake upload endpoint
- Owner: Backend
- Status: ✅ Completed
- Delivered:
  - Added `POST /coaching/intake/resume/upload` (multipart) supporting `.pdf`, `.docx`, `.txt`.
  - Reused file metadata validation (type/size/path safety constraints).

### A2. Structured resume signal extraction
- Owner: Backend
- Status: ✅ Completed
- Delivered:
  - Added deterministic extractor for:
    - role level
    - tools
    - domains
    - project experience keywords
    - strengths/gaps
  - Added fallback markers when extraction returns low/empty text.

### A3. Persistence for generation usage
- Owner: Backend
- Status: ✅ Completed
- Delivered:
  - Added intake request support for `resume_parse_summary`.
  - Persisted parsed summary in `preferences.resume_parse_summary`.
  - Added DB helper to update preferences on existing submission.

## Epic B — GlobalMart-like Project Charter Flow (P0)

### B1. Enforced section flow
- Owner: Backend
- Status: ✅ Completed
- Delivered:
  - Added `project_charter` with required ordered sections:
    1. `prerequisites_resources`
    2. `executive_summary` (current/future)
    3. `technical_architecture`
    4. `implementation_plan`
    5. `deliverables_acceptance_criteria`
    6. `risks_assumptions`
    7. `stretch_goals`

### B2. Narrative/data source quality
- Owner: Backend
- Status: ✅ Completed
- Delivered:
  - Validator checks for real public URLs and ingestion-doc URLs in charter architecture sources.
  - Prompt contract updated to require realistic fictitious business narrative and tighter milestone expectations.

## Epic C — Validation + Regression Tests (P0)

### C1. New backend tests
- Owner: Backend
- Status: ✅ Completed
- Delivered:
  - `apps/api/tests/test_coaching_sprint9_backend.py`
    - resume upload parse happy-path
    - resume parse fallback behavior
    - charter section order enforcement

## Test Evidence
- `python -m pytest -q tests/test_coaching_sprint9_backend.py` (apps/api) → pass

## Epic D — Frontend Review-Ready UX Refresh (P0)

### D1. Intake resume upload experience
- Owner: Frontend
- Status: ✅ Completed
- Delivered:
  - Added drag/drop + file picker resume intake UI in `CoachingProjectWorkbench`.
  - Added upload progress + parse status states.
  - Added editable parsed highlights list (add/remove/edit) before submit.

### D2. Project output charter readability redesign
- Owner: Frontend
- Status: ✅ Completed
- Delivered:
  - Added new default `Project Charter` view with narrative business story at top.
  - Added prominent data source + ingestion instruction block.
  - Redesigned milestone section into card format with expectations, deliverables, acceptance checks.
  - Improved spacing/typography for reviewer scanning.

### D3. Combined profile payload alignment
- Owner: Frontend
- Status: ✅ Completed
- Delivered:
  - Combined self-assessment + resume-derived highlights into submitted intake body.
  - Added `preferences.resume_profile` and `preferences.combined_profile` payload support.
  - Added load-back support for resume highlights from submission preferences.

## Test Evidence
- `powershell -ExecutionPolicy Bypass -File .\run-coaching.ps1 -RuntimeCheckOnly` (repo root) → pass, runtime remediated to Node 20.11.1/npm 10.8.2.
- `C:\Program Files\Volta\volta.exe run --node 20.11.1 --npm 10.8.2 npm run typecheck` (apps/web) → pass.
- `C:\Program Files\Volta\volta.exe run --node 20.11.1 --npm 10.8.2 npm run build` (apps/web) → **fails** with pre-existing Next.js/node_modules corruption signature (`EISDIR ... next/dist/pages/_app.js`, then `EPERM .next/trace`).

## Risks / Follow-ups
- OCR support for scanned PDFs remains out-of-scope for sprint 9 (current behavior is explicit fallback warning).
- Optional next step: route extracted resume text through PII-aware summarization before long-term analytics storage.
- Resolve deterministic Windows `next` build corruption via clean node_modules reinstall / lock recovery before release build signoff.
