@echo off
setlocal

set ROOT=%~dp0
set API_DIR=%ROOT%apps\api
set WEB_DIR=%ROOT%apps\web

echo Starting Data Modeling IDE demo stack...

if not exist "%API_DIR%\.venv" (
  echo Creating API virtual environment...
  cd /d "%API_DIR%"
  python -m venv .venv
)

echo Installing API dependencies...
cd /d "%API_DIR%"
call .venv\Scripts\python.exe -m pip install -r requirements.txt

if not exist "%WEB_DIR%\node_modules" (
  echo Installing Web dependencies...
  cd /d "%WEB_DIR%"
  call npm install
)

start "API" cmd /k "cd /d "%API_DIR%" && .venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"
start "Web" cmd /k "cd /d "%WEB_DIR%" && npm run dev"

echo.
echo Demo services launched:
echo   API: http://localhost:8000/health
echo   Web: http://localhost:3000

echo.
echo Press any key to exit this launcher...
pause > nul
