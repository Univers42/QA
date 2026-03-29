# Transcendence Testing

This workspace contains the smallest useful frontend test module that can run
directly or be wrapped by the repository JSON battery.

## Goals

- Playwright smoke coverage for login, guarded routes, error screens, and auth
  degradation.
- Reusable header / cookie assertions for dev, preview, and staging.
- Keep the structure small enough to maintain without a second QA subsystem.

## Layout

```text
trascendence_testing/
├── definitions/
│   └── ui/
├── scripts/
└── tests/
    ├── support.ts
    └── *.spec.ts
```

## Install

This suite is intentionally isolated from the Python runner. Install the browser
tooling once:

```bash
make tt-install
```

That installs the local `node_modules` for this folder and stores Playwright's
Chromium bundle inside the repo so the same browser path can be reused by host
commands and by the Python battery when it executes the `bash` wrappers.

## Run Directly

```bash
make tt-smoke ENV=local
make tt-headers ENV=preview
```

## Mongo / Battery Integration

This module owns its own JSON definitions in `trascendence_testing/definitions/`.
The Python runner now loads both the repository root definitions and this module
definitions automatically, so:

```bash
python3 -m prismatica_qa validate
python3 -m prismatica_qa sync
python3 -m prismatica_qa run --domain ui --type bash --env preview
```

If MongoDB is configured, those definitions and their run history are stored in
Mongo the same way as the rest of the suite. The stored test documents also keep
`suite=trascendence_testing` so the module can be queried or reported as a
separate battery later.

## Environment

The wrappers read the shared repo `.env`. Relevant variables are documented in
`.env.example`, especially:

- `TT_BASE_URL`, `TT_DEV_URL`, `TT_PREVIEW_URL`, `TT_STAGING_URL`
- `TT_LOGIN_PATH`, `TT_PROFILE_PATH`, `TT_LOBBY_PATH`, `TT_CHAT_PATH`
- `TT_STORAGE_STATE_PATH`
- `TT_E2E_EMAIL`, `TT_E2E_PASSWORD`
- `TT_COOKIE_NAMES`

## Scope

This minimal version keeps only the pieces that are useful right now:

- Playwright smoke coverage with one focused spec file per test
- reusable header / cookie assertions
- JSON definitions integrated with the Python battery and Mongo history

These items are intentionally postponed until they are really needed:

- visual baselines
- Semgrep and Gitleaks wrappers
- CI workflow templates for this module
