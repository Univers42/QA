#!/bin/sh
# ─────────────────────────────────────────────────────────
#  Colored logging utility for git hooks
#  Sourced by all hooks via:  . "$(dirname "$0")/log_hook.sh"
# ─────────────────────────────────────────────────────────

LOG_DIR=".git/hook-logs"
mkdir -p "$LOG_DIR" 2>/dev/null || true

# ANSI color codes
RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

timestamp() {
	date +"%Y-%m-%d %H:%M:%S"
}

_log() {
	# portable: printf handles escape sequences everywhere
	printf "%b\n" "$*" | tee -a "$LOG_DIR/hook.log"
}

_log_err() {
	printf "%b\n" "$*" | tee -a "$LOG_DIR/hook.log" >&2
}

log_hr() {
	_log "${BOLD}──────────────────────────────────────────────────${NC}"
}

log_broadcast() {
	title="$1"
	log_hr
	_log "${GREEN}${BOLD}${title} [$(timestamp)]${NC}"
	log_hr
}

log_info() {
	_log "  ${BLUE}[INFO]${NC} $*"
}

log_error() {
	_log_err "  ${RED}[ERROR]${NC} $*"
}

log_warn() {
	_log "  ${YELLOW}[WARN]${NC} $*"
}

log_success() {
	_log "  ${GREEN}[OK]${NC} $*"
}

log_example() {
	_log "  ${CYAN}[TIP]${NC} $*"
}

log_debug() {
	if [ "${GIT_HOOK_DEBUG:-0}" = "1" ]; then
		_log "  ${DIM}[DEBUG]${NC} $*"
	fi
}

log_hook() {
	hook="$1"
	shift
	_log "  ${GREEN}[$hook]${NC} $*"
}

log_example() {
	/bin/echo -e "  ${BOLD}${GREEN}[EXAMPLE]${NC} $*" | tee -a "$LOG_DIR/hook.log"
}
