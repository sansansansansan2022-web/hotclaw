@echo off
cd /d %~dp0
echo Starting HotClaw backend on port 8001...
echo Applying backend database migrations...
.venv\Scripts\python.exe -m alembic upgrade head
if %errorlevel% neq 0 exit /b 1
.venv\Scripts\python.exe -m alembic stamp head
if %errorlevel% neq 0 exit /b 1
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
