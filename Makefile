# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    Makefile                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: vjan-nie <vjan-nie@student.42madrid.com    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/03/24 00:00:00 by dlesieur          #+#    #+#              #
#    Updated: 2026/03/25 23:03:30 by vjan-nie         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

SHELL := /bin/bash
.SHELLFLAGS := -ec

.PHONY: help all install api test list clean preflight check-python check-env venv

.DEFAULT_GOAL := all

# ── Variables ────────────────────────────────────────
VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PQA        := $(VENV)/bin/pqa
UVICORN    := $(VENV)/bin/uvicorn

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
	@echo ""

banner:
	$(BANNER)

# ============================================
#  🚀 API SERVER
# ============================================

api: install  ## 🚀 Start FastAPI server (port 8000)
	@$(call step,$(BLUE)ℹ,Starting Prismatica QA API on :8000...)
	@$(UVICORN) api.main:app --reload --port 8000

# ============================================
#  🧪 TEST EXECUTION
# ============================================

test: install  ## 🧪 Run tests (DOMAIN=auth PRIORITY=P0 ENV=local)
	@$(call step,$(BLUE)ℹ,Running tests — domain=$(DOMAIN) priority=$(PRIORITY) env=$(ENV)...)
	@DOMAIN=$(DOMAIN) PRIORITY=$(PRIORITY) TEST_ENV=$(ENV) $(PQA) test run \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		$(if $(PRIORITY),--priority $(PRIORITY))

list: install  ## 📋 List all tests
	@$(PQA) test list

# ============================================
#  🗄️ DATA MANAGEMENT
# ============================================

migrate: install  ## 🔄 Migrate v1 JSON tests into Atlas
	@$(call step,$(BLUE)ℹ,Migrating test definitions to Atlas...)
	@$(PYTHON) scripts/migrate_v1_to_v2.py
	@$(call step,$(GREEN)✓,Migration complete)

export: install  ## 📤 Export tests from Atlas to test-definitions/ JSON
	@$(PQA) test export

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
#  🔒 GIT HOOKS
# ============================================

hooks:  ## 🔒 Install git hooks (conventional commits, branch protection)
	@bash hooks/install.sh

# ============================================
#  🧹 CLEANUP
# ============================================

clean:  ## 🧹 Remove venv and caches
	@$(call step,$(YELLOW)⚠,Cleaning...)
	@rm -rf $(VENV) __pycache__ core/__pycache__ runner/__pycache__ api/__pycache__ cli/__pycache__
	@rm -rf *.egg-info .pytest_cache
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
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo -e "  $(DIM)Examples:$(NC)"
	@echo -e "  $(DIM)  make test DOMAIN=auth$(NC)"
	@echo -e "  $(DIM)  make test PRIORITY=P0$(NC)"
	@echo -e "  $(DIM)  make api$(NC)"
	@echo -e "  $(DIM)  make dashboard$(NC)"
	@echo ""
