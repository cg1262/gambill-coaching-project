@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Gambill Coaching Project launcher (Windows)
REM Starts API + Web in separate terminal windows.

set ROOT=%~dp0
set API_DIR=%ROOT%apps\api
set WEB_DIR=%ROOT%apps\web

if not exist "%API_DIR%" (
  echo [ERROR] API directory not found: %API_DIR%
  exit /b 1
)

if not exist "%WEB_DIR%" (
  echo [ERROR] Web directory not found: %WEB_DIR%
  exit /b 1
)

echo Starting Gambill Coaching app...

REM --- API bootstrap ---
if not exist "%API_DIR%\.venv\Scripts\python.exe" (
  echo [API] Creating virtual environment...
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    py -3 -m venv "%API_DIR%\.venv"
  ) else (
    python -m venv "%API_DIR%\.venv"
  )
)

echo [API] Installing dependencies...
"%API_DIR%\.venv\Scripts\python.exe" -m pip install -r "%API_DIR%\requirements.txt"

REM --- Web bootstrap ---
if not exist "%WEB_DIR%\node_modules" (
  echo [WEB] Installing npm dependencies...
  pushd "%WEB_DIR%"
  npm install
  popd
)

REM Start API in a new window
start "Coaching API" cmd /k "cd /d "%API_DIR%" && set LAKEBASE_BACKEND=duckdb && set APP_ENV=dev && .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"

REM Start Web in a new window
start "Coaching Web" cmd /k "cd /d "%WEB_DIR%" && npm run dev"

echo.
echo Launched:
echo   API: http://127.0.0.1:8000
echo   WEB: http://localhost:3000
echo.
echo Use Ctrl+C in each window to stop services.

endlocal
