# Prismatica QA — Usage Guide

*Quick reference for daily operations. Pin this to your terminal.*

---

## First Time Setup

```bash
git clone https://github.com/Univers42/QA.git
cd QA
make                    # installs Python, venv, dependencies, git hooks
nano .env               # set MONGO_URI_ATLAS with your Atlas password
make test               # verify everything works (some tests will fail — that's OK)
```

---

## Everyday Commands

### See what tests exist

```bash
make list                       # all tests
make list DOMAIN=auth           # only auth domain
make list STATUS=active         # only active tests
make list PRIORITY=P0           # only blocking tests
```

### Run tests

```bash
make test                       # all active tests
make test DOMAIN=auth           # only auth
make test PRIORITY=P0           # only P0 (blocking)
make test ID=AUTH-003           # one specific test
```

### Create a new test

```bash
make add                        # interactive mode — guides you step by step
```

Or in one line (quick mode):

```bash
.venv/bin/pqa test add --quick \
  --id AUTH-005 \
  --title "Signup with valid email creates account" \
  --domain auth \
  --priority P1 \
  --type http \
  --url "http://localhost:9999/auth/v1/signup" \
  --method POST \
  --expected-status 200 \
  --expected-body access_token \
  --author your_42_login
```

### Edit or delete a test

```bash
make edit ID=AUTH-003           # interactive edit with diff preview
make delete ID=AUTH-003         # marks as deprecated (soft delete)
```

### Export and sync

```bash
make export                     # export all tests from Atlas → JSON files
make export DOMAIN=auth         # export only auth tests
```

Always commit the JSON files after export:

```bash
git add test-definitions/
git commit -m "test(auth): Add AUTH-005 signup test"
```

---

## Start the API Server

```bash
make api                        # starts on http://localhost:8000
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI where you can test all endpoints from your browser.

---

## Code Quality

```bash
make lint                       # check PEP 8 compliance (read-only)
make fix                        # auto-fix lint issues
make format                     # format code + fix issues
```

Run `make format` before committing if your editor doesn't auto-format Python.

---

## Domain Reference

Use this table when choosing which domain a test belongs to.

| Domain | ID Prefix | Folder | What it tests |
|--------|-----------|--------|---------------|
| `auth` | `AUTH-` | `test-definitions/auth/` | GoTrue — login, OAuth, JWT, sessions |
| `gateway` | `GW-` | `test-definitions/gateway/` | Kong — routing, rate limiting, CORS |
| `schema` | `SCH-` | `test-definitions/schema/` | schema-service — collections, fields, DDL |
| `api` | `API-` | `test-definitions/api/` | PostgREST or QA API — endpoints, filters, RLS |
| `realtime` | `RT-` | `test-definitions/realtime/` | Supabase Realtime — WebSocket, subscriptions |
| `storage` | `STG-` | `test-definitions/storage/` | MinIO — file upload, presigned URLs |
| `ui` | `UI-` | `test-definitions/ui/` | React frontend — components, hooks, stores |
| `infra` | `INFRA-` | `test-definitions/infra/` | Docker, health checks, Atlas, infrastructure |

---

## Priority Guide

| Priority | Meaning | CI effect | When to use |
|----------|---------|-----------|-------------|
| `P0` | System cannot function | Blocks merge | Health checks, login, core API |
| `P1` | Critical feature broken | Blocks merge | Key user flows, security |
| `P2` | Degraded experience | Warning only | Non-critical features, edge cases |
| `P3` | Nice to have | Report only | Cosmetic, performance, polish |

---

## Test Types

| Type | Executor | Fields needed | Example |
|------|----------|---------------|---------|
| `http` | Makes an HTTP call | `url`, `method`, `expected` | Check that `/health` returns 200 |
| `bash` | Runs a shell command | `script`, `expected_exit_code` | Check that `pg_isready` succeeds |
| `manual` | Skipped by runner | `notes` (optional) | "Verify the error message appears" |

---

## Test Lifecycle

```
draft → active → deprecated
  ↓        ↓
  ↓     skipped → active
  ↓
deprecated
```

- **draft** — the test exists as a specification but hasn't been verified against a running environment. The runner ignores it.
- **active** — the test passes and is executed on every run. Failing active tests block CI.
- **skipped** — there is a known blocker (e.g. service not running). Always add a `notes` field explaining why.
- **deprecated** — the feature was removed or the test was replaced.

**Rule:** new tests always start as `draft`. Only set to `active` after confirming it passes.

---

## Commit Format

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): Description (25-170 chars, starts uppercase, no trailing period)
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`, `ci`, `build`, `revert`

**Examples:**

```bash
git commit -m "test(auth): Add AUTH-005 signup with valid email"
git commit -m "fix(runner): Resolve timeout handling in HTTP executor"
git commit -m "docs(readme): Update architecture diagram for v3"
git commit -m "chore(deps): Upgrade FastAPI to 0.110.0"
```

The git hooks enforce this format automatically.

---

## Troubleshooting

**`pqa: command not found`**
Use `.venv/bin/pqa` or activate the venv first: `source .venv/bin/activate`

**`MONGO_URI_ATLAS is not set`**
Copy `.env.example` to `.env` and fill in your Atlas password.

**`connection refused: http://localhost:9999/...`**
The service under test (GoTrue, PostgREST, etc.) is not running. Start mini-baas-infra first. This is expected behaviour — not a bug in the QA system.

**`make api` and tests fail at the same time**
The QA API and the services under test may use the same port (8000). If Kong runs on 8000, change `API_PORT` in `.env` to 8001 and update the API-00x test URLs.

**Pre-commit hook blocks my commit**
Read the error message — it tells you exactly what to fix. If you need to bypass temporarily: `SKIP_PRE_COMMIT=1 git commit ...`

**Commit message rejected**
Must be `type(scope): Description` with 25+ chars. See examples above. Bypass: `SKIP_COMMIT_MSG=1 git commit ...`

---

## All Make Commands at a Glance

| Command | What it does |
|---------|-------------|
| `make` | Full setup (install + hooks) |
| `make api` | Start API on :8000 |
| `make test` | Run all active tests |
| `make test DOMAIN=auth` | Run auth tests |
| `make test PRIORITY=P0` | Run P0 tests |
| `make test ID=AUTH-003` | Run one test |
| `make list` | List all tests |
| `make list DOMAIN=auth` | List auth tests |
| `make list STATUS=draft` | List draft tests |
| `make add` | Create test (interactive) |
| `make edit ID=AUTH-003` | Edit a test |
| `make delete ID=AUTH-003` | Deprecate a test |
| `make export` | Atlas → JSON files |
| `make migrate` | JSON files → Atlas |
| `make lint` | Check PEP 8 |
| `make fix` | Auto-fix lint |
| `make format` | Format + fix |
| `make hooks` | Install git hooks |
| `make clean` | Remove venv + caches |
| `make help` | Show categorised help |

---

*For detailed test authoring: [docs/how-to-add-a-test.md](how-to-add-a-test.md)*
*For architecture: [README.md](../README.md)*
*For Python intro: [docs/python-guide.md](python-guide.md)*
