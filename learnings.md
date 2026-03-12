# Learnings Log

## Sprint 19 — Frontend Aesthetic Polish (2026-03-12)

### Before Sprint (Plan)

#### Pass 1 — Layout constraint + rhythm
- **Getting ready to do:**
  - Constrain desktop content width while keeping mobile full width.
  - Increase spacing consistency between sections and cards.
- **Success criteria:**
  - No full-bleed feel on desktop.
  - Mobile flow remains unchanged.

#### Pass 2 — Visual hierarchy polish
- **Getting ready to do:**
  - Strengthen hero/panel hierarchy via softer framing and intentional grouping.
  - Keep action controls visible without visual clutter.
- **Success criteria:**
  - Primary areas read first, supporting areas recede.
  - UI feels less “flat dashboard,” more “productized app.”

#### Pass 3 — Desktop two-column workbench
- **Getting ready to do:**
  - Put intake and output areas into a responsive 2-column layout on large screens.
  - Preserve single-column behavior on smaller screens.
- **Success criteria:**
  - Better side-by-side workflow on desktop.
  - No regression to phone/tablet usability.

### After Sprint (Execution + Learnings)

#### Pass 1 — Layout constraint + rhythm
- **What I did:**
  - Updated `.coaching-shell` in `apps/web/src/app/globals.css`:
    - `width: min(1220px, 100% - 24px)`
    - centered with `margin-inline: auto`
    - increased section gap and bottom padding
- **Learnings:**
  - A max-width shell creates immediate visual polish with very low implementation risk.
  - Keeping the same internal cards/components avoids behavior regressions.

#### Pass 2 — Visual hierarchy polish
- **What I did:**
  - Kept existing hero and card hierarchy, but improved overall separation through stronger shell spacing and constrained canvas.
  - Preserved sticky top-nav and busy-strip behavior for operational clarity.
- **Learnings:**
  - Hierarchy gains can come from macro layout first (container and spacing), before changing every component style.
  - Operational UX cues (busy strip/nav) should stay prominent even while polishing visual aesthetics.

#### Pass 3 — Desktop two-column workbench
- **What I did:**
  - Added new responsive grid class in `globals.css`:
    - `.coaching-workbench-grid` single column by default
    - switches to 2 columns at `min-width: 1100px`
  - Wrapped Intake + Output Viewer sections in this grid in:
    - `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`
- **Learnings:**
  - Pairing intake and output side-by-side is the biggest productivity and aesthetic lift for desktop users.
  - Keeping review/readiness sections outside this grid avoids over-compressing dense operational tables.

### Notes for future sprints
- Continue this file every sprint with the same structure:
  1) Before sprint plan per pass
  2) After sprint execution per pass
  3) Explicit learnings per pass
