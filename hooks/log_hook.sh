#!/bin/bash
# ── Prismatica QA · Hook Logging Utilities ─────────────────
# Sourced by all hooks. Provides colorized output and persistent logging.

HOOK_LOG_DIR=".git/hook-logs"
HOOK_LOG_FILE="${HOOK_LOG_DIR}/hook.log"

mkdir -p "${HOOK_LOG_DIR}"

# Colors
_R='\033[0;31m'    # Red
_G='\033[0;32m'    # Green
_Y='\033[1;33m'    # Yellow
_B='\033[0;34m'    # Blue
_C='\033[0;36m'    # Cyan
_D='\033[2m'       # Dim
_BD='\033[1m'      # Bold
_N='\033[0m'       # Reset

_log_to_file() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "${HOOK_LOG_FILE}"
}

log_broadcast() {
    echo ""
    echo -e "  ${_B}── $1 ──${_N}"
    echo ""
    _log_to_file "=== $1 ==="
}

log_info() {
    echo -e "  ${_B}ℹ${_N}  $1"
    _log_to_file "[INFO] $1"
}

log_error() {
    echo -e "  ${_R}✗${_N}  $1" >&2
    _log_to_file "[ERROR] $1"
}

log_warn() {
    echo -e "  ${_Y}⚠${_N}  $1"
    _log_to_file "[WARN] $1"
}

log_success() {
    echo -e "  ${_G}✓${_N}  $1"
    _log_to_file "[OK] $1"
}

log_example() {
    echo -e "  ${_C}↳${_N}  ${_D}$1${_N}"
}

log_debug() {
    if [ "${GIT_HOOK_DEBUG}" = "1" ]; then
        echo -e "  ${_D}[DEBUG] $1${_N}"
        _log_to_file "[DEBUG] $1"
    fi
}
