#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORT_DIR="${REPO_ROOT}/audit/maintenance"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
REPORT_FILE="${REPORT_DIR}/workspace-maintenance-${TIMESTAMP}.md"

mkdir -p "${REPORT_DIR}"

section() {
  printf '\n## %s\n\n' "$1" >>"${REPORT_FILE}"
}

run_step() {
  local title="$1"
  shift

  section "${title}"
  printf '```text\n' >>"${REPORT_FILE}"
  "$@" >>"${REPORT_FILE}" 2>&1
  local exit_code=$?
  printf '\n[exit code: %s]\n' "${exit_code}" >>"${REPORT_FILE}"
  printf '```\n' >>"${REPORT_FILE}"

  return "${exit_code}"
}

safe_cleanup() {
  find "${REPO_ROOT}" -name .DS_Store -not -path "${REPO_ROOT}/.git/*" -print -delete
  find "${REPO_ROOT}/backend/app" "${REPO_ROOT}/backend/tests" -type d -name __pycache__ -prune -print -exec rm -rf {} +
  if [[ -d "${REPO_ROOT}/frontend/.next" ]]; then
    rm -rf "${REPO_ROOT}/frontend/.next"
    printf '%s\n' "Removed frontend/.next"
  fi
}

main() {
  cd "${REPO_ROOT}" || exit 1

  cat >"${REPORT_FILE}" <<EOF
# HotClaw Workspace Maintenance

- Time: $(date '+%Y-%m-%d %H:%M:%S %Z')
- Repository: ${REPO_ROOT}

EOF

  run_step "Git Status Before Cleanup" git status --short --branch

  section "Safe Cleanup"
  printf '```text\n' >>"${REPORT_FILE}"
  safe_cleanup >>"${REPORT_FILE}" 2>&1
  printf '```\n' >>"${REPORT_FILE}"

  run_step "Git Status After Cleanup" git status --short --branch

  if [[ -d "${REPO_ROOT}/frontend" ]]; then
    run_step "Frontend Type Check" bash -lc 'cd frontend && npm run lint'
  fi

  if [[ -x "${REPO_ROOT}/backend/.venv/bin/python" ]]; then
    run_step "Backend Tests" bash -lc 'backend/.venv/bin/python -m pytest backend/tests'
  elif command -v python3 >/dev/null 2>&1; then
    run_step "Backend Tests" bash -lc 'cd backend && python3 -m pytest tests'
  else
    section "Backend Tests"
    printf 'Python was not found; skipped backend tests.\n' >>"${REPORT_FILE}"
  fi

  section "Final Safe Cleanup"
  printf '```text\n' >>"${REPORT_FILE}"
  safe_cleanup >>"${REPORT_FILE}" 2>&1
  printf '```\n' >>"${REPORT_FILE}"

  run_step "Final Git Status" git status --short --branch

  printf '%s\n' "${REPORT_FILE}"
}

main "$@"
