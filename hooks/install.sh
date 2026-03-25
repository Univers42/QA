#!/bin/bash
# ── Prismatica QA · Install Git Hooks ──────────────────────
# Points git to hooks/ and verifies permissions.
# Run once after clone, or via: make hooks

set -e

HOOK_DIR="hooks"

echo ""
echo -e "  \033[0;34m── Installing Git Hooks ──\033[0m"
echo ""

# Verify hook files exist
if [ ! -f "${HOOK_DIR}/pre-commit" ]; then
    echo -e "  \033[0;31m✗\033[0m  Hook files not found in ${HOOK_DIR}/"
    echo -e "  \033[2m  Are you in the repo root?\033[0m"
    exit 1
fi

# Make hooks executable
chmod +x "${HOOK_DIR}/pre-commit"
chmod +x "${HOOK_DIR}/commit-msg"
chmod +x "${HOOK_DIR}/pre-push"
chmod +x "${HOOK_DIR}/log_hook.sh"

# Point git to our hooks directory
git config core.hooksPath "${HOOK_DIR}"

echo -e "  \033[0;32m✓\033[0m  core.hooksPath set to ${HOOK_DIR}/"
echo -e "  \033[0;32m✓\033[0m  pre-commit hook active (file validation)"
echo -e "  \033[0;32m✓\033[0m  commit-msg hook active (conventional commits)"
echo -e "  \033[0;32m✓\033[0m  pre-push hook active (branch protection)"
echo ""
echo -e "  \033[2mBypass variables:\033[0m"
echo -e "  \033[2m  SKIP_PRE_COMMIT=1   skip file checks\033[0m"
echo -e "  \033[2m  SKIP_COMMIT_MSG=1   skip message validation\033[0m"
echo -e "  \033[2m  SKIP_PRE_PUSH=1     skip push protection\033[0m"
echo ""
