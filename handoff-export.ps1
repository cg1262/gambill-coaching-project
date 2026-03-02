$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $root 'handoff'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$summaryPath = Join-Path $outDir ("handoff-summary-$timestamp.md")

$gitLog = git -C $root log --oneline -n 20
$status = git -C $root status --short

@"
# Handoff Summary ($timestamp)

## Recent Commits

```
$gitLog
```

## Working Tree Status

```
$status
```

## Sprint 2 Board
See: docs/coaching-project/SPRINT_2_TASK_BOARD.md

## Key Docs
- docs/coaching-project/SQUARESPACE_INTEGRATION_IMPLEMENTATION_PLAN.md
- docs/coaching-project/MASTER_TASK_PLAN.md
- docs/coaching-project/RESOURCE_LIBRARY.json
- docs/coaching-project/PILOT_RELEASE_HARDENING_CHECKLIST.md

"@ | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host "Handoff summary written: $summaryPath" -ForegroundColor Green
