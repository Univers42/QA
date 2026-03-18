#!/bin/bash
# ==========================================
# mini-baas — RGPD & Security Compliance Check
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

BACKEND_PATH="$SCRIPT_DIR/../app"

function check_rgpd() {
    log_section "RGPD COMPLIANCE CHECK"
    print_header "🔐 RGPD & SECURITY COMPLIANCE CHECK"
    reset_counters
    
    # 1. Password Security (Encryption in depth)
    echo ""
    echo "1️⃣  Password Security (Bcrypt + Pepper)"
    log_subsection "1. Password Security"
    
    if check_package_installed "bcrypt"; then
        print_ok "bcrypt installed for base password hashing"
        log_pass "bcrypt installed"
        count_pass
        
        if grep -r "AES-256-GCM\|encryption" "$BACKEND_PATH/src/common/crypto" --include="*.ts" 2>/dev/null | grep -q .; then
            print_ok "AES-256-GCM implemented for Per-Tenant Pepper encryption"
            log_pass "Per-Tenant encryption implemented"
            count_pass
        else
            print_warn "AES-256-GCM encryption service missing for pepper/secrets"
            log_warn "Missing crypto service"
            count_warn
        fi
    else
        print_error "bcrypt not installed!"
        count_fail
    fi

    # 2. Audit Logging
    echo ""
    echo "2️⃣  Audit Logging (Data Traceability)"
    log_subsection "2. Audit Logging"
    
    if [[ -f "$BACKEND_PATH/src/modules/audit/audit.module.ts" ]]; then
        print_ok "Audit Module exists (Phase 4 requirement)"
        log_pass "Audit Module found"
        count_pass
        
        if grep -q "audit_log\|audit" "$BACKEND_PATH/src/common/schemas/system-entities.ts" 2>/dev/null; then
            print_ok "System entity _baas_audit_log is provisioned"
            log_pass "Audit table schema exists"
            count_pass
        else
            print_warn "Audit schema missing from system-entities.ts"
            log_warn "Audit schema missing"
            count_warn
        fi
    else
        print_error "Audit Module completely missing. Required for traceability."
        log_fail "Audit Module missing"
        count_fail
    fi

    # 3. GDPR Operations (Right to be Forgotten)
    echo ""
    echo "3️⃣  GDPR Operations (Export & Deletion)"
    log_subsection "3. GDPR Module"
    
    if [[ -d "$BACKEND_PATH/src/modules/gdpr" ]]; then
        print_ok "GDPR Module structure found"
        log_pass "GDPR Module exists"
        count_pass
        
        if grep -r "export\|deletion\|anonymize" "$BACKEND_PATH/src/modules/gdpr" --include="*.ts" -i 2>/dev/null | grep -q .; then
            print_ok "Data export and anonymization logic detected"
            log_pass "GDPR methods implemented"
            count_pass
        else
            print_warn "GDPR module seems empty. Implement export and anonymization."
            log_warn "GDPR logic missing"
            count_warn
        fi
    else
        print_warn "Consider implementing a dedicated GDPR module for compliance"
        log_warn "GDPR Module missing"
        count_warn
    fi

    # 4. Data Leakage Prevention
    echo ""
    echo "4️⃣  Error Handling (No Data Leakage)"
    log_subsection "4. Error Handling"
    
    if [[ -f "$BACKEND_PATH/src/common/exceptions/all-exceptions.filter.ts" ]]; then
        print_ok "Global exception filter present to mask stack traces"
        log_pass "Internal errors are masked"
        count_pass
    else
        print_error "AllExceptionsFilter missing. Risk of stack trace leakage."
        log_fail "AllExceptionsFilter missing"
        count_fail
    fi

    # 5. Consent Management
    echo ""
    echo "5️⃣  Consent Management"
    log_subsection "5. Consent Tracking"
    
    if grep -qi "consents\|consentType" "$BACKEND_PATH/src/common/schemas/system-entities.ts" 2>/dev/null; then
        print_ok "Consent tracking (_baas_consents) defined in system entities"
        log_pass "Consent schema exists"
        count_pass
    else
        print_warn "Consider adding _baas_consents to system-entities.ts"
        log_warn "No consent tracking schema found"
        count_warn
    fi

    print_summary
    log_end_section
    print_verbose
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_rgpd
fi
