# Python for Prismatica QA — A Practical Guide

*Everything you need to understand and contribute to this codebase, explained through the code itself.*

*March 2026 · dlesieur*

---

## Table of Contents

- [0. Who This Guide Is For](#0-who-this-guide-is-for)
- [1. Project Infrastructure — The Files That Are Not Code](#1-project-infrastructure--the-files-that-are-not-code)
- [2. Python Fundamentals — Through Our Code](#2-python-fundamentals--through-our-code)
- [3. How Python Imports Work — Packages and Modules](#3-how-python-imports-work--packages-and-modules)
- [4. Type Hints — Python's Type System](#4-type-hints--pythons-type-system)
- [5. Pydantic — Validation That Replaces AJV](#5-pydantic--validation-that-replaces-ajv)
- [6. Async / Await — Why the Runner Uses It](#6-async--await--why-the-runner-uses-it)
- [7. FastAPI — How the API Layer Works](#7-fastapi--how-the-api-layer-works)
- [8. pymongo — Talking to MongoDB from Python](#8-pymongo--talking-to-mongodb-from-python)
- [9. The Global Pattern — How db.py Manages State](#9-the-global-pattern--how-dbpy-manages-state)
- [10. Error Handling — try/except Instead of try/catch](#10-error-handling--tryexcept-instead-of-trycatch)
- [11. How Everything Connects — A Full Request Traced](#11-how-everything-connects--a-full-request-traced)
- [12. Common Gotchas Coming from C/C++ or JavaScript](#12-common-gotchas-coming-from-cc-or-javascript)

---

## 0. Who This Guide Is For

You know C from 42. You might know some JavaScript or TypeScript from transcendence. You have never written Python, or you wrote some once and forgot. This guide will not teach you Python from scratch — it will teach you enough Python to read, modify, and extend this repository by walking through the actual code we use.

Every example in this guide is real code from `prismatica-qa/`.

---

## 1. Project Infrastructure — The Files That Are Not Code

Before looking at any Python, let's understand the files that make the project work but don't contain application logic.

### `.venv/` — The Virtual Environment

```
.venv/
├── bin/
│   ├── python          ← a copy of python3, isolated
│   ├── pip             ← installs packages INTO this venv only
│   ├── pqa             ← our CLI command (installed via pyproject.toml)
│   └── uvicorn         ← the API server
├── lib/
│   └── python3.13/
│       └── site-packages/   ← all installed libraries live here
└── pyvenv.cfg
```

**What it is:** An isolated copy of Python with its own packages. When you run `.venv/bin/python`, it uses the libraries inside `.venv/lib/` instead of the system-wide ones. This means each project can have different versions of the same library without conflicts.

**The C analogy:** Imagine if each project had its own `/usr/lib/` that only it could see. That is what a venv does.

**The Node.js analogy:** It is exactly `node_modules/`, but for Python. In fact, `.venv/` is in `.gitignore` for the same reason `node_modules/` was — it is generated, not committed.

**How it is created and used:**

```bash
python3 -m venv .venv              # create the venv (once)
source .venv/bin/activate           # activate it (makes 'python' point to .venv/bin/python)
pip install -r requirements.txt     # install libraries into the venv
deactivate                          # go back to system Python
```

Our `Makefile` handles all of this automatically — you never need to activate the venv manually. Every Make target uses `.venv/bin/python` directly.

### `requirements.txt` — The Dependency List

```
fastapi>=0.109.0
pymongo>=4.6.0
pydantic>=2.5.0
httpx>=0.26.0
typer[all]>=0.9.0
rich>=13.0.0
```

**What it is:** A flat list of packages to install. Each line is a package name and a version constraint. `>=0.109.0` means "this version or newer".

**The Node.js analogy:** This is `package.json` dependencies, but without the metadata. Just the packages.

**Why not `package.json`?** Python's ecosystem uses `pip` instead of `npm`. The file format is simpler — no JSON structure, just one package per line.

### `pyproject.toml` — The Project Metadata

```toml
[project]
name = "prismatica-qa"
version = "3.0.0"

[project.scripts]
pqa = "cli.main:app"
```

**What it is:** The modern way to configure a Python project. It defines the project name, version, and — critically — **entry points**.

**The key line:** `pqa = "cli.main:app"` means: when someone types `pqa` in the terminal, Python should import the `app` object from `cli/main.py` and run it. This is how the `pqa` CLI command is created without a shell script.

**The Node.js analogy:** This is like the `"bin"` field in `package.json` combined with the `"name"` and `"version"` fields.

**How it gets installed:**

```bash
pip install -e .    # the dot means "install the current directory as a package"
                    # -e means "editable" — changes to the code take effect immediately
```

After this command, `pqa` is available as a command inside the venv.

### `__init__.py` — Package Markers

```
core/
├── __init__.py        ← makes 'core' a Python package
├── db.py
├── schema.py
└── git_export.py
```

**What it is:** An empty file (or nearly empty) that tells Python "this directory is a package that can be imported". Without it, `from core.db import get_db` would fail because Python would not recognise `core/` as a package.

**The C analogy:** Think of it as a directory-level header file that says "the files in here are part of the same library".

**Our `__init__.py` files:**

```python
# core/__init__.py
# Prismatica QA — Core layer
# Database connection, schema validation, and git export utilities.
```

Most of ours are just a comment. They can contain imports to create a public API:

```python
# If we added this to core/__init__.py:
from core.db import get_db
from core.schema import parse_test

# Then other code could do:
from core import get_db, parse_test    # shorter import
```

We don't do this yet to keep things explicit — you always see exactly which file a function comes from.

### `*.egg-info/` — Build Metadata

After running `pip install -e .`, Python creates a `prismatica_qa.egg_info/` directory. This is metadata about the installed package — it tells pip "this project is installed, here are its entry points". It is generated, not committed. The `.gitignore` excludes it.

### `.env` and `.env.example`

```bash
# .env.example (committed — template)
MONGO_URI_ATLAS=mongodb+srv://user:password@cluster/test_hub

# .env (NOT committed — has real secrets)
MONGO_URI_ATLAS=mongodb+srv://univers42:realpassword@cluster0.rqo6vif.mongodb.net/test_hub
```

Python reads `.env` using the `python-dotenv` library:

```python
from dotenv import load_dotenv
import os

load_dotenv()                           # reads .env into environment variables
uri = os.getenv("MONGO_URI_ATLAS")      # retrieves the value
```

This is identical in concept to how Node.js uses `dotenv` — same pattern, same purpose, different language.

---

## 2. Python Fundamentals — Through Our Code

### Variables and types — no declarations needed

In C you write `int x = 5;`. In Python:

```python
# From runner/executor.py
start = time.perf_counter()     # float — Python figures out the type
error = None                     # None is Python's null
passed = False                   # bool — True/False (capitalised)
status_code = None               # will become an int later
```

No `let`, `const`, `var`, or type keyword. The variable exists the moment you assign to it.

### Strings — f-strings are your best friend

```python
# From runner/executor.py
error = f"expected status {expected_status}, got {response.status_code}"
```

The `f` prefix means "formatted string". Anything inside `{}` is evaluated as Python code. This is like JavaScript's template literals (`` `expected ${status}` ``) but with an `f` prefix instead of backticks.

Other string patterns we use:

```python
# Regular string
uri = "mongodb+srv://..."

# Multi-line string (triple quotes) — used for docstrings
"""
This is a docstring.
It can span multiple lines.
"""

# Raw string (r prefix) — backslashes are literal, used for regex
pattern = r"^[A-Z]+-\d{3}$"
```

### Functions — `def` instead of `function`

```python
# From core/db.py
def get_db() -> Database:
    """Return the test_hub database handle."""
    return get_client()["test_hub"]
```

Breaking this down:
- `def` — keyword to define a function (like `function` in JS or the return type in C)
- `get_db()` — function name and parameters
- `-> Database` — return type hint (optional but we always use them)
- `"""..."""` — docstring: a special comment that becomes the function's documentation
- Indentation defines the body (no `{}` braces)

### Indentation IS the syntax

In C and JavaScript, `{}` braces define blocks. In Python, **indentation does**. This is not a style choice — it is the language grammar.

```python
# From runner/executor.py
if expected_status is not None and response.status_code != expected_status:
    error = f"expected status {expected_status}, got {response.status_code}"
elif expected.get("bodyContains"):
    missing = [s for s in expected["bodyContains"] if s not in body]
    if missing:
        error = f"body missing: {missing}"
```

- 4 spaces = one level of indentation (this is the standard, never use tabs)
- The colon `:` at the end of `if`, `for`, `def`, `class` opens a new block
- There is no `fi`, `end`, or `}` — the block ends when indentation returns

### Dictionaries — Python's JSON-native data structure

```python
# From runner/executor.py — returning a result
return {
    "test_id": test["id"],
    "passed": passed,
    "duration_ms": duration_ms,
    "http_status": status_code,
    "error": error,
}
```

A `dict` in Python is exactly like a JavaScript object or a JSON document. In fact, Python's `json.loads()` returns a `dict`. This is why Python feels natural for working with MongoDB — MongoDB documents ARE Python dicts.

Accessing values:

```python
# Square brackets — raises KeyError if key missing
value = test["id"]

# .get() — returns None (or a default) if key missing
value = test.get("method", "GET")    # returns "GET" if no "method" key
```

We use `.get()` everywhere in the runner because test documents may not have every field.

### Lists and list comprehensions

```python
# From runner/executor.py — check which expected strings are missing from the body
missing = [s for s in expected["bodyContains"] if s not in body]
```

This one-liner is a **list comprehension** — Python's most powerful shorthand. It reads as: "give me a list of every `s` in `bodyContains` where `s` is not in `body`". The equivalent in JavaScript would be:

```javascript
const missing = expected.bodyContains.filter(s => !body.includes(s));
```

The equivalent in C would be a loop with a counter and a growing array. The list comprehension does it in one line.

### None, True, False — capitalised

```python
_client: MongoClient | None = None     # Python's null
passed = False                          # not 'false'
if error is None:                       # 'is None' not '== None'
    passed = True
```

Always use `is None` and `is not None` for None checks. `==` works but `is` is more correct (it checks identity, not equality).

---

## 3. How Python Imports Work — Packages and Modules

### The basics

A **module** is a `.py` file. A **package** is a directory with an `__init__.py`. When you write:

```python
from core.db import get_db
```

Python does this:
1. Looks for a directory called `core/` with an `__init__.py`
2. Inside it, looks for a file called `db.py`
3. Inside that file, finds the name `get_db`
4. Makes it available in the current file

### How our project imports work

```
prismatica-qa/           ← project root (in sys.path because of pip install -e .)
├── core/
│   ├── __init__.py
│   ├── db.py            ← "from core.db import get_db"
│   └── schema.py        ← "from core.schema import parse_test"
├── runner/
│   ├── __init__.py
│   ├── executor.py      ← "from runner.executor import execute_http_test"
│   └── results.py       ← "from runner.results import persist_result"
└── api/
    ├── __init__.py
    ├── main.py
    └── routers/
        ├── __init__.py
        └── tests.py     ← "from api.routers import tests"
```

### Standard library vs third-party vs local imports

```python
# From runner/executor.py

# 1. Standard library (comes with Python, no install needed)
import time

# 2. Third-party (installed via pip, listed in requirements.txt)
import httpx

# 3. Local (our own code)
from core.schema import HttpTest
```

Convention: group imports in this order, separated by blank lines. This is not enforced by Python but is the universal standard (PEP 8).

### `from __future__ import annotations`

You will see this at the top of `core/schema.py`:

```python
from __future__ import annotations
```

This is a compatibility trick. It makes type hints like `str | None` work as strings instead of being evaluated immediately. It exists because older Python versions didn't support the `|` syntax for types. We include it for safety.

---

## 4. Type Hints — Python's Type System

Python is dynamically typed — variables don't have declared types. But since Python 3.5+, you can add **type hints** that document what types are expected. They don't enforce anything at runtime — they are for developers and tools.

### Basic type hints in our code

```python
# From core/db.py
_client: MongoClient | None = None        # variable that is MongoClient or None

def get_client() -> MongoClient:           # returns a MongoClient
    ...

def disconnect() -> None:                  # returns nothing
    ...
```

```python
# From runner/executor.py
async def execute_http_test(test: dict) -> dict:
    # takes a dict, returns a dict
```

### The `|` operator for unions

```python
description: str | None = None     # this field can be a string or None
```

This is Python 3.10+ syntax. It means "string or null". In older Python you'd write `Optional[str]`, which is the same thing. We use `|` because it's cleaner.

### Why we use type hints everywhere

1. **IDE autocomplete works** — VS Code knows `get_db()` returns a `Database`, so it can suggest methods on it
2. **Bugs show up before running** — if you pass a `str` where an `int` is expected, your IDE highlights it
3. **Documentation that can't get outdated** — the type hint IS the spec

The C analogy: type hints in Python are like function prototypes in `.h` files — they document the interface, but unlike C, they don't enforce it at compile time.

---

## 5. Pydantic — Validation That Replaces AJV

In v1 we used AJV (a JavaScript JSON Schema validator) to check test definitions. In v3 we use Pydantic, which does the same thing but in Python and with better error messages.

### A Pydantic model is a class that validates data

```python
# From core/schema.py
class TestBase(BaseModel):
    id:       str      = Field(..., pattern=r"^[A-Z]+-\d{3}$")
    title:    str      = Field(..., min_length=5)
    domain:   Domain
    priority: Priority
    status:   Status
```

Breaking this down:

- `class TestBase(BaseModel):` — a class that inherits from Pydantic's `BaseModel`. Any class that inherits from `BaseModel` gets automatic validation.
- `id: str = Field(...)` — a field that must be a string. The `...` means "required" (no default). `pattern=r"^[A-Z]+-\d{3}$"` means it must match that regex.
- `domain: Domain` — must be one of the values in the `Domain` enum. If you pass `"invalid"`, Pydantic rejects it.

### How validation works in practice

```python
from core.schema import HttpTest

# This succeeds — all fields valid
test = HttpTest(
    id="AUTH-001",
    title="Login with valid credentials returns token",
    domain="auth",
    priority="P0",
    status="active",
    type="http",
    url="http://localhost:9999/token",
    method="POST",
    expected={"statusCode": 200},
)

# This FAILS — id doesn't match the pattern
test = HttpTest(
    id="bad-id",            # ✗ must be PREFIX-NNN
    title="Hi",             # ✗ min 5 chars
    domain="invalid",       # ✗ not in Domain enum
    ...
)
# → raises ValidationError with a detailed error message per field
```

### Inheritance — how HttpTest extends TestBase

```python
class HttpTest(TestBase):
    type:     Literal["http"] | str = "http"
    url:      str
    method:   str = Field(..., pattern=r"^(GET|POST|PUT|PATCH|DELETE)$")
    expected: HttpExpected
```

`HttpTest` inherits ALL fields from `TestBase` (id, title, domain, priority, status) and adds its own (url, method, expected). This is like C++ class inheritance — the child has everything the parent has, plus more.

### Enums — restricting values to a fixed set

```python
class Domain(str, Enum):
    auth     = "auth"
    gateway  = "gateway"
    infra    = "infra"
    ...
```

`(str, Enum)` means this enum's values are strings. If a field has type `Domain`, only the defined values are accepted. Pydantic uses this to validate that `domain` is one of the 8 allowed values.

### `model_dump()` — turning a Pydantic model back into a dict

```python
doc = test.model_dump()     # returns a plain Python dict
# → {"id": "AUTH-001", "title": "Login...", "domain": "auth", ...}
```

We use this before writing to MongoDB because pymongo expects dicts, not Pydantic objects.

---

## 6. Async / Await — Why the Runner Uses It

### The problem async solves

When the runner calls `http://localhost:9999/health`, it waits for the response. In synchronous code, the program blocks — it does nothing while waiting. If you have 100 tests, each taking 200ms of network wait, that is 20 seconds of doing nothing.

Async lets Python say "start this HTTP call, and while I wait, I'll do something else".

### How it looks in our code

```python
# From runner/executor.py
async def execute_http_test(test: dict) -> dict:
    async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
        response = await client.request(
            method=method,
            url=url,
        )
```

- `async def` — this function is a coroutine: it can be paused and resumed
- `await` — pause here until this operation completes, let other tasks run in the meantime
- `async with` — like `with` (context manager) but for async resources

### You need `asyncio.run()` to start async code

```python
# From cli/commands/run_cmd.py
import asyncio

results = asyncio.run(_run(domain, priority, test_id))
```

`asyncio.run()` is the bridge between synchronous and asynchronous code. It starts the event loop, runs the coroutine, and returns the result. Think of it as `main()` for async code.

### FastAPI is async by default

```python
# From api/routers/tests.py
@router.get("")
async def list_tests(domain: str | None = None):
    ...
```

FastAPI understands `async def` natively. When a request arrives, FastAPI calls the function as a coroutine. This is why our API is fast even under load — it doesn't block while waiting for MongoDB responses.

---

## 7. FastAPI — How the API Layer Works

### The app object

```python
# From api/main.py
from fastapi import FastAPI

app = FastAPI(title="Prismatica QA API", version="3.0.0")
```

This single object IS the API. Uvicorn (the server) imports it and serves it:

```bash
uvicorn api.main:app --reload --port 8000
#        ^^^^^^^^ ^^^
#        module   variable name
```

### Routers — organising endpoints into files

```python
# From api/main.py
from api.routers import tests, run, results

app.include_router(tests.router, prefix="/tests", tags=["Tests"])
```

Instead of putting all endpoints in one file, we split them into routers. Each router handles one area:

```python
# From api/routers/tests.py
from fastapi import APIRouter

router = APIRouter()

@router.get("")           # → GET /tests (prefix added by include_router)
async def list_tests():
    ...

@router.post("")          # → POST /tests
async def create_test():
    ...
```

### Decorators — the `@` syntax

```python
@router.get("")
async def list_tests(domain: str | None = Query(None)):
    ...
```

The `@router.get("")` is a **decorator**. It wraps the function and registers it as an HTTP endpoint. When a GET request arrives at `/tests`, FastAPI calls `list_tests()`.

Decorators are Python's way of modifying functions without changing their code. The C analogy would be a macro that wraps a function, but decorators are much more powerful.

### Query parameters — automatic from function arguments

```python
@router.get("")
async def list_tests(
    domain: str | None = Query(None),
    priority: str | None = Query(None),
    status: str | None = Query(None),
    db: Database = Depends(get_database),
):
```

FastAPI reads the function signature and:
- `domain: str | None = Query(None)` → becomes `?domain=auth` in the URL
- `db: Database = Depends(get_database)` → calls `get_database()` and injects the result

This is **dependency injection** — the function declares what it needs, and FastAPI provides it. You never call `get_database()` manually in a route.

### Swagger UI — free documentation

Because FastAPI knows all your endpoint signatures, it generates interactive documentation automatically at `/docs`. You can test every endpoint from the browser without curl.

---

## 8. pymongo — Talking to MongoDB from Python

### Connection

```python
# From core/db.py
from pymongo import MongoClient

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")          # verify connection
db = client["test_hub"]               # select database
```

This is identical in concept to the MongoDB Node.js driver we used in v1. The syntax is slightly different:

| Operation | Node.js (v1) | Python (v3) |
|-----------|-------------|-------------|
| Connect | `new MongoClient(uri)` | `MongoClient(uri)` |
| Get DB | `client.db("test_hub")` | `client["test_hub"]` |
| Find | `collection.find({status: "active"})` | `collection.find({"status": "active"})` |
| Insert | `collection.insertOne(doc)` | `collection.insert_one(doc)` |
| Upsert | `collection.updateOne({id}, {$set: doc}, {upsert: true})` | `collection.update_one({"id": id}, {"$set": doc}, upsert=True)` |

The biggest difference is naming: JavaScript uses `camelCase`, Python uses `snake_case`.

### Querying

```python
# From cli/commands/list_cmd.py
tests = list(db["tests"].find(query, {"_id": 0}).sort("id", 1))
```

- `db["tests"]` — access the `tests` collection
- `.find(query, {"_id": 0})` — find matching documents, exclude `_id` field
- `.sort("id", 1)` — sort by `id` ascending
- `list(...)` — convert the cursor to a Python list (MongoDB returns a lazy cursor by default)

### Creating indexes

```python
# From core/db.py
db["tests"].create_index("id", unique=True)
db["results"].create_index("executed_at", expireAfterSeconds=90 * 24 * 3600)
```

The TTL index (`expireAfterSeconds`) tells MongoDB to automatically delete documents older than 90 days. This keeps Atlas M0 under the 512MB limit without manual cleanup.

---

## 9. The Global Pattern — How db.py Manages State

```python
# From core/db.py
_client: MongoClient | None = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI_ATLAS")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
    return _client
```

This is the **singleton pattern** in Python. The first call creates the connection, subsequent calls reuse it. The `global` keyword tells Python "I want to modify the module-level variable `_client`, not create a local one".

Why? Because opening a MongoDB connection takes ~500ms. We want to do it once, not on every request. This is the same pattern we used in `scripts/db.ts` — the TypeScript version had the same singleton.

The underscore prefix `_client` is a Python convention meaning "this is private, don't access it from outside this module". It is not enforced — Python trusts the developer — but it signals intent.

---

## 10. Error Handling — try/except Instead of try/catch

```python
# From runner/executor.py
try:
    async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
        response = await client.request(method=method, url=url)

except httpx.TimeoutException:
    error = f"timeout after {timeout_ms}ms"
except httpx.ConnectError:
    error = f"connection refused: {url}"
except Exception as e:
    error = str(e)
```

The structure is identical to JavaScript's `try/catch`, with Python keywords:
- `try:` → `try {`
- `except X:` → `catch (X) {`
- `except X as e:` → `catch (e) {` with type checking
- `finally:` → `finally {` (we use this in `cli/commands/run_cmd.py` to disconnect)

You can catch specific exception types first and fall through to a generic `Exception` catch-all.

### Raising exceptions

```python
# From core/db.py
raise RuntimeError("MONGO_URI_ATLAS is not set.")
```

`raise` is Python's `throw`. `RuntimeError` is a built-in exception class.

```python
# From api/routers/tests.py
from fastapi import HTTPException

raise HTTPException(404, f"Test {test_id} not found")
```

FastAPI's `HTTPException` automatically becomes an HTTP error response.

---

## 11. How Everything Connects — A Full Request Traced

Let's trace what happens when you run `make test` and INFRA-003 (GoTrue health check) executes.

```
1. make test
   → Makefile runs: .venv/bin/pqa test run

2. pqa test run
   → cli/main.py dispatches to cli/commands/run_cmd.py
   → run_tests() is called

3. run_tests() → asyncio.run(_run(domain, priority, test_id))
   → _run() calls core.db.get_db()
   → get_db() calls get_client()
   → get_client() reads MONGO_URI_ATLAS from .env
   → Creates MongoClient, pings Atlas, caches the connection

4. _run() queries Atlas:
   db["tests"].find({"status": "active"}, {"_id": 0})
   → Gets 8 test documents as Python dicts

5. For INFRA-003 (type: "http"):
   → Calls runner.executor.execute_http_test(test_dict)
   → httpx.AsyncClient makes GET http://localhost:9999/health
   → If response.status_code == 200 → passed = True
   → Returns {"test_id": "INFRA-003", "passed": True, "duration_ms": 12}

6. runner.results.persist_result(result)
   → Writes to Atlas: db["results"].insert_one(doc)

7. Back in run_cmd.py:
   → Rich table prints one row per result
   → If any failed → sys.exit(1) → Make exits with error
```

This is the same flow regardless of whether you use `make test`, `pqa test run`, or call `POST /tests/run` via the API. The runner and result persistence are shared.

---

## 12. Common Gotchas Coming from C/C++ or JavaScript

### No semicolons
Python does not use `;` at the end of lines. Just don't.

### Indentation errors are syntax errors
If you mix tabs and spaces, or have inconsistent indentation, Python crashes. Configure your editor to insert 4 spaces when you press Tab.

### `==` works for strings
In C, `strcmp(a, b) == 0`. In Python, `a == b` just works for strings. And `is` checks identity (same object), not equality.

### `None` is not `0` or `""`
In JavaScript, `null`, `undefined`, `0`, `""`, and `false` are all falsy. In Python, `None`, `0`, `""`, `[]`, `{}`, and `False` are falsy, but they are NOT the same thing. Use `if x is None:` to check for None specifically.

### Lists are not arrays
Python lists are dynamic — they grow and shrink. There is no need for `malloc` or `realloc`. `list.append(x)` adds to the end, `list.pop()` removes from the end. They are like JavaScript arrays.

### Dictionaries preserve insertion order
Since Python 3.7, dicts maintain the order you insert keys. This is why our JSON export produces consistent output.

### f-strings need the `f` prefix
```python
name = "AUTH-001"
print(f"Test: {name}")     # ✓ prints "Test: AUTH-001"
print("Test: {name}")      # ✗ prints literally "Test: {name}"
```

### `import` is not `#include`
In C, `#include` copies the file content. In Python, `import` executes the file once and caches the result. Importing the same module twice does NOT run it twice — Python returns the cached version.

### There is no `main()` by default
Python files are scripts — they execute top to bottom. The pattern `if __name__ == "__main__":` means "run this block only if this file was executed directly, not imported":

```python
# From scripts/verify_setup.py
if __name__ == "__main__":
    main()
```

If another file imports `verify_setup`, the `main()` call does not run. If you run `python verify_setup.py` directly, it does.

---

*This guide covers the Python you need to work with this repository. For deeper Python knowledge, the official tutorial at [docs.python.org/3/tutorial](https://docs.python.org/3/tutorial/) is excellent and free.*

*For FastAPI specifics: [fastapi.tiangolo.com/tutorial](https://fastapi.tiangolo.com/tutorial/)*

*For Pydantic specifics: [docs.pydantic.dev/latest/concepts/models](https://docs.pydantic.dev/latest/concepts/models/)*
