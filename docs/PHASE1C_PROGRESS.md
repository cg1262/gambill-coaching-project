# Phase 1c Progress

Completed:
- Wired web UI controls to API endpoints:
  - `/validate/deterministic`
  - `/validate/probabilistic`
  - `/impact/deterministic`
  - `/impact/probabilistic`
- Added demo dataset selector in UI for:
  - telecom
  - cyber
  - manufacturing
  - aviation
- Added violations panel with severity badges (HIGH/MED/LOW)
- Added dependency panel with confidence color badges (red/yellow/green)
- Kept brand color token usage from `globals.css`

Notes:
- Current canvas still uses starter nodes/edges for editing.
- Demo selector currently runs API checks against loaded demo payloads and displays findings.
- Next step can add full node/edge replacement from selected demo into the visual canvas itself.
