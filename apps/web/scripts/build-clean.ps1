$ErrorActionPreference = 'Stop'

function Remove-PathSafe([string]$path) {
  if (Test-Path $path) {
    try {
      Remove-Item -Recurse -Force $path
    } catch {
      cmd /c "rmdir /s /q `"$path`"" | Out-Null
    }
  }
}

function Print-VersionGuidance() {
  $nodeVersion = (node -v) 2>$null
  $npmVersion = (npm -v) 2>$null
  Write-Host "[build-clean] detected node=$nodeVersion npm=$npmVersion"
  Write-Host "[build-clean] guidance: use Node 20.x LTS (or newer patched LTS compatible with Next 14) and npm 10.x for deterministic installs"
}

function Ensure-Lockfile() {
  if (!(Test-Path "package-lock.json")) {
    Write-Error "[build-clean] package-lock.json is required for deterministic recovery. Run npm install once to generate and commit lockfile."
  }
}

function Invoke-Build() {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $output = cmd /c "npm run build" 2>&1
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev

  $output | ForEach-Object { Write-Host $_ }
  return @{ Output = $output; Code = $code }
}

function Needs-ModuleRecovery([string]$text) {
  if ($text -match "EISDIR") { return $true }
  if ($text -match "(tsc|next)\s*(is not recognized|not found|cannot find)") { return $true }
  if ($text -match "Cannot find module 'next'") { return $true }
  if ($text -match "Cannot find module 'typescript'") { return $true }
  return $false
}

Print-VersionGuidance
Ensure-Lockfile

Write-Host "[build-clean] removing .next and ts build artifacts"
Remove-PathSafe ".next"
Remove-PathSafe "tsconfig.tsbuildinfo"

Write-Host "[build-clean] running next build"
$buildRes = Invoke-Build
if ($buildRes.Code -eq 0) {
  Write-Host "[build-clean] build succeeded"
  exit 0
}

$buildText = ($buildRes.Output -join "`n")
if (Needs-ModuleRecovery $buildText) {
  Write-Warning "[build-clean] detected recoverable build failure (EISDIR/missing local binaries). Rebuilding node_modules with npm ci and retrying once."
  Remove-PathSafe "node_modules"
  Remove-PathSafe ".next"
  Remove-PathSafe "tsconfig.tsbuildinfo"

  & npm ci --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) {
    Write-Error "[build-clean] npm ci failed. Check lockfile integrity and Node/npm versions."
    exit $LASTEXITCODE
  }

  $retryRes = Invoke-Build
  if ($retryRes.Code -ne 0) {
    Write-Error "[build-clean] retry failed after module recovery. If persistent, clear npm cache (npm cache verify) and re-run under stable local disk context."
    exit $retryRes.Code
  }

  Write-Host "[build-clean] build succeeded after recovery"
  exit 0
}

exit $buildRes.Code
