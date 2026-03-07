# Sprint 17 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-07 (frontend UX + backend contract check)
Sprint Goal: Add dark mode + stronger panel-based layout for higher engagement/readability.
Latest backend evidence: `docs/coaching-project/evidence/sprint17-backend-contract-check.log`

## Epic A — Theme System (P0)

### A1. Dark mode foundation
- Owner: Frontend
- Status: **Done**
- Scope:
  - implement light/dark theme tokens (CSS variables)
  - add theme toggle + persisted preference
  - respect system preference on first load
- Acceptance:
  - user can switch themes instantly and preference persists

### A2. Accessible contrast pass
- Owner: Frontend + Security
- Status: **Done**
- Scope:
  - verify text/background contrast and interactive states in both themes
- Acceptance:
  - key surfaces meet readable contrast and focus state visibility

## Epic B — Panel-Based Layout Redesign (P0)

### B1. Page paneling and hierarchy
- Owner: Frontend
- Status: **Done**
- Scope:
  - convert long sections into clear panels/cards with visual grouping
  - improve spacing rhythm, typography hierarchy, and scanability
- Acceptance:
  - intake/review/output screens feel structured and easier to navigate

### B2. Engagement-oriented micro-interactions
- Owner: Frontend
- Status: **Done**
- Scope:
  - subtle hover/focus states, section headers, and progress cues
- Acceptance:
  - improved perceived polish without visual clutter

## Epic C — Workflow UX Coherence (P1)

### C1. Cohesive panel interactions
- Owner: Frontend + Backend
- Status: **Done (backend contract impact: none required)**
- Scope:
  - ensure panel states (loading/error/success) are consistent across generation/review actions
- Acceptance:
  - no inconsistent messaging across major panels

### C2. Docs + evidence
- Owner: Frontend
- Status: **Done**
- Scope:
  - update sprint board + POC status with before/after notes and validation evidence
- Acceptance:
  - checkpoints include explicit UX deltas and proof commands

## Required Reporting Format
- Done:
  - Implemented Sprint 17 frontend theme execution in `CoachingProjectWorkbench` and `globals.css`:
    - explicit light/dark token compatibility (`data-theme="light"|"dark"` + backward compatibility for existing theme ids)
    - hero theme toggle with persistent local preference (`coaching-theme-mode`)
    - system preference default on first load with system-change sync when no saved override exists.
  - Upgraded panel hierarchy and engagement polish for coaching flows:
    - section header treatment, panelized card surfaces, sticky route-nav panel, progress cue refinements.
  - Preserved workflow functionality/readability across intake, generate/regenerate, review queue, and export pathways.
  - Preserved prior Sprint 17 backend contract checkpoint evidence in `docs/coaching-project/evidence/sprint17-backend-contract-check.log`.
- Validation:
  - `npm run typecheck` (apps/web) → **pass**.
  - `npm run build` (apps/web) → **pass**.
- Risks:
  - Existing pydantic warning (`TableNode.schema` field shadow) remains non-blocking and unchanged (backend, pre-existing).
- Needs from others:
  - Optional UX/security contrast sign-off pass for dense review-table and badge surfaces under dark mode.
- Next:
  - Add visual regression snapshots for light/dark coaching surfaces and continue trimming large inline style blocks into theme-aware class utilities.
