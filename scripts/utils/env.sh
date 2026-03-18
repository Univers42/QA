#!/bin/bash
# ============================================
# mini-baas — Environment Variables Helper
# ============================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

print_header "🔧 Environment Variables Audit"

cd "$PROJECT_ROOT"

ACTION="${1:-check}"

case "$ACTION" in
    show)
        log "Environment files found:"
        
        if [ -f "$ENV_FILE" ]; then
            echo ""
            log "=== $ENV_FILE ==="
            while IFS='=' read -r key value || [ -n "$key" ]; do
                [[ "$key" =~ ^#.*$ ]] && continue
                [[ -z "$key" ]] && continue
                
                if [[ "$key" =~ (PASSWORD|SECRET|KEY|TOKEN) ]]; then
                    echo "  $key=***masked***"
                else
                    if [ ${#value} -gt 50 ]; then
                        echo "  $key=${value:0:47}..."
                    else
                        echo "  $key=$value"
                    fi
                fi
            done < "$ENV_FILE"
        else
            print_error "No .env file found in $BACKEND_PATH"
        fi
        ;;
        
    check)
        log "Checking required App Factory variables..."
        
        REQUIRED=(
            "MONGODB_URI"
            "MONGODB_DB_NAME"
            "REDIS_HOST"
            "REDIS_PORT"
            "MASTER_ENCRYPTION_KEY"
            "NODE_ENV"
        )
        
        echo ""
        log "Required for Control Plane & Engine:"
        for var in "${REQUIRED[@]}"; do
            if grep -qE "^$var=" "$ENV_FILE" 2>/dev/null; then
                printf "${GREEN}✓${NC} %s is set\n" "$var"
            else
                printf "${RED}✗${NC} %s is missing\n" "$var"
            fi
        done
        
        # Specific check for encryption key length (crucial for AES-256)
        KEY_VAL=$(grep -E "^MASTER_ENCRYPTION_KEY=" "$ENV_FILE" 2>/dev/null | cut -d '=' -f2-)
        if [ -n "$KEY_VAL" ] && [ ${#KEY_VAL} -ne 64 ]; then
            echo ""
            print_warn "MASTER_ENCRYPTION_KEY is not 64 characters (32 bytes hex)!"
            log "Generate a correct one with: openssl rand -hex 32"
        fi
        ;;
        
    *)
        log "Usage: ./scripts/utils/env.sh [show|check]"
        exit 1
        ;;
esac