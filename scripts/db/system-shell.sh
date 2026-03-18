#!/bin/bash
# ============================================
# mini-baas — Control Plane DB Shell
# ============================================
# Connects interactively to the MongoDB system database.
# Usage: ./scripts/db/system-shell.sh
# ============================================

set -e

CONTAINER="baas-system-db"
DB_NAME="mini_baas_control"

echo -e "\033[0;34mℹ  Connecting to Control Plane (MongoDB) -> \033[1m$DB_NAME\033[0m"

# Check if container is running
if ! docker ps | grep -q $CONTAINER; then
    echo -e "\033[0;31m✗ Container $CONTAINER is not running. Run 'make docker-up'.\033[0m"
    exit 1
fi

# Execute mongosh inside the container
docker exec -it $CONTAINER mongosh "mongodb://localhost:27117/$DB_NAME"