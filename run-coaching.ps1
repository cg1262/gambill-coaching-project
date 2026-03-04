param(
  [switch]$RuntimeCheckOnly
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root 'apps/api'
$webDir = Join-Path $root 'apps/web'
$venvPython = Join-Path $apiDir '.venv/Scripts/python.exe'

Write-Host 'Starting Gambill Coaching app with health checks...' -ForegroundColor Cyan

function Get-CommandVersion($name, $versionArg = '--version') {
  try {
    $v = (& $name $versionArg 2>$null | Select-Object -First 1).ToString().Trim()
    return $v
  } catch { return $null }
}

function Ensure-WebRuntime {
  param(
    [string]$NodeVersion = '20.11.1',
    [string]$NpmVersion = '10.8.2'
  )

  $nodeOk = $false
  $npmOk = $false

  $nodeV = Get-CommandVersion 'node' '-v'
  $npmV = Get-CommandVersion 'npm' '-v'
  if ($nodeV -match '^v20\.11\.1$') { $nodeOk = $true }
  if ($npmV -match '^10\.') { $npmOk = $true }

  if ($nodeOk -and $npmOk) {
    Write-Host "[WEB] Runtime OK: node $nodeV, npm $npmV" -ForegroundColor Green
    return
  }

  Write-Host "[WEB] Runtime mismatch detected: node $nodeV, npm $npmV" -ForegroundColor Yellow
  Write-Host '[WEB] Attempting automatic runtime remediation...' -ForegroundColor Yellow

  $voltaBins = @(
    (Join-Path $env:LOCALAPPDATA 'Volta\bin'),
    'C:\Program Files\Volta'
  )
  $voltaBin = $null
  $voltaExe = $null
  foreach($b in $voltaBins){
    if(Test-Path (Join-Path $b 'volta.exe')) { $voltaBin = $b; $voltaExe = (Join-Path $b 'volta.exe'); break }
  }

  if (-not $voltaExe -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host '[WEB] Volta not found. Installing via winget...' -ForegroundColor Yellow
    winget install --id Volta.Volta -e --accept-source-agreements --accept-package-agreements | Out-Host
    foreach($b in $voltaBins){
      if(Test-Path (Join-Path $b 'volta.exe')) { $voltaBin = $b; $voltaExe = (Join-Path $b 'volta.exe'); break }
    }
  }

  if ($voltaExe) {
    $env:PATH = "$voltaBin;$env:PATH"
    Write-Host '[WEB] Using Volta to pin Node/npm...' -ForegroundColor Cyan
    & $voltaExe setup | Out-Host
    & $voltaExe install node@$NodeVersion npm@$NpmVersion | Out-Host
    $env:PATH = "$voltaBin;$env:PATH"
  }

  $nodeV = Get-CommandVersion 'node' '-v'
  $npmV = Get-CommandVersion 'npm' '-v'
  $nodeOk = $nodeV -match '^v20\.11\.1$'
  $npmOk = $npmV -match '^10\.'

  if (-not ($nodeOk -and $npmOk) -and (Get-Command nvm -ErrorAction SilentlyContinue)) {
    Write-Host '[WEB] Falling back to nvm-windows...' -ForegroundColor Cyan
    nvm install $NodeVersion | Out-Host
    nvm use $NodeVersion | Out-Host
    npm i -g npm@$NpmVersion | Out-Host
    $nodeV = Get-CommandVersion 'node' '-v'
    $npmV = Get-CommandVersion 'npm' '-v'
    $nodeOk = $nodeV -match '^v20\.11\.1$'
    $npmOk = $npmV -match '^10\.'
  }

  if (-not ($nodeOk -and $npmOk)) {
    throw "Web runtime still unsupported (node=$nodeV npm=$npmV). Install Volta and run: volta install node@$NodeVersion npm@$NpmVersion"
  }

  Write-Host "[WEB] Runtime fixed: node $nodeV, npm $npmV" -ForegroundColor Green
}

if (-not (Test-Path $venvPython)) {
  Write-Host '[API] Creating virtual environment...' -ForegroundColor Yellow
  if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv (Join-Path $apiDir '.venv')
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv (Join-Path $apiDir '.venv')
  } else {
    throw 'Python not found. Install Python 3 and ensure py/python is on PATH.'
  }
}

