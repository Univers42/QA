#!/bin/bash
# ==========================================
# mini-baas — Docker Infrastructure Check
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

function check_docker() {
    log_section "DOCKER & INFRASTRUCTURE CHECK"
    print_header "🐳 DOCKER & INFRASTRUCTURE (App Factory Edition)"
    reset_counters

    # 1. Docker Service
    echo ""
    echo "1️⃣  Docker Service"
    log_subsection "1. Docker Daemon"
    
    if docker info &>/dev/null; then
        print_ok "Docker daemon is running"
        log_pass "Docker daemon running"
        count_pass
    else
        print_error "Docker daemon not running"
        log_fail "Docker daemon not running"
        count_fail
        return 1
    fi

    # 2. Running Containers
    echo ""
    echo "2️⃣  Running Containers"
    log_subsection "2. Container Status"
    
    local container_count
    container_count=$(docker ps -q --filter "name=baas-" 2>/dev/null | wc -l)
    
    if [[ $container_count -ge 3 ]]; then
        print_ok "$container_count BaaS containers running"
        log_pass "Containers running: $container_count"
        count_pass
    else
        print_warn "Missing expected containers (Engine, System DB, Tenant DB, Cache)"
        log_warn "Only $container_count containers running"
        count_warn
    fi

    # 3. System Database (MongoDB)
    echo ""
    echo "3️⃣  Control Plane Database (MongoDB)"
    log_subsection "3. System DB"
    
    if docker inspect -f '{{.State.Running}}' baas-system-db 2>/dev/null | grep -q "true"; then
        print_ok "baas-system-db is running"
        log_pass "MongoDB running"
        count_pass
    else
        print_error "baas-system-db not running. Engine will crash."
        log_fail "MongoDB not running"
        count_fail
    fi

    # 4. Tenant Database (PostgreSQL)
    echo ""
    echo "4️⃣  Default Tenant Database (PostgreSQL)"
    log_subsection "4. Tenant DB"
    
    if docker inspect -f '{{.State.Running}}' baas-tenant-db 2>/dev/null | grep -q "true"; then
        print_ok "baas-tenant-db is running"
        log_pass "PostgreSQL running"
        count_pass
    else
        print_warn "baas-tenant-db not running. SQL tenants will fail."
        log_warn "PostgreSQL not running"
        count_warn
    fi

    # 5. Cache (Redis)
    echo ""
    echo "5️⃣  Cache Layer (Redis)"
    log_subsection "5. Cache"
    
    if docker inspect -f '{{.State.Running}}' baas-redis 2>/dev/null | grep -q "true"; then
        print_ok "baas-redis is running"
        log_pass "Redis running"
        count_pass
    else
        print_error "baas-redis not running. Metadata cache will fail."
        log_fail "Redis not running"
        count_fail
    fi

    # 6. Disk Space
    echo ""
    echo "6️⃣  Disk Space"
    log_subsection "6. Storage"
    
    local disk_usage
    disk_usage=$(df -h . | tail -1 | awk '{print $5}')
    local disk_percent
    disk_percent=$(echo "$disk_usage" | tr -d '%')
    
    if [[ $disk_percent -lt 80 ]]; then
        print_ok "Disk usage: $disk_usage"
        log_pass "Disk usage OK: $disk_usage"
        count_pass
    elif [[ $disk_percent -lt 90 ]]; then
        print_warn "Disk usage high: $disk_usage"
        log_warn "Disk usage high: $disk_usage"
        count_warn
    else
        print_error "Disk usage critical: $disk_usage"
        log_fail "Disk usage critical: $disk_usage"
        count_fail
    fi

    print_summary
    log_end_section
    print_verbose
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_docker
fi
