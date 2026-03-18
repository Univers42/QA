#!/bin/bash
# ============================================
# mini-baas — Check HTTP Security Headers
# Usage: ./scripts/security/headers.sh [URL]
# ============================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

print_header "🛡️  Security Headers Check"

# Default to the health endpoint of our BaaS
URL="${1:-http://localhost:3000/health}"

log "Checking security headers for: ${CYAN}$URL${NC}"
echo ""

# Fetch headers
HEADERS=$(curl -sI "$URL" 2>/dev/null || { print_error "Cannot connect to $URL"; exit 1; })

echo "$HEADERS" | head -n 10
echo ""

# Check important headers (These will be implemented via Helmet in main.ts)
declare -A SECURITY_HEADERS=(
    ["Strict-Transport-Security"]="HSTS - Enforces HTTPS"
    ["X-Content-Type-Options"]="Prevents MIME sniffing"
    ["X-Frame-Options"]="Prevents clickjacking"
    ["X-XSS-Protection"]="XSS filter (legacy)"
    ["Content-Security-Policy"]="CSP - Controls resource loading"
    ["Referrer-Policy"]="Controls referrer information"
)

log "Security Header Analysis:"
echo ""

for header in "${!SECURITY_HEADERS[@]}"; do
    if echo "$HEADERS" | grep -qi "^$header:"; then
        VALUE=$(echo "$HEADERS" | grep -i "^$header:" | cut -d':' -f2- | tr -d '\r')
        printf "${GREEN}✓${NC} %-30s ${CYAN}%s${NC}\n" "$header:" "$VALUE"
    else
        printf "${RED}✗${NC} %-30s ${YELLOW}Missing${NC} - %s\n" "$header:" "${SECURITY_HEADERS[$header]}"
    fi
done