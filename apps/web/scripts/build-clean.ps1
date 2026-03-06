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

function Get-NodeVersionString() {
  if ($env:npm_node_execpath -and (Test-Path $env:npm_node_execpath)) {
    return (& $env:npm_node_execpath -v) 2>$null
  }
  return (node -v) 2>$null
}

function Print-VersionGuidance() {
  $nodeVersion = Get-NodeVersionString
  $npmVersion = (npm -v) 2>$null
  Write-Host "[build-clean] detected node=$nodeVersion npm=$npmVersion"
  Write-Host "[build-clean] required baseline: Node >=20.11.1 <21 and npm 10.x"
}

function Assert-RuntimeParity() {
  $nodeRaw = Get-NodeVersionString
  $npmRaw = (npm -v) 2>$null
  $node = [regex]::Match([string]$nodeRaw, '(\d+)\.(\d+)\.(\d+)')
  $npm = [regex]::Match([string]$npmRaw, '(\d+)\.(\d+)\.(\d+)')
  if (!$node.Success -or !$npm.Success) {
    Write-Error "[build-clean] unable to parse Node/npm versions. Install Node 20.11.1 + npm 10.x, then rerun."
    exit 1
  }

  $nodeMajor = [int]$node.Groups[1].Value
  $nodeMinor = [int]$node.Groups[2].Value
  $nodePatch = [int]$node.Groups[3].Value
  $npmMajor = [int]$npm.Groups[1].Value

  $nodeOk = $nodeMajor -eq 20 -and ($nodeMinor -gt 11 -or ($nodeMinor -eq 11 -and $nodePatch -ge 1))
  $npmOk = $npmMajor -eq 10
  if (!$nodeOk -or !$npmOk) {
    Write-Error "[build-clean] runtime mismatch (detected node=$nodeRaw npm=$npmRaw)."
    Write-Error "[build-clean] this mismatch is a known trigger for persistent EISDIR/readlink failures in Next build paths."
    Write-Error "[build-clean] switch to Node 20.11.1 (see .nvmrc) + npm 10.x, then run: npm ci --no-audit --no-fund; npm run typecheck; npm run build"
    exit 1
  }
}

function Ensure-Lockfile() {
  if (!(Test-Path "package-lock.json")) {
    Write-Error "[build-clean] package-lock.json is required for deterministic recovery. Run npm install once to generate and commit lockfile."
  }
}

function Assert-SourcePathIntegrity() {
  $expectedFiles = @(
    "src/app/page.tsx",
    "src/app/layout.tsx",
    "src/app/intake/page.tsx",
    "src/app/review/page.tsx",
    "src/app/project/[id]/page.tsx"
  )

  foreach ($path in $expectedFiles) {
    if ((Test-Path $path -PathType Container)) {
      Write-Error "[build-clean] source path corruption detected: '$path' is a directory but must be a file. Restore from git and rerun."
      exit 1
    }
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
  if ($text -match "EPERM") { return $true }
  if ($text -match "operation not permitted") { return $true }
  if ($text -match "(tsc|next)\s*(is not recognized|not found|cannot find)") { return $true }
  if ($text -match "Cannot find module 'next'") { return $true }
  if ($text -match "Cannot find module 'typescript'") { return $true }
  return $false
}

Print-VersionGuidance
Assert-RuntimeParity
Ensure-Lockfile
Assert-SourcePathIntegrity

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
  Write-Warning "[build-clean] detected recoverable build failure (EISDIR/EPERM/missing local binaries). Rebuilding node_modules with npm ci and retrying once."
  Remove-PathSafe "node_modules"
  Remove-PathSafe ".next"
  Remove-PathSafe "tsconfig.tsbuildinfo"
  Remove-PathSafe "node_modules\next\node_modules\@next\swc-win32-x64-msvc"

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
