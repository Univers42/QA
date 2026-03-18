#!/bin/bash
# ============================================
# mini-baas — Check for Secrets in Code
# Usage: ./scripts/security/secrets.sh
# ============================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

print_header "🔍 Scanning for Secrets in Code"

cd "$PROJECT_ROOT"

FOUND_ISSUES=0

# Patterns to search for (Updated for App Factory)
PATTERNS=(
    "password\s*=\s*['\"][^'\"]+['\"]"
    "secret\s*=\s*['\"][^'\"]+['\"]"
    "api_key\s*=\s*['\"][^'\"]+['\"]"
    "MASTER_ENCRYPTION_KEY\s*=\s*['\"][^'\"]+['\"]"
    "JWT_SECRET\s*=\s*['\"][^'\"]+['\"]"
    "token\s*=\s*['\"][^'\"]+['\"]"
    "aws_access_key_id"
    "aws_secret_access_key"
)

log "Scanning source files for potential hardcoded secrets..."

for pattern in "${PATTERNS[@]}"; do
    RESULTS=$(grep -rniE "$pattern" backend/src \
        --include="*.ts" --include="*.js" \
        --exclude-dir=node_modules --exclude-dir=dist \
        --exclude="*.spec.ts" --exclude="*.test.ts" 2>/dev/null || true)
    
    if [ -n "$RESULTS" ]; then
        print_warn "Pattern '$pattern' found:"
        echo "$RESULTS"
        echo ""
        FOUND_ISSUES=1
    fi
done

# Check for .env files that might be committed
log "Checking for .env files in git..."
if git ls-files --error-unmatch backend/.env 2>/dev/null; then
    print_error "CRITICAL: backend/.env is tracked by git!"
    FOUND_ISSUES=1
fi

if [ $FOUND_ISSUES -eq 0 ]; then
    print_ok "No obvious hardcoded secrets found in code!"
else
    print_warn "Review the findings above for potential security leaks."
    # We don't exit 1 here so we don't break CI unnecessarily on false positives,
    # but the warning is highly visible.
fi