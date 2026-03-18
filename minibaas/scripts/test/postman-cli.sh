#!/usr/bin/env bash
# **************************************************************************** #
#   postman-cli.sh - Official Postman CLI Integration                          #
# **************************************************************************** #

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR/..")"
POSTMAN_DIR="$PROJECT_ROOT/backend/test/postman"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default values
BASE_URL="${API_URL:-http://localhost:3000/api}"

print_header() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║          📮 Postman CLI - API Integration Runner             ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_usage() {
    cat << 'EOF'
Usage: ./scripts/test/postman-cli.sh [COMMAND] [OPTIONS]

Official Postman CLI integration for running collections against mini-baas.

COMMANDS:
    install             Install Postman CLI
    login               Login to Postman (opens browser)
    run COLLECTION_ID   Run a collection from Postman Cloud
    run-local FILE      Run a local collection file
    list                List local collections
    help                Show this help
EOF
}

check_postman_cli() {
    if ! command -v postman &> /dev/null; then
        echo -e "${YELLOW}Postman CLI not found.${NC}"
        echo "Install with: ./scripts/test/postman-cli.sh install"
        exit 1
    fi
}

install_postman_cli() {
    echo -e "${BLUE}▶ Installing Postman CLI...${NC}"
    if command -v postman &> /dev/null; then
        echo -e "${GREEN}✓ Postman CLI already installed${NC}"
        return 0
    fi
    
    case "$(uname -s)" in
        Linux*)  curl -o- "[https://dl-cli.pstmn.io/install/linux64.sh](https://dl-cli.pstmn.io/install/linux64.sh)" | sh ;;
        Darwin*) curl -o- "[https://dl-cli.pstmn.io/install/osx_64.sh](https://dl-cli.pstmn.io/install/osx_64.sh)" | sh ;;
        *) echo -e "${RED}Unsupported OS.${NC}"; exit 1 ;;
    esac
    echo -e "${GREEN}✓ Postman CLI installed${NC}"
}

postman_login() {
    check_postman_cli
    echo -e "${BLUE}▶ Logging into Postman...${NC}"
    postman login
}

run_collection_cloud() {
    local collection_id="$1"
    check_postman_cli
    if [[ -z "$collection_id" ]]; then
        echo -e "${RED}Error: Collection ID required${NC}"; exit 1
    fi
    
    local cmd="postman collection run $collection_id --global-var baseUrl=$BASE_URL"
    echo -e "${CYAN}$ $cmd${NC}"
    eval "$cmd"
}

run_collection_local() {
    local file="$1"
    check_postman_cli
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}Error: File not found: $file${NC}"; exit 1
    fi
    
    local cmd="postman collection run $file --global-var baseUrl=$BASE_URL"
    echo -e "${CYAN}$ $cmd${NC}"
    eval "$cmd"
}

list_collections() {
    echo -e "${CYAN}Local collections in this repo:${NC}"
    if [ -d "$POSTMAN_DIR" ]; then
        find "$POSTMAN_DIR" -name "*.json" -not -name "env.*" | while read -r file; do
            echo "  - $(basename "$file")"
        done
    else
        echo "  No collections found in $POSTMAN_DIR"
    fi
}

# Parse command
COMMAND="${1:-help}"
shift 2>/dev/null || true

print_header

case "$COMMAND" in
    install)   install_postman_cli ;;
    login)     postman_login ;;
    run)       run_collection_cloud "$@" ;;
    run-local) run_collection_local "$@" ;;
    list)      list_collections ;;
    *)         print_usage ;;
esac