#!/bin/bash
# ============================================
# mini-baas — Seed Control Plane
# ============================================
# Injects a test Master Document into MongoDB.
# Usage: ./scripts/db/seed-control-plane.sh
# ============================================
set -e

CONTAINER="baas-system-db"
DB_NAME="mini_baas_control"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║  🧠  mini-baas — Seed Control Plane      ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

if ! docker ps | grep -q $CONTAINER; then
    echo -e "${RED}✗ Container $CONTAINER is not running. Run 'make docker-up'.${NC}"
    exit 1
fi

echo -e "${CYAN}ℹ Injecting test tenant 'vite-gourmand' into MongoDB...${NC}"

# We use mongosh inside the container to insert the Master Document
docker exec -i $CONTAINER mongosh "mongodb://localhost:27117/$DB_NAME" --quiet <<EOF
db.tenantmetadata.deleteMany({ tenantId: "vite-gourmand" });
db.tenantmetadata.insertOne({
  tenantId: "vite-gourmand",
  status: "active",
  database: {
    engine: "mongodb",
    uri: "mongodb://baas-system-db:27117/tenant_vite_gourmand"
  },
  schema: {
    books: {
      fields: {
        title: { type: "string" },
        price: { type: "number" }
      }
    }
  },
  version: 1,
  createdAt: new Date(),
  updatedAt: new Date()
});
EOF

echo -e "${GREEN}✓ Control Plane seeded successfully!${NC}"
echo -e "  Tenant ID: ${BOLD}vite-gourmand${NC}"
echo -e "  Engine:    ${BOLD}mongodb${NC}"