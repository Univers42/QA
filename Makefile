# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    Makefile                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: dlesieur <dlesieur@student.42madrid.com    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/03/24 00:00:00 by dlesieur          #+#    #+#              #
#    Updated: 2026/03/26 00:00:00 by dlesieur         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

SHELL := /bin/bash
.SHELLFLAGS := -ec

.PHONY: help all install api test list add lint fix format clean fclean \
        preflight check-python check-env venv hooks dashboard re

.DEFAULT_GOAL := all

# ── Variables ────────────────────────────────────────
VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PQA        := $(VENV)/bin/pqa
UVICORN    := $(VENV)/bin/uvicorn
RUFF       := $(VENV)/bin/ruff

DOMAIN    ?=
PRIORITY  ?=
STATUS    ?=
ENV       ?= local
ID        ?=

# Source directories for linting/formatting
SRC_DIRS  := core/ runner/ api/ cli/ scripts/

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
	@echo -e "$(BLUE)║$(NC)  🧪  $(BOLD)Prismatica QA$(NC) · Test Hub v3                          $(BLUE)║$(NC)"
	@echo -e "$(BLUE)╚══════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
endef

define step
	echo -e "  $(1)  $(2)"
endef

# ============================================
#  🛡️ PREFLIGHT CHECKS
# ============================================

check-python:
	@command -v python3 >/dev/null 2>&1 || { \
		echo ""; \
		echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
		echo -e "$(RED)│  ✗  FAILED: $(BOLD)Python 3 not found$(NC)"; \
		echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
		echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  sudo apt install python3 python3-venv python3-pip"; \
		echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null || { \
		echo ""; \
		echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
		echo -e "$(RED)│  ✗  FAILED: $(BOLD)Python 3.11+ required$(NC)"; \
		echo -e "$(RED)├─────────────────────────────────────────────────────────┤$(NC)"; \
		echo -e "$(RED)│$(NC)  Current: $$(python3 --version)"; \
		echo -e "$(RED)│$(NC)  $(BOLD)Fix:$(NC)  sudo apt install python3.11 (or newer)"; \
		echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
		echo ""; \
		exit 1; \
	}
	@$(call step,$(GREEN)✓,Python $$(python3 --version | cut -d' ' -f2) detected)

check-env:
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			echo -e "  $(YELLOW)⚠$(NC)  .env not found — creating from .env.example"; \
			cp .env.example .env; \
			echo -e "  $(GREEN)✓$(NC)  .env created — $(BOLD)edit it with your Atlas password$(NC)"; \
		else \
			echo ""; \
			echo -e "$(RED)┌─────────────────────────────────────────────────────────┐$(NC)"; \
			echo -e "$(RED)│  ✗  FAILED: $(BOLD).env and .env.example are both missing$(NC)"; \
			echo -e "$(RED)└─────────────────────────────────────────────────────────┘$(NC)"; \
			echo ""; \
			exit 1; \
		fi; \
	else \
		$(call step,$(GREEN)✓,.env file loaded); \
	fi

preflight: check-python check-env  ## 🛡️ Run all preflight checks
	@$(call step,$(GREEN)✓,$(BOLD)All preflight checks passed$(NC))

# ============================================
#  📦 VIRTUAL ENVIRONMENT & DEPENDENCIES
# ============================================

venv: check-python  ## 🐍 Create virtual environment
	@if [ ! -d $(VENV) ]; then \
		$(call step,$(BLUE)ℹ,Creating virtual environment...); \
		python3 -m venv $(VENV); \
		$(call step,$(GREEN)✓,Virtual environment created at $(VENV)/); \
	else \
		$(call step,$(GREEN)✓,Virtual environment already exists); \
	fi

install: venv check-env  ## 📦 Install all Python dependencies
	@$(call step,$(BLUE)ℹ,Installing dependencies...)
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r requirements.txt -q
	@$(PIP) install -e . -q
	@$(call step,$(GREEN)✓,Dependencies installed)
	@$(call step,$(GREEN)✓,$(BOLD)pqa$(NC) command available inside venv)
	@echo ""
	@echo -e "  $(DIM)Activate the venv to use pqa directly:$(NC)"
	@echo -e "  $(DIM)  source $(VENV)/bin/activate$(NC)"
	@echo ""

