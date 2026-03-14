param(
  [switch]$RuntimeCheckOnly
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root 'apps/api'
$webDir = Join-Path $root 'apps/web'
$venvPython = Join-Path $apiDir '.venv/Scripts/python.exe'

Write-Host 'Starting Gambill Coaching app with health checks...' -ForegroundColor Cyan

$launchStartedAt = Get-Date
$stageTimings = [ordered]@{}

function Invoke-TimedStage {
  param(
    [Parameter(Mandatory=$true)][string]$Label,
    [Parameter(Mandatory=$true)][scriptblock]$Action
  )

  Write-Host "[$Label] Starting..." -ForegroundColor DarkCyan
  $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    & $Action
  } finally {
    $stopwatch.Stop()
    $elapsedSeconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 1)
    $stageTimings[$Label] = $elapsedSeconds
    Write-Host "[$Label] Finished in ${elapsedSeconds}s" -ForegroundColor DarkCyan
  }
}

function Write-LaunchTimingSummary {
  $totalSeconds = [Math]::Round(((Get-Date) - $launchStartedAt).TotalSeconds, 1)
  Write-Host ''
  Write-Host 'Launch timing summary:' -ForegroundColor Cyan
  foreach ($entry in $stageTimings.GetEnumerator()) {
    Write-Host ("  {0}: {1}s" -f $entry.Key, $entry.Value)
  }
  Write-Host ("  TOTAL: {0}s" -f $totalSeconds) -ForegroundColor Cyan
}

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
    throw "Web runtime still unsupported (node=$nodeV npm=$npmV). Run 'npm --prefix apps/web run runtime:doctor' for exact remediation, then install Volta and run: volta install node@$NodeVersion npm@$NpmVersion"
  }

  Write-Host "[WEB] Runtime fixed: node $nodeV, npm $npmV" -ForegroundColor Green
}

Invoke-TimedStage 'API venv check' {
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
}

function Get-RequirementsHash {
  param([string]$RequirementsPath)
  $bytes = [System.IO.File]::ReadAllBytes($RequirementsPath)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $hashBytes = $sha.ComputeHash($bytes)
  return ([System.BitConverter]::ToString($hashBytes) -replace '-', '').ToLower()
}

$reqFile = Join-Path $apiDir 'requirements.txt'
$hashFile = Join-Path $apiDir '.pip-installed-hash'
$currentHash = Get-RequirementsHash -RequirementsPath $reqFile
$cachedHash = if (Test-Path $hashFile) { (Get-Content $hashFile -Raw).Trim() } else { '' }

Invoke-TimedStage 'API dependency check' {
  if ($currentHash -eq $cachedHash) {
    Write-Host '[API] Dependencies up to date (hash match). Skipping pip install.' -ForegroundColor Green
  } else {
    Write-Host '[API] Installing dependencies (requirements.txt changed)...' -ForegroundColor Yellow
    & $venvPython -m pip install -r $reqFile | Out-Host
    if ($LASTEXITCODE -eq 0) {
      Set-Content -Path $hashFile -Value $currentHash -NoNewline
      Write-Host '[API] Dependencies installed and hash cached.' -ForegroundColor Green
    } else {
      throw '[API] pip install failed'
    }
  }
}

Invoke-TimedStage 'WEB runtime check' {
  Ensure-WebRuntime
}

if ($RuntimeCheckOnly) {
  Write-Host '[WEB] Runtime check completed. Exiting due to -RuntimeCheckOnly.' -ForegroundColor Green
  Write-LaunchTimingSummary
  exit 0
}

