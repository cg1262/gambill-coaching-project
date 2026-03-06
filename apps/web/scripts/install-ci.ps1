$ErrorActionPreference = 'Stop'

function Remove-PathSafe([string]$path) {
  if (Test-Path $path) {
    try {
      attrib -R $path 2>$null | Out-Null
      Remove-Item -Recurse -Force $path -ErrorAction Stop
    } catch {
      cmd /c "attrib -R /S /D `"$path`"" | Out-Null
      cmd /c "rmdir /s /q `"$path`"" | Out-Null
    }
  }
}

function Stop-WebNodeProcesses([string]$workspacePath) {
  try {
    $normalized = $workspacePath.ToLower()
    $procs = Get-CimInstance Win32_Process | Where-Object {
      $_.Name -match '^node(\.exe)?$' -and $_.CommandLine -and $_.CommandLine.ToLower().Contains($normalized)
    }
    foreach ($p in $procs) {
      Write-Host "[install:ci] stopping stale node process PID $($p.ProcessId)"
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
  } catch {}
}

function Invoke-NpmCi() {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $output = cmd /c "npm ci --no-audit --no-fund" 2>&1
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  $output | ForEach-Object { Write-Host $_ }
  return @{ Output = $output; Code = $code }
}

function Needs-WindowsRecovery([string]$text) {
  if ($text -match 'EPERM') { return $true }
  if ($text -match 'ENOTEMPTY') { return $true }
  if ($text -match 'EISDIR') { return $true }
  if ($text -match '@next\\swc-win32-x64-msvc') { return $true }
  return $false
}

$attempt = 1
while ($attempt -le 3) {
  Write-Host "[install:ci] npm ci attempt $attempt/3"
  $res = Invoke-NpmCi
  if ($res.Code -eq 0) {
    Write-Host '[install:ci] npm ci succeeded'
    exit 0
  }

  $buildText = ($res.Output -join "`n")
  if ($attempt -lt 3 -and (Needs-WindowsRecovery $buildText)) {
    Write-Warning '[install:ci] detected recoverable Windows install corruption (EPERM/ENOTEMPTY/EISDIR). Removing locked SWC artifacts and retrying.'
    Stop-WebNodeProcesses (Get-Location).Path
    Remove-PathSafe 'node_modules\@next\swc-win32-x64-msvc'
    Remove-PathSafe 'node_modules\next\node_modules\@next\swc-win32-x64-msvc'
    Start-Sleep -Seconds 2
    $attempt += 1
    continue
  }

  Write-Error '[install:ci] npm ci failed and was not recoverable by SWC cleanup.'
  exit $res.Code
}
