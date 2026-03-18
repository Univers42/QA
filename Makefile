# ============================================
# mini-baas — MAKEFILE (App Factory Edition)
# ============================================
# Usage: make <target>
# Run 'make help' to see all available targets
#
# 🐳 FULLY CONTAINERIZED: Only Docker required!
# 🛡️ RESILIENT: Auto-detects docker compose v2 / v1 / podman
# ============================================

SHELL := /bin/bash
.SHELLFLAGS := -ec

# ── BuildKit auto-detection ──────────────────────────
BUILDX_AVAILABLE := $(shell docker buildx version >/dev/null 2>&1 && echo 1 || echo 0)
ifeq ($(BUILDX_AVAILABLE),1)
export DOCKER_BUILDKIT := 1
export COMPOSE_DOCKER_CLI_BUILD := 1
else
export DOCKER_BUILDKIT := 0
export COMPOSE_DOCKER_CLI_BUILD := 0
endif
.PHONY: help
.DEFAULT_GOAL := help

# ── Compose auto-detection ───────────────────────────
COMPOSE_CMD := $(shell \
	if docker compose version >/dev/null 2>&1; then \
		echo 'docker compose'; \
	elif command -v docker-compose >/dev/null 2>&1; then \
		echo 'docker-compose'; \
	elif command -v podman-compose >/dev/null 2>&1; then \
		echo 'podman-compose'; \
	else \
		echo '__NONE__'; \
	fi \
)

# ── Variables ────────────────────────────────────────
COMPOSE_DEV		:= $(COMPOSE_CMD) -f docker-compose.dev.yml
COMPOSE_PROD	:= $(COMPOSE_CMD) -f docker-compose.yml
CONTAINER		:= baas-dev-engine
APP				:= app
FILTER          ?=
LOG_LEVEL       ?= debug
DOCKER_PROGRESS ?= auto
DOCKER_CACHE_ROOT := .docker/buildx-cache
DEV_IMAGE       := mini-baas-dev-engine:local
PROD_IMAGE      := mini-baas-prod-engine:local
DEV_CACHE_DIR   := $(DOCKER_CACHE_ROOT)/dev
PROD_CACHE_DIR  := $(DOCKER_CACHE_ROOT)/prod

ifneq ($(findstring docker compose,$(COMPOSE_CMD)),)
COMPOSE_BUILD_PROGRESS_FLAG := --progress=$(DOCKER_PROGRESS)
else
COMPOSE_BUILD_PROGRESS_FLAG :=
endif

