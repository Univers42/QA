#!/usr/bin/env bash
# Shared shell helpers for the Transcendence testing wrappers, including
# logging, command checks, environment target resolution, and cookie defaults.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TT_DIR="$ROOT_DIR/trascendence_testing"

log_step() {
  printf '[trascendence_testing] %s\n' "$*"
}

fail() {
  printf '[trascendence_testing] ERROR: %s\n' "$*" >&2
  exit 1
}

ensure_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

resolve_target_url() {
  local target="${1:-${TEST_ENV:-local}}"
  case "$target" in
    local)
      printf '%s\n' "${TT_BASE_URL:-${PLAYWRIGHT_BASE_URL:-${FRONTEND_URL:-http://127.0.0.1:5173}}}"
      ;;
    dev)
      printf '%s\n' "${TT_DEV_URL:-${TT_BASE_URL:-${PLAYWRIGHT_BASE_URL:-${FRONTEND_URL:-}}}}"
      ;;
    preview)
      printf '%s\n' "${TT_PREVIEW_URL:-}"
      ;;
    staging)
      printf '%s\n' "${TT_STAGING_URL:-}"
      ;;
    *)
      fail "Unsupported target '$target'. Allowed: local, dev, preview, staging"
      ;;
  esac
}

cookie_names_from_env() {
  local raw="${TT_COOKIE_NAMES:-sb-access-token,sb-refresh-token,auth-token,session}"
  local cleaned="${raw// /}"
  printf '%s\n' "$cleaned"
}
