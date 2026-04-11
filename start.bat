@echo off
chcp 65001 >nul
title HotClaw - Multi-Agent Content Platform

echo ============================================
echo   HotClaw - Pixel Editorial Office
echo ============================================
echo.

set "API_ORIGIN=http://127.0.0.1:8000"
set "HOTCLAW_API_ORIGIN=%API_ORIGIN%"
set "NEXT_PUBLIC_HOTCLAW_API_ORIGIN=%API_ORIGIN%"

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+.
    pause
    exit /b 1
)

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+.
    pause
    exit /b 1
)

:: Install backend dependencies
echo [1/4] Installing backend dependencies...
cd /d "%~dp0backend"
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -e ".[dev]" -q 2>nul
if %errorlevel% neq 0 (
    echo [WARN] pip install had warnings, continuing...
)
echo   Applying backend database migrations...
python -m alembic upgrade head
if %errorlevel% neq 0 (
    echo [ERROR] alembic upgrade head failed.
    pause
    exit /b 1
)
python -m alembic stamp head
if %errorlevel% neq 0 (
    echo [ERROR] alembic stamp head failed.
    pause
    exit /b 1
)

:: Install frontend dependencies
echo [2/4] Installing frontend dependencies...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    call npm install
) else (
    echo   node_modules exists, skipping npm install.
)

:: Start backend
echo [3/4] Starting backend server on %API_ORIGIN% ...
cd /d "%~dp0backend"
start "HotClaw Backend" cmd /k ".venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait for backend health check so frontend rewrite/direct origin is ready
echo   Waiting for backend health endpoint...
set "BACKEND_READY="
for /l %%I in (1,1,30) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { $response = Invoke-WebRequest -UseBasicParsing '%API_ORIGIN%/api/v1/health' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } } catch { }; exit 1" >nul 2>&1
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto backend_ready
    )
    timeout /t 1 /nobreak >nul
)

:backend_ready
if not defined BACKEND_READY (
    echo [WARN] Backend health check did not respond within 30 seconds. Frontend will still be started.
)

:: Start frontend
echo [4/4] Starting frontend server on http://localhost:3000 ...
cd /d "%~dp0frontend"
start "HotClaw Frontend" cmd /k "npm run dev"

:: Wait for frontend to start
timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo   HotClaw is running!
echo   Backend:  %API_ORIGIN%
echo   Frontend: http://localhost:3000
echo   API Docs: %API_ORIGIN%/docs
echo ============================================
echo.
echo Press any key to open the browser...
pause >nul
start http://localhost:3000