# ============================================
#  ⚡ DEFAULT
# ============================================

all: banner preflight install hooks  ## 🚀 Full setup (default)
	@echo ""
	@echo -e "  $(GREEN)$(BOLD)Setup complete!$(NC) Next steps:"
	@echo -e "  $(DIM)  1. Edit .env with your Atlas password$(NC)"
	@echo -e "  $(DIM)  2. make api    — start the API server$(NC)"
	@echo -e "  $(DIM)  3. make test   — run all active tests$(NC)"
	@echo -e "  $(DIM)  4. make help   — see all available commands$(NC)"
	@echo ""

re: fclean all  ## 🔄 Full rebuild (clean + setup)

banner:
	$(BANNER)

# ============================================
#  🔒 GIT HOOKS
# ============================================

hooks:  ## 🔒 Install git hooks (conventional commits, branch protection)
	@bash hooks/install.sh

# ============================================
#  🚀 API SERVER
# ============================================

api: install  ## 🚀 Start FastAPI server (port 8000, Swagger at /docs)
	@$(call step,$(BLUE)ℹ,Starting Prismatica QA API on :8000...)
	@echo -e "  $(DIM)  Swagger UI:  http://localhost:8000/docs$(NC)"
	@echo -e "  $(DIM)  Health:      http://localhost:8000/$(NC)"
	@echo ""
	@$(UVICORN) api.main:app --reload --port 8000

# ============================================
#  🧪 TEST MANAGEMENT & EXECUTION
# ============================================

test: install  ## 🧪 Run tests (DOMAIN=auth PRIORITY=P0)
	@$(call step,$(BLUE)ℹ,Running tests — domain=$(DOMAIN) priority=$(PRIORITY) env=$(ENV)...)
	@$(PQA) test run \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		$(if $(PRIORITY),--priority $(PRIORITY)) \
		$(if $(ID),--id $(ID))

list: install  ## 📋 List tests (DOMAIN=auth STATUS=active PRIORITY=P0)
	@$(PQA) test list \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		$(if $(STATUS),--status $(STATUS)) \
		$(if $(PRIORITY),--priority $(PRIORITY))

add: install  ## ➕ Create a new test (interactive)
	@$(PQA) test add

edit: install  ## ✏️  Edit a test (ID=AUTH-003)
	@if [ -z "$(ID)" ]; then \
		echo ""; \
		echo -e "  $(RED)✗  Missing ID.$(NC) Usage: $(BOLD)make edit ID=AUTH-003$(NC)"; \
		echo ""; \
		exit 1; \
	fi
	@$(PQA) test edit $(ID)

delete: install  ## 🗑️  Deprecate a test (ID=AUTH-003)
	@if [ -z "$(ID)" ]; then \
		echo ""; \
		echo -e "  $(RED)✗  Missing ID.$(NC) Usage: $(BOLD)make delete ID=AUTH-003$(NC)"; \
		echo ""; \
		exit 1; \
	fi
	@$(PQA) test delete $(ID)

# ============================================
#  🔍 CODE QUALITY
# ============================================

lint: install  ## 🔍 Check PEP 8 compliance (ruff)
	@$(call step,$(BLUE)ℹ,Running ruff linter...)
	@$(RUFF) check $(SRC_DIRS)
	@$(call step,$(GREEN)✓,Lint passed — PEP 8 compliant)

fix: install  ## 🔧 Auto-fix lint issues (ruff --fix)
	@$(call step,$(BLUE)ℹ,Auto-fixing lint issues...)
	@$(RUFF) check --fix $(SRC_DIRS)
	@$(call step,$(GREEN)✓,Lint issues fixed)

