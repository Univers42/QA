# Prismatica QA — AI Unblocking Guide

*For developers who are stuck. Copy the prompts, paste them into any AI assistant, and replace the `[BRACKETS]` with your actual situation.*

*This guide assumes you have read `how-to-add-a-test.md`. If you have not, read it first — it is short.*

---

## Before you start — understanding TDD and red-green-refactor

This section is not a blocking situation. It is background you need before writing any test. Read it once.

### What TDD means in this project

TDD (Test-Driven Development) means you write the test before writing the implementation. The reason is not discipline for its own sake — it is because writing the test forces you to answer one question first: *what does success look like?* If you cannot describe the expected behaviour, you do not yet understand the feature well enough to build it.

### The red-green-refactor cycle

TDD works in three steps that repeat in a loop:

**Red — write the test first, watch it fail.**
Write the JSON test document. Set `status` to `"active"`. Run `make test`. It fails — the feature does not exist yet. This failure is correct and expected. A red test is not a problem. It is a specification written in a language the machine can check.

**Green — write just enough to make it pass.**
Implement the minimum change in the service to make the test pass. Not the best code. Not the clean architecture. Just enough to go from red to green. Run `make test` again and confirm it passes.

**Refactor — clean up while staying green.**
Now that the test passes, improve the implementation. Rename things, extract functions, remove duplication. Run `make test` after each change. If it turns red again, you broke something — revert the last change and try again.

### What the cycle looks like in this project

```
Red:      Write the JSON test document with status: "active"
          Run: make test DOMAIN=[your domain]
          Expected result: the test fails (the feature does not exist yet)

Green:    Implement the feature in the relevant service
          (GoTrue config, Kong route, PostgREST endpoint, schema-service handler...)
          Run: make test DOMAIN=[your domain]
          Expected result: the test passes

Refactor: Clean up the implementation
          Run: make test DOMAIN=[your domain] after each change
          Expected result: stays green throughout
```

The first time you do this it feels backwards. You will want to build the feature first and then prove it works. Resist that. The test written before implementation is a different thing from the test written after — it captures what you intended, not what you accidentally built.

---

## How to use the rest of this document

Each section below covers one blocking situation. Find the one that matches where you are stuck, copy the prompt block, paste it into Claude, ChatGPT, or any AI assistant, and replace the `[BRACKETS]` with your actual situation.

Every prompt includes the minimum context the AI needs to give you a useful answer. Do not skip the context block — without it the AI will give you generic advice that does not apply to this project.

---

## Situation 1 — I do not know how to write this test in JSON

Use this when you know what behaviour you want to test but cannot figure out how to express it as a test definition document.

### Prompt to copy

```
I am working on a QA repository for a project called Prismatica / ft_transcendence.
We use a Data-Driven Automation (DDA) strategy: tests are JSON documents stored in
MongoDB. A generic Node.js runner reads each document, makes one HTTP call, and
checks the response against the expected fields.

Here is the JSON schema a test document must follow:

Required fields: id, title, domain, type, layer, priority, expected, status.

The "expected" object can contain:
- statusCode: number (HTTP status code)
- bodyContains: array of strings that must appear in the response body
- jwtClaims: object with fields that must exist in the decoded JWT
- cookieSet: name of a cookie that must be set

The runner makes exactly ONE HTTP call per test document. It cannot chain calls
or store state between tests. If a test requires a precondition (for example, a
user must exist), that precondition is written in the "preconditions" field as
documentation — it is not executed automatically.

The domains are: auth, gateway, schema, api, realtime, storage, ui, infra.
Priority levels: P0 (blocks merge), P1 (critical), P2 (degraded), P3 (informational).
Status values: active (runner executes it), draft (runner skips it), deprecated, skipped.

The behaviour I want to test is:
[DESCRIBE WHAT SHOULD HAPPEN IN ONE OR TWO SENTENCES]

The service involved is: [SERVICE NAME — e.g. GoTrue, Kong, PostgREST, MinIO]
The URL I think I need to call is: [URL OR "I don't know yet"]
The HTTP method is: [GET / POST / PATCH / DELETE / "I don't know yet"]

Please write the complete JSON document for this test. Use status "draft" since
I have not yet confirmed it passes. Use my login [YOUR 42 LOGIN] as the author field.
Set phase to [phase-0 / phase-1 / etc.].

After the JSON, explain each field you filled in and why, so I can learn the pattern.
```

### What to do with the output

1. Read the explanation the AI gives — do not just copy the JSON blindly.
2. Save the file to `test-definitions/[domain]/[ID].json`.
3. Run `make validate` — if it fails, paste the error back to the AI and ask it to fix it.
4. Run `make seed`.
5. Change `status` from `"draft"` to `"active"` only once you have confirmed the test passes against a running service.

---

## Situation 2 — The runner fails and I do not know why

Use this when `make test` produces an error or unexpected result and you cannot figure out what is wrong.

### Before using the AI — check these first

These are the most common causes of runner failures, in order of likelihood:

1. **The service is not running.** Run `docker ps` or check `mini-baas-infra`. If Kong is not up, every gateway test will fail.
2. **The URL in the JSON is wrong.** Copy the URL from the JSON and paste it directly into `curl`. Does it respond?
3. **The test is draft, not active.** The runner skips `"status": "draft"` tests. If your test is not appearing in results, check its status.
4. **MongoDB is not running.** Run `make up` first.
5. **The `.env` file is missing or wrong.** Compare with `.env.example`.

