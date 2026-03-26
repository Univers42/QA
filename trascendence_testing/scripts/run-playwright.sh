#!/usr/bin/env bash
# Launches the Playwright smoke suite for the selected environment, reusing the
# module configuration and optional grep filters.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"

TARGET="${TEST_ENV:-local}"
GREP=""
HEADED=0

usage() {
  cat <<'EOF'
Usage:
  bash trascendence_testing/scripts/run-playwright.sh [--target local|dev|preview|staging]
                                                     [--grep REGEX] [--headed]
EOF
}

while (($#)); do
  case "$1" in
    --target)
      shift
      TARGET="${1:-}"
      ;;
    --grep)
      shift
      GREP="${1:-}"
      ;;
    --headed)
      HEADED=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
  shift
done

ensure_command npm

PLAYWRIGHT_BIN="$TT_DIR/node_modules/.bin/playwright"
[[ -x "$PLAYWRIGHT_BIN" ]] || fail "Playwright is not installed. Run: make tt-install"

BASE_URL="$(resolve_target_url "$TARGET")"
[[ -n "$BASE_URL" ]] || fail "No URL configured for target '$TARGET'. Update .env.example variables in your local .env."

export TT_BASE_URL="$BASE_URL"
export PLAYWRIGHT_BASE_URL="$BASE_URL"
export PLAYWRIGHT_BROWSERS_PATH=0

CMD=("$PLAYWRIGHT_BIN" test "tests/smoke")

if [[ -n "$GREP" ]]; then
  CMD+=(--grep "$GREP")
fi

if (( HEADED )); then
  CMD+=(--headed)
fi

log_step "Running Playwright smoke checks against $BASE_URL"
(
  cd "$TT_DIR"
  "${CMD[@]}"
)
