#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
FRONTEND_DIR="${REPO_ROOT}/frontend"

BACKEND_PORT="${HOTCLAW_BACKEND_PORT:-8000}"
FRONTEND_PORT="${HOTCLAW_FRONTEND_PORT:-3000}"
FRONTEND_MODE="${HOTCLAW_FRONTEND_MODE:-auto}"
API_ORIGIN="${HOTCLAW_API_ORIGIN:-http://127.0.0.1:${BACKEND_PORT}}"
API_ORIGIN="${API_ORIGIN%/}"

export HOTCLAW_API_ORIGIN="${API_ORIGIN}"
export NEXT_PUBLIC_HOTCLAW_API_ORIGIN="${API_ORIGIN}"
export HOTCLAW_AUTO_CREATE_TABLES="${HOTCLAW_AUTO_CREATE_TABLES:-0}"
export HOTCLAW_ENABLE_SCHEDULER="${HOTCLAW_ENABLE_SCHEDULER:-0}"
export NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"
export PYTHONUNBUFFERED=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\n==> %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found: $1" >&2
    exit 1
  fi
}

cleanup() {
  local exit_code=$?
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID}" ]]; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

wait_for_http() {
  local url="$1"
  local attempts="${2:-45}"
  local sleep_seconds="${3:-2}"
  local i
  for ((i = 1; i <= attempts; i += 1)); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_seconds}"
  done
  return 1
}

prepare_backend() {
  log "Preparing backend"
  cd "${BACKEND_DIR}"
  if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -e ".[dev]"
  python -m alembic upgrade head
}

prepare_frontend() {
  log "Preparing frontend"
  cd "${FRONTEND_DIR}"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
}

start_backend() {
  log "Starting backend on ${API_ORIGIN}"
  cd "${BACKEND_DIR}"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_PORT}" &
  BACKEND_PID=$!

  if ! wait_for_http "${API_ORIGIN}/api/v1/health" 45 2; then
    echo "[ERROR] Backend health check failed at ${API_ORIGIN}/api/v1/health" >&2
    exit 1
  fi
}

resolve_frontend_command() {
  cd "${FRONTEND_DIR}"

  case "${FRONTEND_MODE}" in
    dev)
      echo "npx next dev -H 0.0.0.0 -p ${FRONTEND_PORT}"
      return 0
      ;;
    start)
      npm run build
      echo "npx next start -H 0.0.0.0 -p ${FRONTEND_PORT}"
      return 0
      ;;
    auto)
      if npm run build; then
        echo "npx next start -H 0.0.0.0 -p ${FRONTEND_PORT}"
      else
        echo "[WARN] Frontend production build failed, falling back to dev mode." >&2
        echo "npx next dev -H 0.0.0.0 -p ${FRONTEND_PORT}"
      fi
      return 0
      ;;
    *)
      echo "[ERROR] Unsupported HOTCLAW_FRONTEND_MODE: ${FRONTEND_MODE}" >&2
      exit 1
      ;;
  esac
}

start_frontend() {
  local frontend_command
  frontend_command="$(resolve_frontend_command)"
  log "Starting frontend on 0.0.0.0:${FRONTEND_PORT}"
  cd "${FRONTEND_DIR}"
  bash -lc "${frontend_command}" &
  FRONTEND_PID=$!
}

main() {
  require_command python3
  require_command node
  require_command npm
  require_command curl

  prepare_backend
  prepare_frontend
  start_backend
  start_frontend

  cat <<EOF

============================================
HotClaw is running in DevBox mode
Frontend public port: ${FRONTEND_PORT}
Backend internal origin: ${API_ORIGIN}
Frontend local URL: http://127.0.0.1:${FRONTEND_PORT}
Backend docs: ${API_ORIGIN}/docs
Expose only port ${FRONTEND_PORT} in Sealos DevBox.
============================================

EOF

  wait -n "${BACKEND_PID}" "${FRONTEND_PID}"
}

main "$@"
