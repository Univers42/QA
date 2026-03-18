#!/bin/bash
# ============================================
# mini-baas — Tenant DB Shell
# ============================================
# Connects interactively to the default PostgreSQL Data Plane.
# Usage: ./scripts/db/tenant-shell.sh
# ============================================

set -e

CONTAINER="baas-tenant-db"
USER="tenant_admin"
DB_NAME="tenant_data"

echo -e "\033[0;34mℹ  Connecting to Default Tenant DB (PostgreSQL) -> \033[1m$DB_NAME\033[0m"

if ! docker ps | grep -q $CONTAINER; then
    echo -e "\033[0;31m✗ Container $CONTAINER is not running.\033[0m"
    exit 1
fi

docker exec -it -u postgres $CONTAINER psql -U $USER -d $DB_NAME