#!/bin/bash
# ==========================================
# mini-baas — Code Quality Check
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Default path for the new architecture
BACKEND_PATH="$SCRIPT_DIR/../app"

function check_code_quality() {
    log_section "CODE QUALITY CHECK"
    print_header "📝 CODE QUALITY CHECK (App Factory Edition)"
    reset_counters

    # 1. ESLint Configuration
    echo ""
    echo "1️⃣  ESLint Configuration"
    log_subsection "1. Linting"
    if [[ -f "$BACKEND_PATH/eslint.config.mjs" ]] || [[ -f "$BACKEND_PATH/.eslintrc.js" ]] || [[ -f "$BACKEND_PATH/.eslintrc.json" ]]; then
        print_ok "ESLint configured"
        log_pass "ESLint configuration found"
        count_pass
    else
        print_error "ESLint not configured"
        log_fail "No ESLint configuration"
        count_fail
    fi

    # 2. Architectural Integrity (No Prisma allowed)
    echo ""
    echo "2️⃣  Architectural Integrity (Zero Static Models)"
    log_subsection "2. Architecture"
    
    if grep -q "@prisma/client\|prisma" "$BACKEND_PATH/package.json" 2>/dev/null; then
        print_error "Prisma detected in package.json! (Violates App Factory pattern)"
        log_fail "Prisma dependency found"
        count_fail
    else
        print_ok "No Prisma dependencies found (Dynamic engine safe)"
        log_pass "Zero static ORM dependencies"
        count_pass
    fi

    if [[ -f "$BACKEND_PATH/src/common/interfaces/database-adapter.interface.ts" ]]; then
        print_ok "Universal Database Adapter interface found"
        log_pass "IDatabaseAdapter exists"
        count_pass
    else
        print_error "Missing IDatabaseAdapter interface in common/interfaces/"
        log_fail "Core adapter interface missing"
        count_fail
    fi

    # 3. TypeScript Strict Mode
    echo ""
    echo "3️⃣  TypeScript Configuration"
    log_subsection "3. TypeScript Strictness"
    
    if grep -q "\"strict\": true" "$BACKEND_PATH/tsconfig.json" 2>/dev/null; then
        print_ok "TypeScript strict mode enabled"
        log_pass "Strict mode enabled"
        count_pass
    else
        print_warn "Consider enabling TypeScript strict mode"
        log_warn "Strict mode not enabled"
        count_warn
    fi

    # 4. Dependency Injection Patterns
    echo ""
    echo "4️⃣  Dependency Injection"
    log_subsection "4. DI Patterns"
    
    local injectable_count
    injectable_count=$(grep -r "@Injectable" "$BACKEND_PATH/src" --include="*.ts" 2>/dev/null | wc -l)
    if [[ $injectable_count -gt 0 ]]; then
        print_ok "Proper DI with @Injectable ($injectable_count services)"
        log_pass "DI pattern followed"
        count_pass
    fi

    # 5. Code Organization (Domain Driven Design)
    echo ""
    echo "5️⃣  Code Organization"
    log_subsection "5. Project Structure"
    
    local module_count
    module_count=$(find "$BACKEND_PATH/src" -name "*.module.ts" 2>/dev/null | wc -l)
    
    if [[ -d "$BACKEND_PATH/src/modules/control-plane" ]] && [[ -d "$BACKEND_PATH/src/modules/data-plane" ]]; then
        print_ok "Control/Data Plane structure verified"
        log_pass "DDD structure applied"
        count_pass
    else
        print_warn "Missing Control/Data plane directories in src/modules/"
        log_warn "DDD structure incomplete"
        count_warn
    fi

    # 6. Technical Debt Tracking
    echo ""
    echo "6️⃣  TODO/FIXME Tracking"
    log_subsection "6. Technical Debt"
    
    local todo_count
    todo_count=$(grep -r "TODO\|FIXME\|XXX\|HACK" "$BACKEND_PATH/src" --include="*.ts" 2>/dev/null | wc -l)
    if [[ $todo_count -gt 0 ]]; then
        print_warn "Found $todo_count TODO/FIXME comments"
        log_warn "Technical debt markers: $todo_count"
        count_warn
    else
        print_ok "No TODO/FIXME comments"
        log_pass "No technical debt markers"
        count_pass
    fi

    print_summary
    log_end_section
    print_verbose
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_code_quality
fi
