$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host '=== Gambill Coaching Project — Next Session Checklist ===' -ForegroundColor Cyan
Write-Host "Repo: $root"
Write-Host ''
Write-Host '1) Pull latest:' -ForegroundColor Yellow
Write-Host '   git pull origin main'
Write-Host ''
Write-Host '2) Start app:' -ForegroundColor Yellow
Write-Host '   .\run-coaching.ps1'
Write-Host ''
Write-Host '3) Validate core flow:' -ForegroundColor Yellow
Write-Host '   intake -> generate -> regenerate -> export -> review queue'
Write-Host ''
Write-Host '4) Review open sprint tasks:' -ForegroundColor Yellow
Write-Host '   docs/coaching-project/SPRINT_2_TASK_BOARD.md'
Write-Host ''
Write-Host '5) Generate handoff artifact when done:' -ForegroundColor Yellow
Write-Host '   .\handoff-export.ps1'
