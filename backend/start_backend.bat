@echo off
cd /d %~dp0
echo Starting HotClaw backend on port 8001...
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