format: install  ## 🎨 Auto-format code (ruff format + fix)
	@$(call step,$(BLUE)ℹ,Formatting code...)
	@$(RUFF) format $(SRC_DIRS)
	@$(RUFF) check --fix $(SRC_DIRS)
	@$(call step,$(GREEN)✓,Code formatted)

# ============================================
#  🌐 DASHBOARD
# ============================================

dashboard:  ## 🌐 Start React dashboard (port 5173)
	@if [ ! -d dashboard/node_modules ]; then \
		$(call step,$(BLUE)ℹ,Installing dashboard dependencies...); \
		cd dashboard && npm install; \
	fi
	@$(call step,$(BLUE)ℹ,Starting dashboard on :5173...)
	@cd dashboard && npm run dev

# ============================================
#  🧹 CLEANUP
# ============================================

clean:  ## 🧹 Remove venv and caches
	@$(call step,$(YELLOW)⚠,Cleaning...)
	@rm -rf $(VENV) *.egg-info .pytest_cache .ruff_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@$(call step,$(GREEN)✓,Clean)

fclean: clean  ## 🧹 Full clean (venv + dashboard node_modules)
	@rm -rf dashboard/node_modules
	@$(call step,$(GREEN)✓,Full clean)

# ============================================
#  ❓ HELP
# ============================================

help:  ## ❓ Show available commands
	@echo ""
	@echo -e "$(BOLD)Prismatica QA — Available Commands$(NC)"
	@echo ""
	@echo -e "  $(CYAN)Setup & Server$(NC)"
	@echo -e "  $(GREEN)make$(NC)                  Full setup (install + hooks)"
	@echo -e "  $(GREEN)make api$(NC)              Start FastAPI on :8000 (Swagger at /docs)"
	@echo -e "  $(GREEN)make dashboard$(NC)        Start React dashboard on :5173"
	@echo ""
	@echo -e "  $(CYAN)Test Management$(NC)"
	@echo -e "  $(GREEN)make list$(NC)             List all tests from Atlas"
	@echo -e "  $(GREEN)make list DOMAIN=auth$(NC) List tests filtered by domain"
	@echo -e "  $(GREEN)make list STATUS=active$(NC) List only active tests"
	@echo -e "  $(GREEN)make add$(NC)              Create a new test (interactive)"
	@echo -e "  $(GREEN)make edit ID=AUTH-003$(NC) Edit a test"
	@echo -e "  $(GREEN)make delete ID=AUTH-003$(NC) Deprecate a test"
	@echo ""
	@echo -e "  $(CYAN)Test Execution$(NC)"
	@echo -e "  $(GREEN)make test$(NC)             Run all active tests"
	@echo -e "  $(GREEN)make test DOMAIN=auth$(NC) Run auth tests only"
	@echo -e "  $(GREEN)make test PRIORITY=P0$(NC) Run P0 (blocking) tests only"
	@echo -e "  $(GREEN)make test ID=AUTH-003$(NC) Run a single test"
	@echo ""
	@echo -e "  $(CYAN)Data & Export$(NC)"
	@echo -e "  $(GREEN)make export$(NC)           Export all tests from Atlas to JSON"
	@echo -e "  $(GREEN)make export DOMAIN=auth$(NC) Export auth tests only"
	@echo -e "  $(GREEN)make migrate$(NC)          Load JSON files into Atlas (one-time)"
	@echo ""
	@echo -e "  $(CYAN)Code Quality$(NC)"
	@echo -e "  $(GREEN)make lint$(NC)             Check PEP 8 compliance"
	@echo -e "  $(GREEN)make fix$(NC)              Auto-fix lint issues"
	@echo -e "  $(GREEN)make format$(NC)           Format code + fix issues"
	@echo ""
	@echo -e "  $(CYAN)Maintenance$(NC)"
	@echo -e "  $(GREEN)make hooks$(NC)            Install git hooks"
	@echo -e "  $(GREEN)make clean$(NC)            Remove venv and caches"
	@echo -e "  $(GREEN)make fclean$(NC)           Full clean (+ dashboard)"
	@echo ""