Write-Host '[API] Installing dependencies...' -ForegroundColor Yellow
& $venvPython -m pip install -r (Join-Path $apiDir 'requirements.txt') | Out-Host

Ensure-WebRuntime

if ($RuntimeCheckOnly) {
  Write-Host '[WEB] Runtime check completed. Exiting due to -RuntimeCheckOnly.' -ForegroundColor Green
  exit 0
}

function Invoke-CmdChecked {
  param(
    [Parameter(Mandatory=$true)][string]$Command,
    [string]$ErrorMessage = 'Command failed'
  )
  Invoke-Expression $Command | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "$ErrorMessage (exit=$LASTEXITCODE): $Command"
  }
}

function Stop-WebNodeProcesses {
  param([string]$RepoPath)
  try {
    $procs = Get-CimInstance Win32_Process | Where-Object {
      $_.Name -match '^node(\.exe)?$' -and $_.CommandLine -and $_.CommandLine.ToLower().Contains($RepoPath.ToLower())
    }
    foreach($p in $procs){
      Write-Host "[WEB] Stopping stale node process PID $($p.ProcessId)" -ForegroundColor Yellow
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
  } catch {}
}

Write-Host '[WEB] Installing npm dependencies (deterministic npm ci)...' -ForegroundColor Yellow
Push-Location $webDir
if (-not (Test-Path (Join-Path $webDir 'package-lock.json'))) {
  Write-Host '[WEB] package-lock.json missing, generating lockfile with npm install once...' -ForegroundColor Yellow
  Invoke-CmdChecked "npm install --no-audit --no-fund" '[WEB] npm install failed'
}

$installed = $false
for ($i=1; $i -le 2 -and -not $installed; $i++) {
  try {
    Invoke-CmdChecked "npm ci --no-audit --no-fund" '[WEB] npm ci failed'
    $installed = $true
  } catch {
    if ($i -eq 1) {
      Write-Host '[WEB] npm ci failed. Attempting lock recovery (stale node process cleanup + retry)...' -ForegroundColor Yellow
      Stop-WebNodeProcesses -RepoPath $root
      Start-Sleep -Seconds 2
    } else {
      Pop-Location
      throw "[WEB] npm ci failed after retry. If EPERM persists, close editors/terminals using apps/web and rerun as Administrator. Details: $($_.Exception.Message)"
    }
  }
}
Pop-Location

# Start API
$apiCmd = "cd /d `"$apiDir`" && set LAKEBASE_BACKEND=duckdb && set APP_ENV=dev && .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $apiCmd -WindowStyle Normal

# Start WEB
$webCmd = "cd /d `"$webDir`" && npm run dev"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $webCmd -WindowStyle Normal

function Wait-Url($url, $label, $timeoutSec = 90) {
  $start = Get-Date
  while (((Get-Date) - $start).TotalSeconds -lt $timeoutSec) {
    try {
      $resp = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 3 -UseBasicParsing
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        Write-Host "[$label] READY -> $url" -ForegroundColor Green
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 800
    }
  }
  Write-Host "[$label] NOT READY within $timeoutSec sec -> $url" -ForegroundColor Red
  return $false
}

$apiReady = Wait-Url 'http://127.0.0.1:8000/admin/bootstrap-status' 'API'
$webReady = Wait-Url 'http://127.0.0.1:3000' 'WEB'

Write-Host ''
if ($apiReady -and $webReady) {
  Write-Host 'Gambill Coaching app is ready to use:' -ForegroundColor Green
  Write-Host '  WEB: http://localhost:3000'
  Write-Host '  API: http://127.0.0.1:8000'
} else {
  Write-Host 'One or more services did not become healthy. Check the opened terminal windows for errors.' -ForegroundColor Yellow
}
