#!/usr/bin/env bash
# Resolves the selected environment URL and executes the reusable header and
# cookie assertion script with the configured cookie names.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

TARGET="${TEST_ENV:-preview}"
URL=""
declare -a COOKIE_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  bash trascendence_testing/scripts/run-http-surface.sh [--target local|dev|preview|staging] [--url URL]
                                                        [--cookie-name NAME]
EOF
}

while (($#)); do
  case "$1" in
    --target)
      shift
      TARGET="${1:-}"
      ;;
    --url)
      shift
      URL="${1:-}"
      ;;
    --cookie-name)
      shift
      COOKIE_ARGS+=(--cookie-name "${1:-}")
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

ensure_command curl

if [[ -z "$URL" ]]; then
  URL="$(resolve_target_url "$TARGET")"
fi

[[ -n "$URL" ]] || fail "No URL configured for target '$TARGET'."

if ((${#COOKIE_ARGS[@]} == 0)); then
  IFS=',' read -r -a cookie_names <<<"$(cookie_names_from_env)"
  for cookie_name in "${cookie_names[@]}"; do
    [[ -n "$cookie_name" ]] || continue
    COOKIE_ARGS+=(--cookie-name "$cookie_name")
  done
fi

log_step "Checking headers and cookies for $URL"
bash "$TT_DIR/scripts/check-http-surface.sh" "${COOKIE_ARGS[@]}" "$URL"
