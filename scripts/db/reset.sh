#!/bin/bash
# ============================================
# mini-baas — Data Reset
# ============================================
# Destroys all data volumes (Control Plane + Data Plane + Cache).
# Usage: ./scripts/db/reset.sh
# ============================================

echo -e "\033[0;31m⚠  WARNING: This will DESTROY all Master Documents and Tenant Data.\033[0m"
read -p "Are you sure you want to nuke the databases? [y/N] " confirm

if [[ "$confirm" != "y" ]]; then
    echo "Aborted."
    exit 0
fi

echo -e "\033[0;34mℹ  Stopping containers...\033[0m"
docker compose -f docker-compose.dev.yml down

echo -e "\033[0;34mℹ  Deleting volumes...\033[0m"
docker volume rm minibaas_mongo-data 2>/dev/null || true
docker volume rm minibaas_pg-data 2>/dev/null || true
docker volume rm minibaas_redis-data 2>/dev/null || true

echo -e "\033[0;32m✓  Data reset complete. Run 'make dev' to start fresh.\033[0m"