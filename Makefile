# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    Makefile                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: vjan-nie <vjan-nie@student.42madrid.com    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/03/21 19:04:31 by vjan-nie          #+#    #+#              #
#    Updated: 2026/03/24 00:00:00 by codex            ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

SHELL := /bin/bash
.SHELLFLAGS := -ec

.DEFAULT_GOAL := all

.PHONY: help all banner preflight check-docker check-compose check-env build ensure-image \
	up down logs ps add validate sync run run-interactive export shell install seed test clean

# ── Compose auto-detection ────────────────────────────────────────────────────
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

# ── Runtime variables ────────────────────────────────────────────────────────
QA_IMAGE   := prismatica-qa-cli:local
DOMAIN     ?=
TYPE       ?=
LAYER      ?=
PRIORITY   ?=
STATUS     ?=
ENV        ?= local
WORKERS    ?=
ARGS       ?=
LOCAL_UID  := $(shell id -u)
LOCAL_GID  := $(shell id -g)

export LOCAL_UID
export LOCAL_GID

FILTER_ARGS = $(if $(DOMAIN),--domain $(DOMAIN),) \
	$(if $(TYPE),--type $(TYPE),) \
	$(if $(LAYER),--layer $(LAYER),) \
	$(if $(PRIORITY),--priority $(PRIORITY),) \
	$(if $(STATUS),--status $(STATUS),)

RUN_ARGS = $(strip $(FILTER_ARGS) --env $(ENV) $(if $(WORKERS),--workers $(WORKERS),) $(ARGS))
SYNC_ARGS = $(strip $(if $(DOMAIN),--domain $(DOMAIN),) $(ARGS))
VALIDATE_ARGS = $(strip $(if $(DOMAIN),--domain $(DOMAIN),) $(ARGS))
EXPORT_ARGS = $(strip $(if $(DOMAIN),--domain $(DOMAIN),) $(if $(STATUS),--status $(STATUS),) $(ARGS))

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
	@echo -e "$(BLUE)║$(NC)  $(BOLD)Prismatica QA$(NC) · Dockerized CLI                         $(BLUE)║$(NC)"
	@echo -e "$(BLUE)╚══════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
endef

define step
	echo -e "  $(1)  $(2)"
endef

define run_qa
	$(COMPOSE_CMD) run --rm --no-deps qa $(1)
endef

# ============================================
#  PRECHECKS
# ============================================

check-docker:
	@command -v docker >/dev/null 2>&1 || { \
		echo ""; \
		echo -e "$(RED)Docker Engine not found.$(NC)"; \
		echo -e "$(RED)Install Docker: https://docs.docker.com/get-docker/$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@docker info >/dev/null 2>&1 || { \
		echo ""; \
		echo -e "$(RED)Docker daemon is not running.$(NC)"; \
		echo -e "$(RED)Start Docker Desktop or the docker service first.$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@$(call step,$(GREEN)✓,Docker Engine is running)

check-compose:
ifeq ($(COMPOSE_CMD),__NONE__)
	@echo ""
	@echo -e "$(RED)No Docker Compose tool found.$(NC)"
	@echo -e "$(RED)Install Docker Desktop or docker-compose.$(NC)"
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
			echo -e "  $(GREEN)✓$(NC)  .env created — review URLs if your services do not run on the host"; \
		else \
			echo ""; \
			echo -e "$(RED).env file is missing.$(NC)"; \
			echo -e "$(RED)Fix: cp .env.example .env$(NC)"; \
			echo ""; \
			exit 1; \
		fi; \
	else \
		echo -e "  $(GREEN)✓$(NC)  .env file loaded"; \
	fi

preflight: check-docker check-compose check-env  ## Run all preflight checks
	@$(call step,$(GREEN)✓,$(BOLD)All preflight checks passed$(NC))

# ============================================
#  DEFAULT
# ============================================

all: banner preflight build up  ## Full dockerized setup

banner:
	$(BANNER)

# ============================================
#  DOCKER
# ============================================

build: check-docker check-compose check-env  ## Build the Prismatica QA CLI image
	@$(call step,$(BLUE)ℹ,Building Docker image $(QA_IMAGE)...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) build qa
	@$(call step,$(GREEN)✓,Docker image ready)

ensure-image: check-docker check-compose check-env
	@if ! docker image inspect $(QA_IMAGE) >/dev/null 2>&1; then \
		$(call step,$(BLUE)ℹ,Docker image not found — building $(QA_IMAGE)...); \
		LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) build qa; \
		$(call step,$(GREEN)✓,Docker image ready); \
	else \
		$(call step,$(GREEN)✓,Docker image available: $(QA_IMAGE)); \
	fi

