# Prismatica QA — Roadmap 6

*From Data-Driven Automation to Test Registry: QA becomes the catalog, tests stay in their repos.*

*March 2026 · Version 1.0 · Univers42*

---

## Table of Contents

- [1. The Paradigm Shift](#1-the-paradigm-shift)
- [2. Architecture — Registry Model](#2-architecture--registry-model)
- [3. What a Registry Entry Looks Like](#3-what-a-registry-entry-looks-like)
- [4. How Execution Works](#4-how-execution-works)
- [5. Result Persistence](#5-result-persistence)
- [6. Developer Identity and Codeownership](#6-developer-identity-and-codeownership)
- [7. Multi-Repo Integration](#7-multi-repo-integration)
- [8. CLI Changes](#8-cli-changes)
- [9. API Changes](#9-api-changes)
- [10. What Disappears vs What Stays](#10-what-disappears-vs-what-stays)
- [11. Migration Plan](#11-migration-plan)
- [12. Tradeoffs and Open Decisions](#12-tradeoffs-and-open-decisions)
- [13. Implementation Phases](#13-implementation-phases)
- [14. Next Steps](#14-next-steps)

---

## 1. The Paradigm Shift

### What we built (Roadmaps 0–5): Data-Driven Automation

Tests were JSON documents stored in Atlas. A generic runner read each document, made the HTTP call, and checked the response. The test definition and the execution logic lived together in the QA system.

```
QA owned everything: definition + execution + results
```

### What exists in reality

mini-baas-infra already has 13 phases of bash test scripts — real, working, comprehensive tests that cover smoke checks, auth flows, HTTP methods, token lifecycle, storage operations, error handling, rate limiting, CORS, and WebSocket. These are not JSON documents — they are executable code written by the infrastructure team.

transcendence has its own tests (Jest/Vitest for frontend, potentially pytest for backend).

### What we need now: Test Registry

QA becomes a **catalog and result store**. Tests live as scripts in each repo. QA knows about them (metadata), can launch them (execution), and remembers what happened (results).

```
Before (DDA):
  QA defines tests → QA executes tests → QA stores results

After (Registry):
  Repos define tests → QA registers metadata → QA orchestrates execution → QA stores results
```

This is not a theoretical redesign. It is driven by what already exists.

---

## 2. Architecture — Registry Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  transcendence/                        mini-baas-infra/             │
│  ├── tests/                            ├── scripts/                 │
│  │   ├── jest.config.ts                │   ├── phase1-smoke.sh      │
│  │   ├── auth.test.ts                  │   ├── phase2-smoke.sh      │
│  │   └── components.test.tsx           │   ├── ...                  │
│  └── Makefile                          │   ├── phase13-cors.sh      │
│      make qa-test                      │   └── test-ui.sh           │
│      make qa-register                  └── Makefile                 │
│                                            make qa-test              │
│                                            make qa-register          │
│                                                                     │
│                        ┌──────────────────┐                         │
│                        │   QA Repository   │                         │
│                        │   (submodule or   │                         │
│                        │    cloned in CI)  │                         │
│                        │                  │                         │
│                        │  ┌────────────┐  │                         │
│                        │  │ Registry   │  │  "What tests exist"     │
│                        │  │ Engine     │──┼──────────────────────┐  │
│                        │  └────────────┘  │                      │  │
│                        │  ┌────────────┐  │                      ▼  │
│                        │  │ Executor   │  │  ┌─────────────────────┐│
│                        │  │ (launches  │  │  │   MongoDB Atlas     ││
│                        │  │  scripts)  │  │  │                     ││
│                        │  └────────────┘  │  │  tests collection   ││
│                        │  ┌────────────┐  │  │   (metadata only)   ││
│                        │  │ Result     │  │  │                     ││
│                        │  │ Collector  │──┼─▶│  results collection ││
│                        │  └────────────┘  │  │   (execution data)  ││
│                        │                  │  └─────────────────────┘│
│                        └──────────────────┘                         │
│                                                                     │
│  Dashboard (future)                                                 │
│  └── Browser UI showing registry + results from Atlas               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key principle

**Tests are code. QA is the catalog.**

QA does not define what a test does (that is the script's job). QA knows:
- That the test exists (metadata)
- Where it lives (repo + path)
- How to run it (command)
- What happened when it ran (results)

---

## 3. What a Registry Entry Looks Like

### The old DDA model (Roadmap 5)

```json
{
  "id": "AUTH-001",
  "title": "Login with valid credentials returns access token",
  "type": "http",
  "url": "http://localhost:9999/auth/v1/token?grant_type=password",
  "method": "POST",
  "payload": {"email": "test@prismatica.dev", "password": "TestPassword42!"},
  "expected": {"statusCode": 200, "bodyContains": ["access_token"]}
}
```

The test definition IS the test. QA knows everything: the URL, the payload, what to check.

### The new Registry model (Roadmap 6)

```json
{
  "id": "BAAS-PHASE08",
  "title": "Token lifecycle and refresh — JWT validation suite",
  "description": "13 checks: signup token generation, JWT structure, claims validation, token refresh, malformed token rejection",

  "repo": "mini-baas-infra",
  "script": "scripts/phase8-token-lifecycle-test.sh",
  "runner": "bash",

  "domain": "auth",
  "layer": "backend",
  "phase": "phase-8",
  "priority": "P1",
  "status": "active",

  "author": "vjan-nie",
  "group": "backend",
  "tags": ["jwt", "token", "refresh", "gotrue", "auth"],

  "env_vars": {
    "BASE_URL": "http://localhost:8000",
    "APIKEY": "public-anon-key"
  },

  "created_at": "2026-03-28T10:00:00Z",
  "updated_at": "2026-03-28T10:00:00Z"
}
```

QA knows the test exists and how to launch it, but not what it does internally. The script handles all assertions, setup, and teardown. QA captures the exit code and (optionally) the stdout.

### The metadata vs the script

```
┌──────────────────────────────────────────────┐
│  Atlas (metadata)                            │
│                                              │
│  id: BAAS-PHASE08                             │
│  script: scripts/phase8-token-lifecycle.sh   │
│  repo: mini-baas-infra                       │
│  last_run: 2026-03-28 passed in 3200ms       │
│                                              │
│  QA does NOT store:                          │
│  - The script content                        │
│  - The assertions                            │
│  - The expected values                       │
│  - The test logic                            │
│                                              │
│  Those live in the script file in the repo.  │
└──────────────────────────────────────────────┘
```

---

## 4. How Execution Works

### The executor

When QA runs a registered test, it:

1. Reads the registry entry from Atlas
2. Resolves the script path (relative to the repo root)
3. Sets the environment variables from the entry
4. Runs the script via subprocess
5. Captures: exit code, stdout, stderr, duration
6. Writes the result to Atlas

```python
async def execute_registered_test(entry: dict, repo_root: str) -> dict:
    """Execute a registered test script and capture results."""
    script = entry["script"]
    runner = entry.get("runner", "bash")
    env_vars = entry.get("env_vars", {})
    timeout = entry.get("timeout_seconds", 120)

    full_path = os.path.join(repo_root, script)

    env = {**os.environ, **env_vars}

    start = time.perf_counter()
    result = subprocess.run(
        [runner, full_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=repo_root,
    )
    duration_ms = round((time.perf_counter() - start) * 1000)

    return {
        "test_id": entry["id"],
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "duration_ms": duration_ms,
        "stdout_tail": result.stdout[-2000:] if result.stdout else None,
        "stderr_tail": result.stderr[-500:] if result.stderr else None,
    }
```

### What about the existing DDA tests (HTTP)?

The old HTTP executor still works for tests with `"runner": "http"`. These are the tests we built in Roadmaps 1–5 (INFRA-003, API-001, etc.). They coexist with registered scripts:

```
runner == "bash"   → subprocess, execute the script
runner == "http"   → httpx, make the HTTP call (legacy DDA behavior)
runner == "jest"   → npx jest --testPathPattern=<script>
runner == "pytest" → python -m pytest <script>
```

The registry model is a superset of DDA. Old tests keep working.

---

## 5. Result Persistence

### What gets stored per execution

```json
{
  "test_id": "BAAS-PHASE8",
  "passed": true,
  "exit_code": 0,
  "duration_ms": 3200,
  "stdout_tail": "...last 2000 chars of output...",
  "tests_passed": 13,
  "tests_failed": 0,

  "repo": "mini-baas-infra",
  "run_by": "vjan-nie",
  "environment": "local",
  "executed_at": "2026-03-28T10:05:00Z",
  "git_sha": "a1b2c3d"
}
```

### Parsing test counts from stdout

The bash scripts in mini-baas-infra already print structured summaries via `test-ui.sh`:

```
╔════════════════════════════════════════════════════════════╗
║ Test Summary
╠════════════════════════════════════════════════════════════╣
║ ✔ Passed: 13
║ ✖ Failed: 0
║ Total : 13
╚════════════════════════════════════════════════════════════╝
```

The result collector can parse this to extract `tests_passed` and `tests_failed` from the stdout. This gives granularity (13 individual checks within one script) without requiring each script to report to Atlas individually.

---

## 6. Developer Identity and Codeownership

### Identity: PQA_USER

Each developer sets `PQA_USER=their_42_login` in their environment. This is used as:
- `author` when registering a test
- `run_by` when executing tests
- Identity check when editing/deleting another developer's test

### Group-based access control

Instead of per-developer permissions, tests have a `group` field:

```
group: "backend"    → backend team owns these
group: "frontend"   → frontend team owns these
group: "infra"      → infrastructure team owns these
group: "qa"         → QA admin owns these
```

Access rules (enforced in the API, not in Atlas):
- **Read/Run**: everyone can see and run any test
- **Edit/Delete**: requires `PQA_USER` to be the `author`, OR same `group`
- **Admin override**: `PQA_USER=admin` can do anything

This is implemented as a simple check in the API, not as MongoDB roles. For 4–6 developers, this is sufficient.

---

## 7. Multi-Repo Integration

### QA as submodule (recommended for now)

```bash
# In mini-baas-infra:
git submodule add https://github.com/Univers42/QA.git qa

# In transcendence:
git submodule add https://github.com/Univers42/QA.git qa
```

The submodule lives at `qa/` in each repo. Make rules reference it directly:

```makefile
# In mini-baas-infra/Makefile:
QA_DIR := qa
PQA := $(QA_DIR)/.venv/bin/pqa

qa-setup:  ## Install QA submodule dependencies
	@cd $(QA_DIR) && make install

qa-test:  ## Run registered tests (LAYER=backend DOMAIN=auth)
	@$(PQA) test run \
		--repo mini-baas-infra \
		$(if $(LAYER),--layer $(LAYER)) \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		$(if $(PRIORITY),--priority $(PRIORITY))

qa-register:  ## Register all test scripts in Atlas
	@$(PQA) test register --repo mini-baas-infra --scan scripts/

qa-list:  ## List tests for this repo
	@$(PQA) test list --repo mini-baas-infra

qa-my:  ## List my tests
	@$(PQA) test list --author $(PQA_USER)
```

### CI integration (clone in GitHub Actions)

```yaml
- name: Run QA tests
  run: |
    git clone --depth 1 https://github.com/Univers42/QA.git /tmp/qa
    cd /tmp/qa && pip install -r requirements.txt -q && pip install -e . -q
    PQA_USER=ci python -m runner.ci --repo mini-baas-infra --priority P0
  env:
    MONGO_URI_ATLAS: ${{ secrets.MONGO_URI_ATLAS }}
```

### Auto-registration: `pqa test register --scan`

Instead of manually creating registry entries for each script, `pqa test register --scan scripts/` reads the directory, detects test scripts by naming convention, and registers them:

```
$ pqa test register --repo mini-baas-infra --scan scripts/

  Scanning scripts/ for test files...

  ✓  BAAS-PHASE01  phase1-smoke-test.sh            (new)
  ✓  BAAS-PHASE02  phase2-smoke-test.sh            (new)
  ✓  BAAS-PHASE03  phase3-authenticated-db-test.sh (new)
  ...
  ✓  BAAS-PHASE13  phase13-cors-preflight-test.sh  (new)
  —  test-ui.sh    skipped (helper, not a test)
  —  db-bootstrap.sql  skipped (not a test script)

  Registered 13 tests · 0 updated · 2 skipped
```

Detection rules:
- Files matching `*test*.sh` or `phase*-*.sh` → registered as bash tests
- Files matching `*.test.ts` or `*.test.tsx` → registered as jest tests
- Files matching `test_*.py` or `*_test.py` → registered as pytest tests
- Files named `test-ui.sh`, `conftest.py`, etc. → skipped (helpers)

The ID is auto-generated from the filename: `phase8-token-lifecycle-test.sh` → `BAAS-PHASE08`. The developer can edit the metadata afterwards via `pqa test edit`.

---

## 8. CLI Changes

### New commands

```
pqa test register --repo <name> --scan <dir>    Register test scripts from a directory
pqa test register --repo <name> --script <path> Register a single script
```

### Updated commands

```
pqa test list --repo mini-baas-infra    Filter by repo
pqa test list --layer backend           Filter by development layer
pqa test list --group backend           Filter by team group
pqa test list --author vjan-nie         Filter by codeowner
pqa test list --mine                    Shortcut for --author $PQA_USER

pqa test run --repo mini-baas-infra     Run tests for a specific repo
pqa test run --layer frontend           Run frontend tests from any repo
pqa test run --mine                     Run only my tests

pqa test edit BAAS-PHASE08              Edit metadata (ownership check)
pqa test delete BAAS-PHASE08            Deprecate (ownership check)
```

### Removed commands

```
pqa test export        # No more JSON files on disk
```

`pqa test add` (interactive) still exists for creating simple HTTP tests or manual specs that don't have a script file.

---

## 9. API Changes

### New endpoints

```
POST /tests/register              Register a test from script metadata
POST /tests/register/scan         Scan a directory and register all tests
```

### Updated query parameters

```
GET /tests?repo=mini-baas-infra
GET /tests?layer=backend
GET /tests?group=backend
GET /tests?author=vjan-nie
GET /results?repo=mini-baas-infra
```

### Updated execution

```
POST /tests/run?repo=mini-baas-infra    Run all active tests for a repo
POST /tests/run?layer=backend           Run all backend tests
```

The executor checks the `runner` field to decide how to launch the test:
- `runner: "bash"` → subprocess
- `runner: "http"` → httpx (legacy DDA)
- `runner: "jest"` → `npx jest`
- `runner: "pytest"` → `python -m pytest`

---

## 10. What Disappears vs What Stays

### Disappears

| Item | Why |
|------|-----|
| `test-definitions/` directory | Tests live in their repos, not as JSON in QA |
| `core/git_export.py` | No JSON files to export |
| `scripts/migrate_v1_to_v2.py` | No migration needed |
| `make migrate` | No JSON to migrate |
| `make export` | No JSON to export |

### Stays and evolves

| Item | Change |
|------|--------|
| `core/db.py` | Unchanged — Atlas connection |
| `core/schema.py` | New `RegistryEntry` model, add `Layer` enum, `runner` field |
| `runner/executor.py` | Extended: dispatch by runner type (bash/http/jest/pytest) |
| `runner/results.py` | Extended: stdout parsing for test counts |
| `api/` | New endpoints for register/scan, new filters |
| `cli/` | New `register` command, updated filters |
| `vendor/hooks/` | Unchanged |
| `Makefile` | Simplified (remove migrate/export, add register) |

### Backward compatibility

Old HTTP-type tests (API-001, INFRA-003, etc.) continue to work. They have `"runner": "http"` and the executor handles them with httpx. No existing test breaks.

---

## 11. Migration Plan

### Phase M0 — Schema + new fields (nothing breaks)

Add `repo`, `layer`, `group`, `runner`, `script`, `env_vars` as optional fields to the schema. Add `PQA_USER` handling. All existing tests keep working — new fields default to `None`.

### Phase M1 — Registry executor

Build the new executor that dispatches by `runner` type. Test it with one mini-baas-infra script manually registered.

### Phase M2 — Auto-registration (`pqa test register --scan`)

Build the scan logic that reads a directory, detects test scripts, and registers them in Atlas. Run it against mini-baas-infra's `scripts/` directory.

### Phase M3 — Multi-repo Make rules

Create Make rules for consuming repos. Add QA as submodule in mini-baas-infra. Test from mini-baas-infra.

### Phase M4 — Remove test-definitions/

Delete the old JSON files and related code. Atlas is the sole source.

### Phase M5 — Ownership and group access

Add `check_ownership()` to edit/delete. Implement group-based access checks in the API.

---

## 12. Tradeoffs and Open Decisions

### Tradeoffs accepted

| Tradeoff | Decision | Reason |
|----------|----------|--------|
| QA doesn't know test internals | Accepted | Tests are code in each repo. QA tracks metadata and results. |
| stdout parsing is fragile | Accepted | Works for `test-ui.sh` format. Fails gracefully (counts = 0). |
| Submodule adds complexity | Accepted for now | Better than cloning each time. Docker image is the future. |
| Old HTTP tests coexist with new registry | Accepted | Backward compatible. Migrate gradually. |

### Open decisions

**ID format for registered tests:** `BAAS-PHASE08` or `INFRA-PHASE08` or auto-generated? Recommendation: `{REPO_PREFIX}-{FILENAME_STEM}` auto-generated, editable.

**Should `pqa test run` for a registered bash test require the repo to be present locally?** Yes — the script file must exist at the path. This means either submodule is checked out or QA is running from within the repo.

**How does the dashboard show registered tests?** Same table as before, with additional columns: repo, runner, last result. Clicking "Run" on a registered test requires the repo context (the API needs to know where the script lives).

---

## 13. Implementation Phases

```
🔴 Phase M0 — Schema evolution (~3h)
    Add new fields to Pydantic model
    Add PQA_USER handling
    Add --layer, --repo, --group, --author filters to CLI + API
    All existing tests keep working
        │
        ▼
🔴 Phase M1 — Registry executor (~4h)
    Build multi-runner executor (bash/http/jest/pytest)
    Manually register one mini-baas-infra script
    Verify execution + result persistence
        │
        ▼
🟡 Phase M2 — Auto-registration (~3h)
    pqa test register --scan scripts/
    Auto-detect test files by naming convention
    Register 13 mini-baas-infra phases in Atlas
        │
        ▼
🟡 Phase M3 — Multi-repo integration (~2h)
    Add QA as submodule in mini-baas-infra
    Create Make rules (qa-test, qa-list, qa-register)
    Test from mini-baas-infra
        │
        ▼
🟢 Phase M4 — Remove test-definitions/ (~1h)
    Delete old JSON files
    Remove git_export, migrate
    Update documentation
        │
        ▼
🟢 Phase M5 — Ownership + groups (~2h)
    PQA_USER ownership checks
    Group-based access in API
    Dashboard preparation
```

---

## 14. Next Steps

### Immediate — Phase M0

Start with the schema changes. This is purely additive:

Files to modify:
- `core/schema.py` — add `RegistryEntry` model, `Layer` enum, `runner` field
- `core/db.py` — add new indexes (repo, layer, author, group)
- `cli/commands/list_cmd.py` — add `--repo`, `--layer`, `--author`, `--mine`, `--group` flags
- `cli/commands/run_cmd.py` — add `--repo`, `--layer` flags
- `cli/commands/add_cmd.py` — auto-set `author` from `PQA_USER`, add `layer` prompt
- `api/routers/tests.py` — add query parameters
- `api/routers/run.py` — add query parameters

### Then — Phase M1

Build `runner/registry_executor.py` and test it with `phase1-smoke-test.sh` from mini-baas-infra.

### Then — Phase M2

The auto-registration command. This is the moment the 13 mini-baas-infra scripts appear in Atlas and can be tracked, filtered, and executed from the QA system.

---

*This document reflects the paradigm shift from DDA to Test Registry, informed by the real test suites in mini-baas-infra.*
*Previous: [5-roadmap.md](5-roadmap.md) · Main README: [README.md](../../README.md)*