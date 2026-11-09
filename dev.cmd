@echo off
rem Run Django (backend) and Vite (frontend) together. Press Ctrl+C to stop both.
rem PowerShell: .\dev.cmd   Git Bash: ./dev.cmd   Django port: set DJANGO_PORT (default 8001)
setlocal
cd /d "%~dp0"
if not defined DJANGO_PORT set DJANGO_PORT=8001
where npm >nul 2>nul || set "PATH=%USERPROFILE%\node;%PATH%"

if not exist backend\.venv\Scripts\pip.exe (
  echo [setup] creating backend virtualenv...
  python -m venv backend\.venv || exit /b 1
)
rem Install on every run: quick when nothing changed, and picks up requirements/lock changes.
backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || exit /b 1
call npm install --prefix frontend --no-audit --no-fund || exit /b 1
backend\.venv\Scripts\python backend\manage.py migrate --noinput -v 0 || exit /b 1

echo.
echo   App:   http://localhost:5173
echo   Admin: http://localhost:5173/club-admin/
echo   Stop:  Ctrl+C
echo.
start "" /b backend\.venv\Scripts\python backend\manage.py runserver %DJANGO_PORT%
set DJANGO_URL=http://127.0.0.1:%DJANGO_PORT%
cd frontend
call npm run dev
