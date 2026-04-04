# PRISMATICA · QA

*Test Registry for the Prismatica / ft_transcendence ecosystem — by Univers42, 2026.*

prismatica-qa is a **Test Registry** — a centralized catalog and result store for tests that live as scripts in each project repository. It registers test metadata in MongoDB Atlas, orchestrates execution across multiple repos, and persists results for tracking and analysis. Tests are code. QA is the catalog.

---

## Table of Contents

- [Quick Start (as submodule in your repo)](#quick-start-as-submodule-in-your-repo)
- [How It Works](#how-it-works)
- [Integration Template](#integration-template)
- [Usage Guide](#usage-guide)
- [Managing Test Registry](#managing-test-registry)
- [All Commands](#all-commands)
- [API Reference](#api-reference)
- [File Naming Conventions](#file-naming-conventions)
- [Architecture](#architecture)
- [Documentation](#documentation)

---

## Quick Start (as submodule in your repo)

### Step 1 — Add the submodule

```bash
cd ~/your-repo
git submodule add https://github.com/Univers42/QA.git vendor/qa
```

### Step 2 — Configure Atlas access

```bash
cp vendor/qa/.env.example vendor/qa/.env
nano vendor/qa/.env
```

Set `MONGO_URI_ATLAS` with the team's Atlas connection string. Ask the QA admin if you don't have it.

**Important:** `vendor/qa/.env` is gitignored — each developer configures it once on their machine.

### Step 3 — Add Make rules

Copy the [Integration Template](#integration-template) into your Makefile. Change `QA_REPO` to your repository name.

### Step 4 — Register and run

```bash
make qa-setup                          # install dependencies (first time)
make qa-register                       # scan scripts/ and register in Atlas
make qa-list                           # see your registered tests
make qa-test                           # run all active tests
```

---

## How It Works

```
Your repo (transcendence, mini-baas-infra, ...)
├── scripts/
│   ├── phase1-smoke-test.sh           ← test code lives HERE
│   ├── phase2-auth-test.sh
│   └── my-feature-test.sh
│
├── vendor/qa/                         ← QA submodule
│   ├── .env                           ← Atlas password (NOT committed)
│   └── (QA system code)
│
└── Makefile
    ├── make qa-register               ← scans scripts/, registers in Atlas
    ├── make qa-test                   ← executes tests, stores results
    └── make qa-list                   ← shows registered tests
```

**Tests are code in your repo.** You write bash scripts, pytest files, or jest tests. QA never touches your test code.

**Atlas stores metadata and results.** `make qa-register` reads your scripts directory, detects test files by naming convention, and writes a catalog entry to Atlas. `make qa-test` reads the catalog, executes each script, and writes results back to Atlas.

**No JSON definitions needed.** Your test scripts ARE the tests. QA just tracks them.

---

## Integration Template

Copy this entire block into any project Makefile. Change `QA_REPO` to your repository name.

```makefile
# ============================================================================
# QA Test Registry (Prismatica QA integration)
# ============================================================================
# Setup:
#   git submodule add https://github.com/Univers42/QA.git vendor/qa
#   cp vendor/qa/.env.example vendor/qa/.env
#   nano vendor/qa/.env                  # set MONGO_URI_ATLAS

QA_DIR    := vendor/qa
PQA       := $(QA_DIR)/.venv/bin/pqa
QA_REPO   := your-repo-name

qa-setup: ## 🧪 Install/update QA submodule (auto-pulls latest)
	@cd $(QA_DIR) && git pull origin main --quiet 2>/dev/null || true
	@if [ ! -d "$(QA_DIR)/.venv" ]; then \
		echo -e "\033[0;34mSetting up QA submodule...\033[0m"; \
		cd $(QA_DIR) && make install SHOW_NEXT_STEPS=0; \
	else \
		echo -e "\033[0;32m✓ QA submodule ready\033[0m"; \
		cd $(QA_DIR) && .venv/bin/pip install -e . -q 2>/dev/null; \
	fi

qa-register: qa-setup ## 🧪 Register/update test scripts in Atlas
	@$(PQA) test register --repo $(QA_REPO) --scan scripts/

qa-list: qa-setup ## 📋 List registered tests (DOMAIN= LAYER= STATUS=)
	@$(PQA) test list --repo $(QA_REPO) \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		$(if $(LAYER),--layer $(LAYER)) \
		$(if $(STATUS),--status $(STATUS))

qa-test: qa-setup ## 🧪 Run tests (DOMAIN= PRIORITY= LAYER= ID=)
	@$(PQA) test run --repo $(QA_REPO) --repo-root . \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		$(if $(PRIORITY),--priority $(PRIORITY)) \
		$(if $(LAYER),--layer $(LAYER)) \
		$(if $(ID),--id $(ID))

qa-my: qa-setup ## 👤 List my tests only (uses PQA_USER env var)
	@$(PQA) test list --repo $(QA_REPO) --mine

.PHONY: qa-setup qa-register qa-list qa-test qa-my
```

**Repos currently integrated:**

| Repository | `QA_REPO` value | Test directory | Tests |
|---|---|---|---|
| mini-baas-infra | `mini-baas-infra` | `scripts/` | 15 registered |
| transcendence | `transcendence` | `tests/` | Pending |

---

## Usage Guide

### Daily workflow

```bash
make qa-list                           # see all tests for this repo
make qa-test                           # run all active tests
make qa-test DOMAIN=auth               # run only auth tests
make qa-test PRIORITY=P0               # run only blocking tests
make qa-test ID=BAAS-PHASE08           # run one specific test
make qa-test LAYER=backend             # run only backend tests
```

### After creating new test scripts

```bash
# 1. Name your script following the convention (see File Naming Conventions)
#    Example: scripts/phase16-new-feature-test.sh

# 2. Re-register to pick up the new file
make qa-register

# 3. Verify it appears
make qa-list

# 4. Run it
make qa-test ID=BAAS-PHASE16
```

### Skipping a test temporarily

```bash
cd vendor/qa
.venv/bin/pqa test edit BAAS-PHASE09
# When prompted for status, type: skipped

# To re-activate later:
.venv/bin/pqa test edit BAAS-PHASE09
# Change status back to: active
```

### Bulk status changes

```bash
cd vendor/qa
.venv/bin/python -c "
from core.db import get_db
# Skip all storage tests
result = get_db()['tests'].update_many(
    {'repo': 'mini-baas-infra', 'domain': 'storage'},
    {'\$set': {'status': 'skipped'}}
)
print(f'Skipped {result.modified_count} tests')
"
```

### Updating test metadata

```bash
cd vendor/qa

# Interactive edit (title, domain, priority, layer, etc.)
.venv/bin/pqa test edit BAAS-PHASE08

# Bulk: set all infra tests to P0
.venv/bin/python -c "
from core.db import get_db
result = get_db()['tests'].update_many(
    {'repo': 'mini-baas-infra', 'domain': 'infra'},
    {'\$set': {'priority': 'P0'}}
)
print(f'Updated {result.modified_count} tests')
"
```

### Re-registering

`make qa-register` is safe to run repeatedly:
- Adds new files that match the naming convention
- Updates the `script` path if a file was renamed
- Does NOT overwrite `status`, `author`, or `priority` of existing tests
- Does NOT remove tests whose scripts were deleted

---

## All Commands

### From your project (via Make rules)

| Command | Description |
|---------|-------------|
| `make qa-setup` | Install/update QA submodule |
| `make qa-register` | Scan and register test scripts |
| `make qa-list` | List tests for this repo |
| `make qa-list DOMAIN=auth` | Filter by domain |
| `make qa-list LAYER=backend` | Filter by layer |
| `make qa-list STATUS=active` | Filter by status |
| `make qa-test` | Run all active tests |
| `make qa-test DOMAIN=auth` | Run auth tests |
| `make qa-test PRIORITY=P0` | Run blocking tests |
| `make qa-test ID=BAAS-PHASE08` | Run one test |
| `make qa-my` | List my tests (`PQA_USER`) |

### From the QA repo (admin)

| Command | Description |
|---------|-------------|
| `pqa test list` | All tests, all repos |
| `pqa test list --repo X` | Tests for repo X |
| `pqa test list --mine` | My tests |
| `pqa test run` | Run all active tests |
| `pqa test register --repo X --scan dir/` | Register scripts |
| `pqa test add` | Create test interactively |
| `pqa test edit ID` | Edit metadata |
| `pqa test delete ID` | Deprecate test |
| `make api` | Start FastAPI (:8000) |
| `make lint` | PEP 8 check |
| `make format` | Auto-format |

---

## API Reference

Start with `make api` from the QA repo. Swagger at [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tests` | List (filters: `domain`, `priority`, `status`, `repo`, `layer`, `author`, `group`, `runner`) |
| `GET` | `/tests/{id}` | Get by ID |
| `POST` | `/tests` | Create |
| `PATCH` | `/tests/{id}` | Update |
| `DELETE` | `/tests/{id}` | Deprecate |
| `POST` | `/tests/run` | Execute (filters: `domain`, `priority`, `repo`, `layer`) |
| `GET` | `/results` | History |
| `GET` | `/results/summary` | Counts by domain |
| `WS` | `/ws/run` | Real-time stream |

---

## File Naming Conventions

Name your test files following these patterns so `make qa-register` detects them automatically.

### Bash
```
*test*.sh              phase1-smoke-test.sh, auth-flow-test.sh
phase*-*.sh            phase3-authenticated-db-test.sh
```

### Python
```
test_*.py              test_auth.py, test_isolation.py
*-test.py              phase15-mongo-mvp-test.py
*_test.py              user_isolation_test.py
```

### JavaScript / TypeScript
```
*.test.ts              auth.test.ts, api.test.ts
*.test.tsx             LoginForm.test.tsx
*.spec.ts              auth.spec.ts
```

### Always skipped
```
test-ui.sh             helper script
conftest.py            pytest config
jest.config.ts         jest config
*.sql, *.md            not tests
generate-*.sh          utility scripts
```

### Auto-generated IDs

| Repo + filename | Generated ID |
|---|---|
| `mini-baas-infra` + `phase8-token-lifecycle-test.sh` | `BAAS-PHASE08` |
| `transcendence` + `auth.test.ts` | `FT-AUTH` |
| `my-project` + `feature-test.sh` | `MYPR-FEATURE` |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Any project repo                                    │
│  ├── scripts/ or tests/    ← test code              │
│  ├── vendor/qa/            ← QA submodule           │
│  │   └── .env              ← Atlas password         │
│  └── Makefile              ← qa-test, qa-list, ...  │
└──────────────────┬───────────────────────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │   QA System      │
         │  Registry Engine │ → detects + registers scripts
         │  Multi-Runner    │ → bash, http, jest, pytest
         │  Result Store    │ → persists to Atlas
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │  MongoDB Atlas   │
         │  tests           │ → metadata catalog
         │  results         │ → execution history (90d TTL)
         └──────────────────┘
```

---

## Documentation

| Document | Covers |
|----------|--------|
| [docs/usage-guide.md](docs/usage-guide.md) | Daily operations reference |
| [docs/python-guide.md](docs/python-guide.md) | Python onboarding |
| [docs/frontend-guide.md](docs/frontend-guide.md) | CSS/React onboarding |
| [docs/strategy/](docs/strategy/) | Roadmaps 0–6 |

---

## Use of AI

AI tools were used during development: architecture, scaffolding, documentation, and onboarding guides were discussed with Claude and iterated on. Test scripts are written by the team based on direct knowledge of the systems under test.

---

*Main project: [Univers42/transcendence](https://github.com/Univers42/transcendence) · Infrastructure: [Univers42/mini-baas-infra](https://github.com/Univers42/mini-baas-infra)*