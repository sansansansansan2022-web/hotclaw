#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_ORIGIN="${HOTCLAW_API_ORIGIN:-${NEXT_PUBLIC_HOTCLAW_API_ORIGIN:-http://127.0.0.1:8000}}"
API_ORIGIN="${API_ORIGIN%/}"

export HOTCLAW_API_ORIGIN="$API_ORIGIN"
export NEXT_PUBLIC_HOTCLAW_API_ORIGIN="$API_ORIGIN"

echo "============================================"
echo "  HotClaw - Pixel Editorial Office"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 not found. Please install Python 3.11+."
    exit 1
fi

# Check Node.js
if ! command -v node &>/dev/null; then
    echo "[ERROR] Node.js not found. Please install Node.js 18+."
    exit 1
fi

# Install backend dependencies
echo "[1/4] Installing backend dependencies..."
cd "$SCRIPT_DIR/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -e ".[dev]" -q 2>/dev/null || echo "[WARN] pip install had warnings, continuing..."
echo "  Applying backend database migrations..."
python3 -m alembic upgrade head
python3 -m alembic stamp head

# Install frontend dependencies
echo "[2/4] Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "  node_modules exists, skipping npm install."
fi

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down HotClaw..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend
echo "[3/4] Starting backend server on $API_ORIGIN ..."
cd "$SCRIPT_DIR/backend"
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend
echo "  Waiting for backend health endpoint..."
BACKEND_READY=0
for _ in $(seq 1 30); do
    if curl -fsS "$API_ORIGIN/api/v1/health" >/dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
    echo "[WARN] Backend health check did not respond within 30 seconds. Frontend will still be started."
fi

# Start frontend
echo "[4/4] Starting frontend server on http://localhost:3000 ..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================"
echo "  HotClaw is running!"
echo "  Backend:  $API_ORIGIN"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: $API_ORIGIN/docs"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop all services."

# Wait for both processes
wait