If none of these fix it, use the prompt below.

### Prompt to copy

```
I am debugging a test failure in a QA repository that uses Data-Driven Automation.
Tests are JSON documents. A Node.js runner reads them from MongoDB, makes an HTTP
call, and checks the response.

Here is the test document that is failing:
[PASTE THE COMPLETE JSON OF THE FAILING TEST]

Here is the error or unexpected output I see in the terminal:
[PASTE THE EXACT ERROR MESSAGE OR OUTPUT]

Here is what I have already checked:
[LIST WHAT YOU TRIED — e.g. "the service is running", "curl to the URL works",
"make validate passes", "the .env file matches .env.example"]

The runner is structured like this:
- It reads the test from MongoDB
- It calls test.url with test.method and test.headers / test.payload
- It checks response.status === expected.statusCode
- It checks the response body contains all strings in expected.bodyContains
- It writes a result document to MongoDB with passed: true/false

Please tell me:
1. What is most likely causing this failure based on the error and the JSON?
2. What should I change in the JSON to fix it?
3. If the problem is in the service and not the JSON, what should I check in
   [SERVICE NAME] to make this test pass?
```

---

## Situation 3 — I do not know which domain or priority to choose

Use this when you have a test in mind but are unsure where it belongs.

### The quick answer before reaching for the AI

**For domain**, ask yourself: *which service would I restart if this test fails?*

- Restart GoTrue → `auth`
- Restart Kong → `gateway`
- Restart PostgREST → `api`
- Restart schema-service → `schema`
- Restart Supabase Realtime → `realtime`
- Restart MinIO → `storage`
- Restart the React dev server → `ui`
- Restart Docker / the whole stack → `infra`

**For priority**, ask yourself: *if this fails in production right now, what happens?*

- Nobody can use the application at all → `P0`
- A major feature (login, data access, file upload) is broken → `P1`
- Something works but in a degraded way → `P2`
- A minor detail is wrong but nobody is blocked → `P3`

If the quick answer above is not enough, use this prompt.

### Prompt to copy

```
I am writing a test for a QA repository. I need help choosing the right domain
and priority.

The test I want to write is:
[DESCRIBE THE BEHAVIOUR YOU ARE TESTING IN ONE OR TWO SENTENCES]

The service or component involved is: [NAME]

The domains available are:
- auth: GoTrue — login, OAuth, JWT, sessions
- gateway: Kong — routing, rate limiting, CORS, JWT validation
- schema: schema-service — DDL lifecycle, collections, fields
- api: PostgREST — endpoints, filters, RLS
- realtime: Supabase Realtime — WebSocket
- storage: MinIO — presigned URLs, file upload
- ui: React frontend — components, hooks, stores
- infra: Docker, health checks, infrastructure

The priority levels are:
- P0: system cannot function without this (blocks merge)
- P1: critical feature broken (blocks merge)
- P2: degraded experience (warning only)
- P3: informational (report only)

Please recommend:
1. Which domain this test belongs to and why
2. Which priority this test should have and why
3. Whether this test should be split into multiple tests (one per observable behaviour)
4. Any fields in the JSON I should pay special attention to for this particular case
```

---

## General rules for working with AI on this project

**Always share the JSON schema context.** Without it the AI will suggest test structures that do not match what the runner expects. The prompts above already include the necessary context — do not strip it out.

**Paste the actual content, not a description of it.** If you are debugging, paste the exact error message. If you are asking about a test, paste the exact JSON. Descriptions introduce ambiguity.

**Ask for explanations, not just output.** The prompts above include "explain each field you filled in". Keep that line. If you only get the JSON without understanding why, you will be stuck again on the next test.

**Start with status: draft.** Never set a test to `"active"` until you have seen it pass against a running service. An active test that fails blocks the whole team in CI.

**One behaviour per test.** If an AI gives you a test that checks five things at once, ask it to split them. The rule is: one test should fail for one reason.

---

## Reference — minimum context block for any new AI conversation

Paste this at the start of any new conversation before asking your question:

```
Context for this conversation:

I am working on prismatica-qa, the QA repository for a project called
Prismatica / ft_transcendence (a 42 school project).

Architecture:
- Tests are JSON documents stored in git under test-definitions/
- A seed script loads them into MongoDB (test_hub database)
- A generic Node.js/TypeScript runner reads from MongoDB and makes HTTP calls
- Results are written back to MongoDB and displayed in a terminal table
- This is called Data-Driven Automation (DDA): tests are data, not code

The services under test (running separately in mini-baas-infra):
- Kong :8000 — API gateway
- GoTrue :9999 — authentication
- PostgREST :3000 — auto-generated REST from PostgreSQL schema
- Supabase Realtime :4001 — WebSocket / database change events
- MinIO :9000 — object storage
- React frontend :5173

Test document required fields: id, title, domain, type, layer, priority, expected, status
Domains: auth, gateway, schema, api, realtime, storage, ui, infra
Priority: P0 (blocks merge), P1 (critical), P2, P3
Status: active (runner executes), draft (runner skips), deprecated, skipped

The runner makes ONE HTTP call per test. It cannot chain calls or store state.
Preconditions are documentation only — they are not executed automatically.

My question: [YOUR QUESTION HERE]
```

---

*This guide is a companion to `how-to-add-a-test.md`.*
*When a situation is not covered here, open an issue in the QA repo or ask dlesieur.*
