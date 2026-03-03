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

Write-Host "[build-clean] removing .next and ts build artifacts"
Remove-PathSafe ".next"
Remove-PathSafe "tsconfig.tsbuildinfo"

Write-Host "[build-clean] running next build"
$buildOutput = & npm run build 2>&1
$buildOutput | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -eq 0) {
  Write-Host "[build-clean] build succeeded"
  exit 0
}

if (($buildOutput -join "`n") -match "EISDIR") {
  Write-Warning "[build-clean] detected EISDIR during build; rebuilding node_modules and retrying once"
  Remove-PathSafe "node_modules"
  & npm install --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Remove-PathSafe ".next"
  & npm run build
  exit $LASTEXITCODE
}

exit $LASTEXITCODE