# Colors
BLUE    := \033[0;34m
GREEN   := \033[0;32m
YELLOW  := \033[1;33m
RED     := \033[0;31m
CYAN    := \033[0;36m
NC      := \033[0m
BOLD    := \033[1m
DIM     := \033[2m

# Box drawing
define BANNER
	@echo ""
	@echo -e "$(BLUE)╔══════════════════════════════════════════════════════════╗$(NC)"
	@echo -e "$(BLUE)║$(NC)  ⚙️   $(BOLD)mini-baas$(NC) — The Polyglot App Factory              $(BLUE)║$(NC)"
	@echo -e "$(BLUE)╚══════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
endef

# ── Step decorator ───────────────────────────────────
define step
	@echo -e "  $(1)  $(2)"
endef

# ============================================
#  🛡️ PREFLIGHT CHECKS
# ============================================

.PHONY: check-docker check-compose check-env check-ports preflight

check-docker:
	@command -v docker >/dev/null 2>&1 || { echo -e "$(RED)✗ Docker Engine not found$(NC)"; exit 1; }
	@docker info >/dev/null 2>&1 || { echo -e "$(RED)✗ Docker daemon is not running$(NC)"; exit 1; }

check-compose:
ifeq ($(COMPOSE_CMD),__NONE__)
	@echo -e "$(RED)✗ No Docker Compose tool found$(NC)"
	@exit 1
endif

check-env:
	@if [ ! -f $(APP)/.env ]; then \
		if [ -f $(APP)/.env.example ]; then \
			echo -e "  $(YELLOW)⚠$(NC)  .env not found — creating from .env.example"; \
			cp $(APP)/.env.example $(APP)/.env; \
		else \
			echo -e "$(RED)✗ .env file is missing in $(APP)/$(NC)"; \
			exit 1; \
		fi; \
	fi

check-ports:
	@PORTS="3000 27117 5432 6379 8025"; \
	BLOCKED=""; \
	for p in $$PORTS; do \
		if ss -tlnp 2>/dev/null | grep -q ":$$p "; then \
			BLOCKED="$$BLOCKED $$p"; \
		fi; \
	done; \
	if [ -n "$$BLOCKED" ]; then \
		echo -e "  $(YELLOW)⚠$(NC)  Ports in use:$(BOLD)$$BLOCKED$(NC) (run 'make kill-ports')"; \
	fi

preflight: check-docker check-compose check-env check-ports
	$(call step,$(GREEN)✓,$(BOLD)Preflight checks passed$(NC))

# ============================================
#  ⚡ BOOTSTRAP
# ============================================

.PHONY: all bootstrap banner

all: banner preflight bootstrap dev ## 🚀 Full setup (preflight, bootstrap, start dev server)

update:
	@git submodule update --init --recursive --remote --merge 2>/dev/null || echo "All up to date"

banner:
	$(BANNER)

bootstrap: preflight docker-up install install-hooks typecheck ## ⚡ Initial setup
	@echo -e "$(GREEN)✅ Engine setup & DevOps Shield complete!$(NC)"
	@echo ""
	@echo -e "$(GREEN)╔══════════════════════════════════════════════════════════╗$(NC)"
	@echo -e "$(GREEN)║$(NC)  ✅  $(BOLD)Engine setup complete!$(NC)                            $(GREEN)║$(NC)"
	@echo -e "$(GREEN)╠══════════════════════════════════════════════════════════╣$(NC)"
	@echo -e "$(GREEN)║$(NC)  BaaS API →  http://localhost:3000/health                 $(GREEN)║$(NC)"
	@echo -e "$(GREEN)║$(NC)  Swagger  →  http://localhost:3000/docs                   $(GREEN)║$(NC)"
	@echo -e "$(GREEN)╚══════════════════════════════════════════════════════════╝$(NC)"
	@echo ""

# ============================================
#  🐳 DOCKER
# ============================================

.PHONY: docker-build docker-build-prod docker-up docker-down docker-logs

docker-build: check-compose ## 🐳 Build the dev engine image with cache + timer
	$(call step,$(BLUE)ℹ,Building dev engine image...)
ifeq ($(BUILDX_AVAILABLE),1)
	@mkdir -p $(DOCKER_CACHE_ROOT)
	@start=$$(date +%s); \
	cache_dir="$(DEV_CACHE_DIR)"; \
	cache_new="$(DEV_CACHE_DIR)-new"; \
	cache_from=""; \
	if [ -d "$$cache_dir" ]; then cache_from="--cache-from type=local,src=$$cache_dir"; fi; \
	rm -rf "$$cache_new"; \
	status=0; \
	docker buildx build \
		--load \
		--progress=$(DOCKER_PROGRESS) \
		--file docker/Dockerfile.dev \
		--tag $(DEV_IMAGE) \
		$$cache_from \
		--cache-to type=local,dest=$$cache_new,mode=max \
		. || status=$$?; \
	if [ $$status -eq 0 ]; then \
		rm -rf "$$cache_dir"; \
		mv "$$cache_new" "$$cache_dir"; \
	else \
		rm -rf "$$cache_new"; \
	fi; \
	end=$$(date +%s); \
	elapsed=$$((end - start)); \
	printf "  $(CYAN)⏱$(NC)  Dev image build time: %02dh:%02dm:%02ds\n" $$((elapsed / 3600)) $$(((elapsed % 3600) / 60)) $$((elapsed % 60)); \
	exit $$status
else
	@start=$$(date +%s); \
	status=0; \
	$(COMPOSE_DEV) build $(COMPOSE_BUILD_PROGRESS_FLAG) engine || status=$$?; \
	end=$$(date +%s); \
	elapsed=$$((end - start)); \
	printf "  $(CYAN)⏱$(NC)  Dev image build time: %02dh:%02dm:%02ds\n" $$((elapsed / 3600)) $$(((elapsed % 3600) / 60)) $$((elapsed % 60)); \
	exit $$status
endif

docker-build-prod: check-compose ## 🐳 Build the prod engine image with cache + timer
	$(call step,$(BLUE)ℹ,Building prod engine image...)
ifeq ($(BUILDX_AVAILABLE),1)
	@mkdir -p $(DOCKER_CACHE_ROOT)
	@start=$$(date +%s); \
	cache_dir="$(PROD_CACHE_DIR)"; \
	cache_new="$(PROD_CACHE_DIR)-new"; \
	cache_from=""; \
	if [ -d "$$cache_dir" ]; then cache_from="--cache-from type=local,src=$$cache_dir"; fi; \
	rm -rf "$$cache_new"; \
	status=0; \
	docker buildx build \
		--load \
		--progress=$(DOCKER_PROGRESS) \
		--file docker/Dockerfile.backend \
		--target production \
		--tag $(PROD_IMAGE) \
		$$cache_from \
		--cache-to type=local,dest=$$cache_new,mode=max \
		. || status=$$?; \
	if [ $$status -eq 0 ]; then \
		rm -rf "$$cache_dir"; \
		mv "$$cache_new" "$$cache_dir"; \
	else \
		rm -rf "$$cache_new"; \
	fi; \
	end=$$(date +%s); \
	elapsed=$$((end - start)); \
	printf "  $(CYAN)⏱$(NC)  Prod image build time: %02dh:%02dm:%02ds\n" $$((elapsed / 3600)) $$(((elapsed % 3600) / 60)) $$((elapsed % 60)); \
	exit $$status
else
	@start=$$(date +%s); \
	status=0; \
	$(COMPOSE_PROD) build $(COMPOSE_BUILD_PROGRESS_FLAG) engine || status=$$?; \
	end=$$(date +%s); \
	elapsed=$$((end - start)); \
	printf "  $(CYAN)⏱$(NC)  Prod image build time: %02dh:%02dm:%02ds\n" $$((elapsed / 3600)) $$(((elapsed % 3600) / 60)) $$((elapsed % 60)); \
	exit $$status
endif

docker-up: docker-build ## 🐳 Start all containers in background
	$(call step,$(BLUE)ℹ,Starting Engine containers...)
	@$(COMPOSE_DEV) up -d

docker-down: check-compose ## 🛑 Stop all containers
	$(call step,$(YELLOW)⚠,Stopping Engine...)
	@$(COMPOSE_DEV) down

docker-logs: check-compose  ## 🐳 Tail all container logs
	@$(COMPOSE_DEV) logs -f

docker-ps: check-compose  ## 🐳 Show running containers
	@$(COMPOSE_DEV) ps #--format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'

docker-images: check-compose  ## 🐳 Show built images
	@$(COMPOSE_DEV) images

docker-clean: check-compose  ## 🐳 Remove containers + volumes (full reset)
	@echo -e "$(RED)⚠  This will delete all data (database, node_modules, cache)$(NC)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@$(COMPOSE_DEV) down -v --remove-orphans 2>/dev/null || { \
		echo -e "$(YELLOW)⚠$(NC)  Compose down failed (AppArmor?). Force-removing containers..."; \
		docker rm -f $$(docker ps -aq --filter "name=transcendence") 2>/dev/null || true; \
		docker volume rm $$(docker volume ls -q --filter "name=transcendance") 2>/dev/null || true; \
	}
	$(call step,$(GREEN)✓,Full cleanup done)

docker-fclean: docker-clean  ## 🐳 Full clean + prune unused Docker resources
	@docker system prune -af --volumes 2>/dev/null || true
	$(call step,$(GREEN)✓,Docker system pruned)

# ============================================
#  🧹 CLEANUP (42 Style)
# ============================================

.PHONY: clean fclean re

clean: ## 🧹 Remove build artifacts (dist/)
	$(call step,$(YELLOW)⚠,Removing build artifacts...)
	@rm -rf $(APP)/dist
	$(call step,$(GREEN)✓,Clean complete)

fclean: clean check-compose ## 💥 Full wipe: clean + remove node_modules and DB volumes
	@echo -e "$(RED)⚠  This will delete all databases and node_modules$(NC)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(call step,$(RED)⚠,Destroying containers and volumes...)
	@$(COMPOSE_DEV) down -v --remove-orphans
	@rm -rf $(APP)/node_modules
	$(call step,$(GREEN)✓,Full deep cleanup done)

re: fclean all ## 🔄 Rebuild everything from scratch (fclean + all)

# ============================================
#  📦 DEPENDENCIES & DEV
# ============================================

.PHONY: install dev shell ensure-backend-deps add-dep

install: docker-up ## 📦 Install Node.js dependencies inside container
	$(call step,$(BLUE)ℹ,Installing BaaS dependencies...)
	@docker exec $(CONTAINER) sh -c "cd /app && pnpm install"

dev: docker-up ## 🔥 Tail hot-reload engine logs (LOG_LEVEL=debug|error|warn)
	$(call step,$(BLUE)ℹ,Tailing hot-reload engine logs [LOG_LEVEL=$(LOG_LEVEL)]...)
	@$(COMPOSE_DEV) logs -f engine

shell: ## 🐚 Open interactive bash shell inside dev container
	@docker exec -it $(CONTAINER) bash

add-dep: ## 📦 Add a dependency (usage: make add-dep PKG="name" DEV=1)
	@if [ "$(DEV)" = "1" ]; then \
		docker exec -it $(CONTAINER) sh -c "cd /app && pnpm add -D $(PKG)"; \
	else \
		docker exec -it $(CONTAINER) sh -c "cd /app && pnpm add $(PKG)"; \
	fi

ensure-backend-deps:
	$(call step,$(BLUE)ℹ,Ensuring backend dependencies are installed...)
	@$(COMPOSE_DEV) exec -T engine sh -c "cd /app && if [ ! -d node_modules/@nestjs/common ] || [ ! -x node_modules/.bin/jest ]; then pnpm install --prod=false; fi" 2>&1 || { \
		echo ""; \
		echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
		echo -e "$(RED)│  ✗  FAILED: $(BOLD)backend dependency check$(NC)"; \
		echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
		echo -e "$(RED)│$(NC)  $(BOLD)Why:$(NC)  Could not access/install backend dependencies"; \
		echo -e "$(RED)│$(NC)        in compose service 'engine' (/app)."; \
		echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  make docker-clean && make dev"; \
		echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
		echo ""; \
		exit 1; \
	}

# ============================================
#  🛡️ GIT HOOKS
# ============================================

.PHONY: install-hooks

install-hooks: ## 🛡️ Install Native Git Pre-push Hooks (Host-side)
	$(call step,$(BLUE)ℹ,Installing DevOps Shield (Pre-push)...)
	
	# Clean up any strict pre-commit hooks to allow WIP commits locally
	@rm -f .git/hooks/pre-commit 
	
	# Generate the pre-push hook script dynamically
	@echo '#!/bin/bash' > .git/hooks/pre-push
	@echo 'CONTAINER_NAME=$(CONTAINER)' >> .git/hooks/pre-push
	
	# Get the current Git branch the developer is pushing from
	@echo 'CURRENT_BRANCH=$$(git rev-parse --abbrev-ref HEAD)' >> .git/hooks/pre-push
	@echo '' >> .git/hooks/pre-push
	
	# ---------------------------------------------------------
	# 🕊️ FREE WILL ZONE (Feature Branches)
	# ---------------------------------------------------------
	@echo '# If the branch is NOT develop and NOT main, allow immediate push' >> .git/hooks/pre-push
	@echo 'if [[ "$$CURRENT_BRANCH" != "develop" && "$$CURRENT_BRANCH" != "main" ]]; then' >> .git/hooks/pre-push
	@echo '  echo -e "\033[0;32m🕊️  DevOps: Feature branch ($$CURRENT_BRANCH) detected. Free will mode active! Push allowed.\033[0m"' >> .git/hooks/pre-push
	@echo '  exit 0' >> .git/hooks/pre-push
	@echo 'fi' >> .git/hooks/pre-push
	@echo '' >> .git/hooks/pre-push
	
	# ---------------------------------------------------------
	# 🛑 ZERO TOLERANCE ZONE (Shared Branches)
	# ---------------------------------------------------------
	@echo '# Protected branch detected. Enforcing Zero Tolerance policy.' >> .git/hooks/pre-push
	@echo 'echo -e "\033[1;33m🛡️  DevOps: Protected branch ($$CURRENT_BRANCH) detected. Applying strict checks...\033[0m"' >> .git/hooks/pre-push
	
	# Check if the development container is DOWN
	@echo 'if [ -z "$$(docker ps -q -f name=$$CONTAINER_NAME)" ]; then' >> .git/hooks/pre-push
	@echo '  echo -e "\033[0;31m🛑 DevOps FATAL: Engine is DOWN. You CANNOT push to $$CURRENT_BRANCH without passing checks.\033[0m"' >> .git/hooks/pre-push
	@echo '  echo -e "Please run \033[1;33mmake dev\033[0m to start the engine and try again."' >> .git/hooks/pre-push
	@echo '  exit 1' >> .git/hooks/pre-push
	@echo 'fi' >> .git/hooks/pre-push
	
	# Run format, lint, typecheck, and unit tests. If any fails, abort.
	@echo 'make format && make lint && make typecheck && make test-unit' >> .git/hooks/pre-push
	@echo 'if [ $$? -ne 0 ]; then' >> .git/hooks/pre-push
	@echo '  echo -e "\033[0;31m❌ Quality check failed. Push blocked to protect $$CURRENT_BRANCH!\033[0m"' >> .git/hooks/pre-push
	@echo '  exit 1' >> .git/hooks/pre-push
	@echo 'fi' >> .git/hooks/pre-push
	
	@echo 'echo -e "\033[0;32m✅ Quality checks passed. Pushing to $$CURRENT_BRANCH...\033[0m"' >> .git/hooks/pre-push
	
	# Make the hook executable
	@chmod +x .git/hooks/pre-push
	$(call step,$(GREEN)✓,DevOps Pre-push Shield active!)

# ============================================
#  ✅ QUALITY & PHASE 0 CHECKS
# ============================================

.PHONY: lint format typecheck

lint: ## 🔍 Run ESLint on the codebase
	$(call step,$(BLUE)ℹ,Running ESLint...)
	@docker exec $(CONTAINER) sh -c "cd /app && pnpm exec eslint . "
	$(call step,$(GREEN)✓,Lint complete)


format: ## ✨ Run Prettier to format code
	$(call step,$(BLUE)ℹ,Running Prettier...)
	@docker exec $(CONTAINER) sh -c "cd /app && pnpm exec prettier --write 'src/**/*.ts'"

typecheck: ## 🏗️ Run TypeScript compiler check (no output)
	$(call step,$(BLUE)ℹ,Verifying Phase 0 Structure (tsc --noEmit)...)
	@docker exec $(CONTAINER) sh -c "cd /app && pnpm exec tsc --noEmit"
	$(call step,$(GREEN)✓,Phase 0 compilation passed!)

# ============================================
#  🔌 PORT MANAGEMENT
# ============================================

.PHONY: kill-ports

kill-ports: ## 🔌 Free up ports used by the project
	$(call step,$(YELLOW)⚠,Freeing ports...)
	@$(COMPOSE_DEV) down 2>/dev/null || true
	@for p in 3000 27117 5432 6379 8025; do \
		PIDS=$$(lsof -t -i :$$p 2>/dev/null || true); \
		if [ -n "$$PIDS" ]; then kill -9 $$PIDS 2>/dev/null || sudo kill -9 $$PIDS 2>/dev/null || true; fi; \
	done
	$(call step,$(GREEN)✓,Ports freed)

# ============================================
#  🩺 DIAGNOSTICS & SCRIPTS
# ============================================

.PHONY: doctor audit test-postman seed-system reset-db

doctor: ## 🩺 Run environment diagnostics
	@bash scripts/utils/doctor.sh

audit: ## 🛡️ Run all security & quality checks
	@bash scripts/diagnostic/run.sh all

test-postman: ## 📮 Run Postman CLI tests
	@bash scripts/test/postman-cli.sh help

seed-system: ## 🧠 Inject test Master Document into MongoDB
	@bash scripts/db/seed-control-plane.sh

reset-db: ## 💥 Destroy all data volumes (Mongo, Postgres, Redis)
	@bash scripts/db/reset.sh

# ============================================
#  🧪 TESTING
# ============================================

.PHONY: test test-unit test-e2e test-watch

test: test-unit test-e2e  ## 🧪 Run all tests

test-unit: ensure-backend-deps  ## 🧪 Run unit tests (LOG_LEVEL=error)
	$(call step,$(BLUE)ℹ,Running unit tests...)
	@$(COMPOSE_DEV) exec -e LOG_LEVEL=$(LOG_LEVEL) -T engine sh -c "cd /app && pnpm test"
	$(call step,$(GREEN)✓,Unit tests passed)

test-e2e: ensure-backend-deps  ## 🧪 Run E2E tests (LOG_LEVEL=error)
	$(call step,$(BLUE)ℹ,Running E2E tests...)
	@$(COMPOSE_DEV) exec -e LOG_LEVEL=$(LOG_LEVEL) -T engine sh -c "cd /app && pnpm run test:e2e"
	$(call step,$(GREEN)✓,E2E tests passed)

test-watch:  ## 🧪 Run tests in watch mode
	@$(COMPOSE_DEV) exec engine sh -c "cd /app && pnpm run test:watch"

# ============================================
#  ❓ HELP
# ============================================

help: ## ❓ Show all commands or search (use FILTER="keyword")
	@echo -e "$(BOLD)mini-baas — Command Manual$(NC)"
	@echo -e "Usage: $(CYAN)make <target>$(NC)"
	@echo -e "Search: $(CYAN)make help FILTER=<keyword>$(NC)"
	@echo ""
	@if [ -z "$(FILTER)" ]; then \
		echo -e "$(BOLD)Available Commands:$(NC)"; \
		grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
			awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'; \
	else \
		echo -e "$(BOLD)Commands matching: $(CYAN)'$(FILTER)'$(NC)"; \
		grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
			awk -v filter="$(FILTER)" 'BEGIN {FS = ":.*?## "; IGNORECASE = 1} \
				{if ($$1 ~ filter || $$2 ~ filter) printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'; \
	fi

help-all: ## ❓ Show all commands
	@echo -e "$(BOLD)mini-baas — All Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

help-%: ## ❓ Show commands for a specific category
	@echo -e "$(BOLD)mini-baas — Commands matching category: $(CYAN)$*$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk -v filter="^$*" 'BEGIN {FS = ":.*?## "; IGNORECASE = 1} \
			{if ($$1 ~ filter) printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
