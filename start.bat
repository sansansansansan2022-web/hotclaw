@echo off
chcp 65001 >nul
title HotClaw - Multi-Agent Content Platform

echo ============================================
echo   HotClaw - Pixel Editorial Office
echo ============================================
echo.

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

:: Install frontend dependencies
echo [2/4] Installing frontend dependencies...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    call npm install
) else (
    echo   node_modules exists, skipping npm install.
)

:: Start backend
echo [3/4] Starting backend server on http://localhost:8000 ...
cd /d "%~dp0backend"
start "HotClaw Backend" cmd /k ".venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend
echo [4/4] Starting frontend server on http://localhost:3000 ...
cd /d "%~dp0frontend"
start "HotClaw Frontend" cmd /k "npm run dev"

:: Wait for frontend to start
timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo   HotClaw is running!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo Press any key to open the browser...
pause >nul
start http://localhost:3000