function Invoke-CmdChecked {
  param(
    [Parameter(Mandatory=$true)][string]$Command,
    [string]$ErrorMessage = 'Command failed'
  )
  # Use & operator to avoid Invoke-Expression injection risk
  $tokens = $Command -split '\s+', 2
  $exe = $tokens[0]
  $argStr = if ($tokens.Length -gt 1) { $tokens[1] } else { '' }
  if ($argStr) {
    & $exe ($argStr -split '\s+') | Out-Host
  } else {
    & $exe | Out-Host
  }
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

function Repair-WebNodeModulesLock {
  param([string]$WebPath)
  $targets = @(
    (Join-Path $WebPath 'node_modules\next\node_modules\@next\swc-win32-x64-msvc\next-swc.win32-x64-msvc.node'),
    (Join-Path $WebPath 'node_modules\next\node_modules\@next\swc-win32-x64-msvc')
  )

  foreach($t in $targets){
    try {
      if (Test-Path $t) {
        attrib -R $t 2>$null | Out-Null
        Remove-Item -LiteralPath $t -Force -Recurse -ErrorAction SilentlyContinue
        Write-Host "[WEB] Removed stale lock target: $t" -ForegroundColor Yellow
      }
    } catch {}
  }
}

Invoke-TimedStage 'WEB dependency check' {
  Write-Host '[WEB] Installing npm dependencies (deterministic npm ci)...' -ForegroundColor Yellow
  Push-Location $webDir
  try {
    $webLockFile = Join-Path $webDir 'package-lock.json'
    $webHashFile = Join-Path $webDir '.npm-installed-hash'
    $webModulesDir = Join-Path $webDir 'node_modules'

    if (-not (Test-Path $webLockFile)) {
      Write-Host '[WEB] package-lock.json missing, generating lockfile with npm install once...' -ForegroundColor Yellow
      Invoke-CmdChecked "npm install --no-audit --no-fund" '[WEB] npm install failed'
    }

    $currentWebHash = Get-RequirementsHash -RequirementsPath $webLockFile
    $cachedWebHash = if (Test-Path $webHashFile) { (Get-Content $webHashFile -Raw).Trim() } else { '' }
    $webInstallRequired = (-not (Test-Path $webModulesDir)) -or ($currentWebHash -ne $cachedWebHash)

    if (-not $webInstallRequired) {
      Write-Host '[WEB] Dependencies up to date (lock hash match). Skipping npm ci.' -ForegroundColor Green
    } else {
      $installed = $false
      for ($i=1; $i -le 3 -and -not $installed; $i++) {
        try {
          Invoke-CmdChecked "npm ci --no-audit --no-fund" '[WEB] npm ci failed'
          $installed = $true
          Set-Content -Path $webHashFile -Value $currentWebHash -NoNewline
          Write-Host '[WEB] Dependencies installed and hash cached.' -ForegroundColor Green
        } catch {
          if ($i -lt 3) {
            Write-Host "[WEB] npm ci attempt $i failed. Attempting lock recovery before retry..." -ForegroundColor Yellow
            Stop-WebNodeProcesses -RepoPath $root
            Repair-WebNodeModulesLock -WebPath $webDir
            Start-Sleep -Seconds 3
          } else {
            throw "[WEB] npm ci failed after 3 attempts. If EPERM persists, temporarily exclude this repo path from AV real-time scan and rerun PowerShell as Administrator. Details: $($_.Exception.Message)"
          }
        }
      }
    }
  } finally {
    Pop-Location
  }
}

# Start API
$apiCmd = "cd /d `"$apiDir`" && set LAKEBASE_BACKEND=duckdb && set APP_ENV=dev && .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"
Invoke-TimedStage 'API process launch' {
  Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $apiCmd -WindowStyle Normal
}

# Start WEB
$webCmd = "cd /d `"$webDir`" && npm run dev"
Invoke-TimedStage 'WEB process launch' {
  Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $webCmd -WindowStyle Normal
}

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

$apiReady = $false
$webReady = $false

Invoke-TimedStage 'API readiness wait' {
  $script:apiReady = Wait-Url 'http://127.0.0.1:8000/admin/bootstrap-status' 'API'
}

Invoke-TimedStage 'WEB readiness wait' {
  $script:webReady = Wait-Url 'http://127.0.0.1:3000' 'WEB'
}

Write-Host ''
if ($apiReady -and $webReady) {
  Write-Host 'Gambill Coaching app is ready to use:' -ForegroundColor Green
  Write-Host '  WEB: http://localhost:3000'
  Write-Host '  API: http://127.0.0.1:8000'
} else {
  Write-Host 'One or more services did not become healthy. Check the opened terminal windows for errors.' -ForegroundColor Yellow
}

Write-LaunchTimingSummary