up: check-docker check-compose check-env  ## Start local MongoDB for history and sync
	@$(call step,$(BLUE)ℹ,Starting MongoDB...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) up -d mongo
	@$(call step,$(GREEN)✓,MongoDB running on port 27017)

down: check-docker check-compose  ## Stop Docker services
	@$(call step,$(YELLOW)⚠,Stopping Docker services...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) down
	@$(call step,$(GREEN)✓,Docker services stopped)

logs: check-docker check-compose  ## Tail MongoDB logs
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) logs -f mongo

ps: check-docker check-compose  ## Show running Docker services
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) ps

shell: ensure-image  ## Open a shell inside the QA CLI container
	@$(call step,$(BLUE)ℹ,Opening shell in qa container...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(COMPOSE_CMD) run --rm --no-deps --entrypoint /bin/bash qa

# ============================================
#  QA CLI
# ============================================

add: ensure-image up  ## Launch the interactive add form (use ARGS='--quick ...' for non-interactive)
	@$(call step,$(BLUE)ℹ,Launching the add form...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(call run_qa,add $(ARGS))

validate: ensure-image  ## Validate repository JSON definitions (DOMAIN=auth optional)
	@$(call step,$(BLUE)ℹ,Validating repository JSON definitions...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(call run_qa,validate $(VALIDATE_ARGS))

sync: ensure-image up  ## Sync valid JSON definitions into local MongoDB
	@$(call step,$(BLUE)ℹ,Synchronizing JSON definitions into MongoDB...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(call run_qa,sync $(SYNC_ARGS))

run: ensure-image up  ## Run tests from repository JSON with optional MongoDB history
	@$(call step,$(BLUE)ℹ,Running tests — domain=$(if $(DOMAIN),$(DOMAIN),all) type=$(if $(TYPE),$(TYPE),all) env=$(ENV)...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(call run_qa,run $(RUN_ARGS))

run-interactive: ensure-image up  ## Run tests with an interactive filter prompt
	@$(call step,$(BLUE)ℹ,Launching interactive test execution...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(call run_qa,run --interactive --env $(ENV) $(ARGS))

export: ensure-image up  ## Export MongoDB definitions back to repository JSON
	@$(call step,$(BLUE)ℹ,Exporting MongoDB definitions to JSON...)
	@LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) $(call run_qa,export $(EXPORT_ARGS))

# Legacy-friendly aliases
install: build  ## Alias for build
seed: sync  ## Alias for sync
test: run  ## Alias for run

# ============================================
#  CLEANUP
# ============================================

clean:  ## Remove Python cache artifacts from the repository
	@$(call step,$(YELLOW)⚠,Cleaning local cache files...)
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@find . -type f -name '*.pyc' -delete
	@$(call step,$(GREEN)✓,Cleanup complete)

# ============================================
#  HELP
# ============================================

help:  ## Show available commands
	@echo ""
	@echo -e "$(BOLD)Prismatica QA — Dockerized Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo -e "  $(DIM)Examples:$(NC)"
	@echo -e "  $(DIM)  make add$(NC)"
	@echo -e "  $(DIM)  make add ARGS=\"--quick --domain infra --title 'PostgreSQL accepts connections' --type bash --script 'pg_isready -h localhost -p 5432 -U postgres' --priority P0 --status active\"$(NC)"
	@echo -e "  $(DIM)  make validate DOMAIN=auth$(NC)"
	@echo -e "  $(DIM)  make run DOMAIN=auth TYPE=http STATUS=active$(NC)"
	@echo -e "  $(DIM)  make run-interactive$(NC)"
	@echo ""
