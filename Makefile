# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    Makefile                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: vjan-nie <vjan-nie@student.42madrid.com    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/03/21 19:04:31 by vjan-nie          #+#    #+#              #
#    Updated: 2026/03/21 19:04:36 by vjan-nie         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

SHELL := /bin/bash
.SHELLFLAGS := -ec

.PHONY: help all up down logs ps install seed validate test clean preflight check-docker check-compose check-env

.DEFAULT_GOAL := all

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
DOMAIN    ?=
PRIORITY  ?=
ENV       ?= local

# Colors
BLUE    := \033[0;34m
GREEN   := \033[0;32m
YELLOW  := \033[1;33m
RED     := \033[0;31m
CYAN    := \033[0;36m
NC      := \033[0m
BOLD    := \033[1m
DIM     := \033[2m

define BANNER
	@echo ""
	@echo -e "$(BLUE)╔══════════════════════════════════════════════════════════╗$(NC)"
	@echo -e "$(BLUE)║$(NC)  🧪  $(BOLD)Prismatica QA$(NC) · Test Hub                              $(BLUE)║$(NC)"
	@echo -e "$(BLUE)╚══════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
endef

define step
	echo -e "  $(1)  $(2)"
endef

# ============================================
#  🛡️ PREFLIGHT CHECKS
# ============================================

check-docker:
	@command -v docker >/dev/null 2>&1 || { \
		echo ""; \
		echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
		echo -e "$(RED)│  ✗  FAILED: $(BOLD)Docker Engine not found$(NC)"; \
		echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
		echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  Install Docker: https://docs.docker.com/get-docker/"; \
		echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@docker info >/dev/null 2>&1 || { \
		echo ""; \
		echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
		echo -e "$(RED)│  ✗  FAILED: $(BOLD)Docker daemon is not running$(NC)"; \
		echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
		echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  sudo systemctl start docker  OR  open Docker Desktop"; \
		echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@$(call step,$(GREEN)✓,Docker Engine is running)

check-compose:
ifeq ($(COMPOSE_CMD),__NONE__)
	@echo ""
	@echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"
	@echo -e "$(RED)│  ✗  FAILED: $(BOLD)No Docker Compose tool found$(NC)"
	@echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"
	@echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  Install Docker Desktop (includes compose v2)"
	@echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"
	@echo ""
	@exit 1
else
	@$(call step,$(GREEN)✓,Compose tool: $(BOLD)$(COMPOSE_CMD)$(NC))
endif

check-env:
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			echo -e "  $(YELLOW)⚠$(NC)  .env not found — creating from .env.example"; \
			cp .env.example .env; \
			echo -e "  $(GREEN)✓$(NC)  .env created — $(BOLD)review it and update values if needed$(NC)"; \
		else \
			echo ""; \
			echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
			echo -e "$(RED)│  ✗  FAILED: $(BOLD).env file is missing$(NC)"; \
			echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
			echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  cp .env.example .env"; \
			echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
			echo ""; \
			exit 1; \
		fi; \
	else \
		echo -e "  $(GREEN)✓$(NC)  .env file loaded"; \
	fi

preflight: check-docker check-compose check-env  ## 🛡️ Run all preflight checks
	@$(call step,$(GREEN)✓,$(BOLD)All preflight checks passed$(NC))

# ============================================
#  ⚡ DEFAULT
# ============================================

all: banner preflight install up  ## 🚀 Full setup (default)

banner:
	$(BANNER)

# ============================================
#  🐳 MONGODB
# ============================================

up: check-docker check-compose check-env  ## 🐳 Start MongoDB container
	@$(call step,$(BLUE)ℹ,Starting MongoDB...)
	@$(COMPOSE_CMD) up -d --build 2>&1 || { \
		echo ""; \
		echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
		echo -e "$(RED)│  ✗  FAILED: $(BOLD)MongoDB startup$(NC)"; \
		echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
		echo -e "$(RED)│$(NC)  $(BOLD)Common causes:$(NC)"; \
		echo -e "$(RED)│$(NC)    • Port 27017 already in use"; \
		echo -e "$(RED)│$(NC)    • Stale container (run $(BOLD)make down$(NC) first)"; \
		echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@$(call step,$(GREEN)✓,MongoDB running on port 27017)

down: check-docker check-compose  ## 🐳 Stop MongoDB container
	@$(call step,$(YELLOW)⚠,Stopping MongoDB...)
	@$(COMPOSE_CMD) down 2>/dev/null || { \
		echo -e "$(YELLOW)⚠$(NC)  Compose down failed — force-removing containers..."; \
		docker rm -f $$(docker ps -aq --filter "name=prismatica-qa") 2>/dev/null || true; \
	}
	@$(call step,$(GREEN)✓,MongoDB stopped)

logs:  ## 🐳 Tail MongoDB logs
	@$(COMPOSE_CMD) logs -f

ps:  ## 🐳 Show running containers
	@$(COMPOSE_CMD) ps

# ============================================
#  📦 DEPENDENCIES
# ============================================

install:  ## 📦 Install Node.js dependencies
	@$(call step,$(BLUE)ℹ,Installing dependencies...)
	@npm install
	@$(call step,$(GREEN)✓,Dependencies installed)

# ============================================
#  🧪 TEST HUB
# ============================================

seed:  ## 🌱 Load test-definitions/ into MongoDB
	@$(call step,$(BLUE)ℹ,Seeding test definitions into MongoDB...)
	@npm run seed
	@$(call step,$(GREEN)✓,Seed complete)

validate:  ## ✅ Validate all test JSON files against schema
	@$(call step,$(BLUE)ℹ,Validating test definitions...)
	@npm run validate
	@$(call step,$(GREEN)✓,Validation complete)

test:  ## 🧪 Run test runner (DOMAIN=auth PRIORITY=P1 ENV=local)
	@$(call step,$(BLUE)ℹ,Running tests — domain=$(DOMAIN) priority=$(PRIORITY) env=$(ENV)...)
	@DOMAIN=$(DOMAIN) PRIORITY=$(PRIORITY) TEST_ENV=$(ENV) npm run test
	@$(call step,$(GREEN)✓,Test run complete)

# ============================================
#  🧹 CLEANUP
# ============================================

clean:  ## 🧹 Remove node_modules and dist
	@$(call step,$(YELLOW)⚠,Cleaning...)
	@rm -rf node_modules dist
	@$(call step,$(GREEN)✓,Clean)

# ============================================
#  ❓ HELP
# ============================================

help:  ## ❓ Show available commands
	@echo ""
	@echo -e "$(BOLD)Prismatica QA — Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo -e "  $(DIM)Examples:$(NC)"
	@echo -e "  $(DIM)  make test DOMAIN=auth$(NC)"
	@echo -e "  $(DIM)  make test PRIORITY=P0$(NC)"
	@echo -e "  $(DIM)  make test DOMAIN=gateway ENV=staging$(NC)"
	@echo ""
