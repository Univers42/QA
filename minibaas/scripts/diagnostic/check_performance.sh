#!/bin/bash
# ==========================================
# mini-baas — Performance Check
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

BACKEND_PATH="$SCRIPT_DIR/../app"

function check_performance() {
    log_section "PERFORMANCE CHECK"
    print_header "⚡ PERFORMANCE CHECK (App Factory Edition)"
    reset_counters

    # 1. Connection Pooling
    echo ""
    echo "1️⃣  Database Connection Pooling"
    log_subsection "1. Connection Pool Configuration"
    
    if grep -r "pool: {" "$BACKEND_PATH/src/modules/engines" --include="*.ts" 2>/dev/null | grep -q .; then
        print_ok "Connection pool configured in Engine Adapters (Knex/Mongo)"
        log_pass "Adapter pooling found"
        count_pass
    else
        print_warn "Verify connection pooling in IDatabaseAdapter implementations"
        log_warn "Pooling configuration not explicitly found in engines"
        count_warn
    fi

    # 2. Caching Strategy
    echo ""
    echo "2️⃣  Caching Strategy"
    log_subsection "2. Caching"
    
    if grep -q "ioredis\|redis" "$BACKEND_PATH/package.json" 2>/dev/null; then
        print_ok "Redis installed for Tenant Metadata caching"
        log_pass "Redis cache installed"
        count_pass
    else
        print_warn "Redis missing! Crucial for resolving Master Documents efficiently"
        log_warn "No Redis dependencies found"
        count_warn
    fi

    # 3. Response Compression
    echo ""
    echo "3️⃣  Response Compression"
    log_subsection "3. Compression"
    
    if grep -q "compression" "$BACKEND_PATH/package.json" 2>/dev/null; then
        print_ok "Compression middleware installed"
        log_pass "Compression installed"
        count_pass
    else
        print_warn "Consider adding compression for large JSON payload responses"
        log_warn "No compression middleware"
        count_warn
    fi

    # 4. JSON Validation Engine Speed
    echo ""
    echo "4️⃣  Validation Engine Optimization"
    log_subsection "4. AJV Runtime Validation"
    
    if grep -q "ajv" "$BACKEND_PATH/package.json" 2>/dev/null; then
        print_ok "AJV installed for high-performance schema validation"
        log_pass "AJV installed"
        count_pass
        
        if grep -r "Map<" "$BACKEND_PATH/src/modules/data-plane/validation" --include="*.ts" 2>/dev/null | grep -q .; then
             print_ok "Compiled schema caching implemented in Validation Engine"
             log_pass "AJV compiled schemas are cached"
             count_pass
        fi
    else
        print_warn "AJV missing. Dynamic payload validation will be slow or unsafe"
        log_warn "No high-performance JSON schema validator found"
        count_warn
    fi

    # 5. Memory Management (Node & Docker)
    echo ""
    echo "5️⃣  Memory Configuration"
    log_subsection "5. Resource Limits"
    
    # Check for hooks memory protection
    if grep -q "isolated-vm" "$BACKEND_PATH/package.json" 2>/dev/null; then
        print_ok "isolated-vm installed to prevent tenant hooks from crashing Node"
        log_pass "V8 Sandboxing installed"
        count_pass
    else
        print_warn "isolated-vm not found. Running tenant hooks natively is a massive memory/security risk."
        log_warn "No V8 sandboxing found"
        count_warn
    fi
    
    # Check Docker Compose resource limits
    local compose_file="$SCRIPT_DIR/../docker-compose.yml"
    if [[ -f "$compose_file" ]]; then
        if grep -q "maxmemory" "$compose_file" 2>/dev/null; then
            print_ok "Redis memory evictions limits configured in compose"
            log_pass "Redis limits set"
            count_pass
        fi
    fi

    # 6. Response Time Monitoring
    echo ""
    echo "6️⃣  Performance Monitoring"
    log_subsection "6. Observability"
    
    if grep -r "Interceptor" "$BACKEND_PATH/src/common/interceptors" --include="*.ts" 2>/dev/null | grep -i -q "time\|duration\|perf"; then
        print_ok "Response time logging interceptor found"
        log_pass "Performance logging implemented"
        count_pass
    else
        print_warn "Consider adding an interceptor to measure P95 latency per tenant"
        log_warn "No explicit timing metrics found"
        count_warn
    fi

    print_summary
    log_end_section
    print_verbose
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_performance
fi
