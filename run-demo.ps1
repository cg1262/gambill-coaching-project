param(
  [switch]$NoInstall
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root 'apps\api'
$webDir = Join-Path $root 'apps\web'

Write-Host 'Starting Data Modeling IDE demo stack...' -ForegroundColor Cyan

# API setup
$venvDir = Join-Path $apiDir '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
  Write-Host 'Creating API virtual environment...' -ForegroundColor Yellow
  Push-Location $apiDir
  if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
  } else {
    throw 'Python launcher not found. Install Python 3 and ensure `py` or `python` is on PATH.'
  }
  Pop-Location
}

if (-not (Test-Path $venvPython)) {
  throw "Virtual environment python not found at $venvPython"
}

if (-not $NoInstall) {
  Write-Host 'Installing API dependencies...' -ForegroundColor Yellow
  Push-Location $apiDir
  & $venvPython -m pip install -r requirements.txt | Out-Host
  Pop-Location
}

# Web setup
if (-not (Test-Path (Join-Path $webDir 'node_modules')) -and -not $NoInstall) {
  Write-Host 'Installing Web dependencies...' -ForegroundColor Yellow
  Push-Location $webDir
  npm install | Out-Host
  Pop-Location
}

# Start API in new window
$apiCmd = "cd /d `"$apiDir`" && .venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"
Start-Process cmd.exe -ArgumentList "/k $apiCmd"

# Start Web in new window
$webCmd = "cd /d `"$webDir`" && npm run dev"
Start-Process cmd.exe -ArgumentList "/k $webCmd"

Start-Sleep -Seconds 3
Write-Host 'Demo services launched:' -ForegroundColor Green
Write-Host '  API: http://localhost:8000/health'
Write-Host '  Web: http://localhost:3000'
Write-Host ''
Write-Host 'Tip: Use -NoInstall to skip dependency installation on later runs.' -ForegroundColor DarkGray
