#!/bin/bash
# ============================================
# mini-baas — Doctor (Environment Check)
# Usage: make doctor
# ============================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

print_header "🩺 mini-baas Environment Check"

WARNINGS=0
ERRORS=0

check_command() {
    local cmd="$1"
    local name="$2"
    local required="${3:-yes}"
    
    if command -v "$cmd" &> /dev/null; then
        VERSION=$($cmd --version 2>&1 | head -n 1)
        printf "${GREEN}✓${NC} %-15s %s\n" "$name:" "$VERSION"
    else
        if [ "$required" = "yes" ]; then
            printf "${RED}✗${NC} %-15s Not installed (required)\n" "$name:"
            ERRORS=$((ERRORS + 1))
        else
            printf "${YELLOW}○${NC} %-15s Not installed (optional)\n" "$name:"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
}

log "Required Tools (Host):"
check_command docker "Docker" yes
check_command git "Git" yes
check_command make "Make" yes

echo ""
log "Optional Tools (Host):"
check_command node "Node.js" no
check_command pnpm "pnpm" no

echo ""
log "Project Files:"

cd "$PROJECT_ROOT"

check_file() {
    local file="$1"
    local name="$2"
    local required="${3:-yes}"
    
    if [ -f "$file" ]; then
        printf "${GREEN}✓${NC} %-30s exists\n" "$name:"
    else
        if [ "$required" = "yes" ]; then
            printf "${RED}✗${NC} %-30s missing\n" "$name:"
            ERRORS=$((ERRORS + 1))
        else
            printf "${YELLOW}○${NC} %-30s not found (optional)\n" "$name:"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
}

check_file "app/package.json" "app package.json" yes
check_file "app/.env.example" "Env template" yes
check_file "docker-compose.dev.yml" "Docker compose (Dev)" yes
check_file "Makefile" "Makefile" yes

# Check for .env 
if [ -f "app/.env" ]; then
    printf "${GREEN}✓${NC} %-30s found\n" ".env file:"
else
    printf "${RED}✗${NC} %-30s missing (Run 'cp app/.env.example app/.env')\n" ".env file:"
    ERRORS=$((ERRORS + 1))
fi

# Ensure no Prisma pollution
if [ -d "app/prisma" ] || grep -q "prisma" "app/package.json" 2>/dev/null; then
    printf "${RED}✗${NC} %-30s Found! Must be removed for App Factory architecture.\n" "Prisma traces:"
    ERRORS=$((ERRORS + 1))
fi

echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    print_ok "Environment is healthy and ready for the App Factory! ✨"
elif [ $ERRORS -eq 0 ]; then
    print_warn "$WARNINGS warning(s) found"
else
    print_fail "$ERRORS error(s) and $WARNINGS warning(s) found"
    exit 1
fi