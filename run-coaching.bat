@echo off
setlocal

REM Wrapper to run the PowerShell launcher with runtime auto-remediation.
powershell -ExecutionPolicy Bypass -File "%~dp0run-coaching.ps1"
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo [ERROR] run-coaching.ps1 failed with exit code %EXITCODE%.
)

exit /b %EXITCODE%
