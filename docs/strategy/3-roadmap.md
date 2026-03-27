# Prismatica QA — Roadmap 3

*De Node.js a Python + FastAPI + React: tres capas, una sola fuente de verdad.*

*Marzo 2026 · Version 1.0 · vjan-nie*

---

## Table of Contents

- [1. De dónde partimos](#1-de-dónde-partimos)
- [2. Por qué este roadmap existe](#2-por-qué-este-roadmap-existe)
- [3. La arquitectura objetivo — tres capas](#3-la-arquitectura-objetivo--tres-capas)
- [4. Decisión crítica — Atlas como única fuente operacional](#4-decisión-crítica--atlas-como-única-fuente-operacional)
- [5. Nuevo stack técnico](#5-nuevo-stack-técnico)
- [6. Nueva estructura del repositorio](#6-nueva-estructura-del-repositorio)
- [7. Esquema flexible de tests — Pydantic v2](#7-esquema-flexible-de-tests--pydantic-v2)
- [8. Capa 1 — Core Python](#8-capa-1--core-python)
- [9. Capa 2 — API FastAPI](#9-capa-2--api-fastapi)
- [10. Capa 3 — Dashboard React + libcss](#10-capa-3--dashboard-react--libcss)
- [11. El CLI — `pqa`](#11-el-cli--pqa)
- [12. Plan de implementación por fases](#12-plan-de-implementación-por-fases)
- [13. Tradeoffs asumidos y decisiones pendientes](#13-tradeoffs-asumidos-y-decisiones-pendientes)
- [14. Progress Against Objectives](#14-progress-against-objectives)
- [15. Next Steps](#15-next-steps)

---

## 1. De dónde partimos

Este roadmap parte del estado real del repositorio al cierre del Roadmap 1. El Roadmap 2 (migración a Python + CLI `pqa`) fue diseñado pero **nunca se implementó**. Todo lo que se conserva de ese roadmap se integra aquí desde cero.

### Estado actual del repositorio (Roadmap 1 completado)

**Lo que existe y funciona:**

- MongoDB local vía Docker (`docker-compose.yml`, `mongo:7`, puerto 27017)
- 10 test definitions en JSON (`test-definitions/` — 5 infra, 3 auth, 2 gateway)
- 4 tests activos pasando: INFRA-003, INFRA-004, INFRA-005, AUTH-003
- Runner v1 en TypeScript (`runner/src/cli.ts`) — ejecuta HTTP GET/POST, compara `statusCode` y `bodyContains`
- Scripts en TypeScript: `scripts/db.ts`, `scripts/seed.ts`, `scripts/validate.ts`
- Validación AJV contra JSON Schema
- Makefile funcional con preflight checks, `make seed`, `make validate`, `make test`
- Documentación: README.md, `docs/how-to-add-a-test.md`, `docs/test-template.json`

**Lo que no existe:**

- No hay runner Python
- No hay CLI `pqa`
- No hay API HTTP
- No hay dashboard
- No hay conexión a Atlas
- No hay persistencia de resultados (solo terminal output)
- No hay soporte para tests bash o manuales
- Kong y Realtime no corren en mini-baas-infra

### Archivos que se eliminarán en la migración

```
package.json              ← Node.js
package-lock.json         ← Node.js
tsconfig.json             ← TypeScript
node_modules/             ← Node.js
runner/src/cli.ts         ← Runner TypeScript
scripts/db.ts             ← MongoDB connection TypeScript
scripts/seed.ts           ← Seed TypeScript
scripts/validate.ts       ← Validate TypeScript
```

### Archivos que se conservan tal cual

```
test-definitions/**/*.json    ← Fuente de verdad histórica — intocables
docker-compose.yml            ← Sigue útil para levantar servicios bajo test
.env.example                  ← Se actualiza pero no se borra
Makefile                      ← Se reescribe para Python
docs/test-template.json       ← Referencia
docs/how-to-add-a-test.md     ← Se actualiza para el nuevo flujo
```

---

## 2. Por qué este roadmap existe

El Roadmap 2 identificó tres problemas reales del Roadmap 1:

1. **Node es el lenguaje incorrecto para QA** — Python es más directo para scripting HTTP y más transversal en el equipo.
2. **Los JSON a mano matan la adopción** — demasiada fricción para añadir un test.
3. **MongoDB local no da visibilidad de equipo** — resultados invisibles entre developers.

Este roadmap conserva las soluciones del Roadmap 2 (Python, Pydantic, CLI interactivo, Atlas compartido) pero añade una cuarta dimensión:

4. **Un dashboard web permite a todo el equipo — incluidos los developers de backend y BD — aprender frontend tocando tecnologías reales** (React, componentes, estado, API REST) dentro de un proyecto con contexto propio.

Además, este roadmap simplifica una decisión del Roadmap 2 que añadía complejidad innecesaria: **la sincronización bidireccional Atlas ↔ Docker local desaparece.** La justificación se explica en la sección 4.

---

## 3. La arquitectura objetivo — tres capas

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   CAPA 3 — FRONTEND                                        │
│                                                             │
│   React + libcss (dashboard)                                │
│   Tabla de tests · filtros · botón Run · resultados         │
│                                                             │
│   CLI pqa (terminal)                                        │
│   pqa test add · run · list · edit · export                 │
│                                                             │
│   Ambos son clientes de la misma API.                       │
│   Ninguno habla directamente con MongoDB.                   │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (fetch / httpx)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   CAPA 2 — API                                              │
│                                                             │
│   FastAPI                                                   │
│   GET  /tests · POST /tests · PATCH /tests/{id}            │
│   POST /tests/run · GET /results                            │
│   WebSocket /ws/run (ejecución en vivo)                     │
│                                                             │
│   Toda la lógica de negocio vive aquí.                      │
│   Valida con Pydantic. Ejecuta con el runner.               │
│   Persiste en Atlas.                                        │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ pymongo
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   CAPA 1 — CORE                                             │
│                                                             │
│   core/db.py         → conexión Atlas (pymongo)             │
│   core/schema.py     → modelos Pydantic v2                  │
│   core/git_export.py → escribe JSON a test-definitions/     │
│   runner/executor.py → ejecuta tests HTTP                   │
│   runner/bash_executor.py → ejecuta tests bash              │
│   runner/results.py  → persiste resultados                  │
│                                                             │
│   No tiene interfaz propia. Es importado por la API         │
│   y por el CLI.                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**El principio fundamental:** la lógica de negocio (validar, ejecutar, persistir) vive en el Core. La API la expone por HTTP. El CLI y el Dashboard la consumen. Si mañana se quiere un bot de Slack o un webhook de CI, es otro cliente más de la misma API.

---

## 4. Decisión crítica — Atlas como única fuente operacional

### Qué proponía el Roadmap 2

El Roadmap 2 mantenía dos backends MongoDB:
- Atlas (compartido, online)
- Docker local (fallback offline)

Con un mecanismo de sync bidireccional (`pqa test sync --to-local`, `--to-atlas`) y resolución de conflictos last-write-wins.

### Por qué lo eliminamos

**El sync bidireccional es la pieza más costosa de implementar y la que menos valor aporta.** Estamos construyendo, en esencia, un sistema de replicación con resolución de conflictos encima de una base de datos que ya tiene replicación nativa. Es ingeniería costosa para un escenario — trabajar offline con estado compartido — que ocurre muy raramente en un equipo académico con conexión a internet en 42.

Con el dashboard web encima, el problema se agrava: si unos developers están contra Atlas y otros contra Docker local, el dashboard muestra datos parciales e inconsistentes. La doble fuente contamina toda la capa de API.

### La decisión

```
Git (JSON en disco)           → historial y trazabilidad (no cambia)
Atlas M0 (tests + results)    → estado operacional, compartido, único
```

Dos fuentes con roles distintos y sin solapamiento:
- **Git** guarda "qué definimos" — trazabilidad, diffs, branches, code review
- **Atlas** guarda "qué existe operacionalmente y qué pasó cuando lo ejecutamos"

### ¿Y Docker MongoDB?

**No desaparece del proyecto.** `docker-compose.yml` sigue útil para levantar los servicios bajo test (GoTrue, PostgREST, MinIO) vía mini-baas-infra. Lo que desaparece es Docker MongoDB como backend alternativo del QA hub.

### ¿Y si no hay internet?

Sin Atlas, el CLI y el dashboard no funcionan — igual que no se puede pushear a GitHub sin red. Es una limitación aceptable a cambio de eliminar toda la complejidad del sync. Si un developer necesita trabajar offline, puede consultar los JSON en disco (que están en git) y ejecutar tests manualmente.

### ¿Y el límite de 512 MB del Atlas M0?

Con 200 tests y 10 ejecuciones diarias, se consumen ~2 MB/día en la colección de resultados. Un TTL index de 90 días en `results` mantiene el consumo bajo control indefinidamente:

```python
# En core/db.py — se ejecuta una vez
results.create_index("executed_at", expireAfterSeconds=90 * 24 * 3600)
```

---

## 5. Nuevo stack técnico

### Lo que se elimina (Node.js / TypeScript)

| Eliminado | Razón |
|-----------|-------|
| `package.json`, `tsconfig.json`, `node_modules/` | Ya no hay código TypeScript |
| `runner/src/cli.ts` | Reemplazado por runner Python |
| `scripts/db.ts`, `scripts/seed.ts`, `scripts/validate.ts` | Reemplazados por Core Python + API |
| AJV (JSON Schema validator) | Reemplazado por Pydantic v2 |
| `ts-node` | Reemplazado por Python directo |

### Lo que se añade (Python + React)

#### Backend (Python 3.11+)

| Librería | Rol |
|----------|-----|
| `fastapi` | Framework API — endpoints REST + WebSocket |
| `uvicorn` | Servidor ASGI para FastAPI |
| `typer` | Framework CLI — subcomandos, autocompletado, ayuda automática |
| `rich` | Output terminal — tablas, colores, progress bars |
| `pymongo` | Driver MongoDB — conexión a Atlas |
| `httpx` | Cliente HTTP async — llamadas a servicios bajo test |
| `pydantic v2` | Validación de schema — reemplaza AJV, integrado en FastAPI |
| `python-dotenv` | Variables de entorno desde `.env` |
| `websockets` | Soporte WebSocket en FastAPI para ejecución en vivo |

#### Frontend (React + libcss)

| Librería | Rol |
|----------|-----|
| `react 18` | Framework UI |
| `typescript 5+` | Tipado estático |
| `react-router v6` | Routing SPA |
| `libcss` | Sistema de componentes — Button, FormField, ThemeToggle, Layout |
| `zustand` | Estado global — ya incluido en libcss |
| `lucide-react` | Iconos — ya incluido en libcss |
| `sonner` | Toasts de notificación — ya incluido en libcss |

#### Instalación

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                    # instala pqa como comando

# Frontend
cd dashboard/
npm install
npm run dev                         # Vite dev server en :5173
```

---

## 6. Nueva estructura del repositorio

```
prismatica-qa/
│
├── core/                              # CAPA 1 — Lógica de negocio
│   ├── __init__.py
│   ├── db.py                          # Conexión Atlas (pymongo)
│   ├── schema.py                      # Modelos Pydantic v2: TestBase, HttpTest, BashTest, ManualTest
│   └── git_export.py                  # Escribe JSON a test-definitions/
│
├── runner/                            # CAPA 1 — Ejecución de tests
│   ├── __init__.py
│   ├── executor.py                    # Ejecuta tests tipo HTTP (httpx)
│   ├── bash_executor.py               # Ejecuta tests tipo bash (subprocess)
│   └── results.py                     # Persiste resultados en Atlas
│
├── api/                               # CAPA 2 — API FastAPI
│   ├── __init__.py
│   ├── main.py                        # Entrypoint FastAPI: app = FastAPI()
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── tests.py                   # GET/POST/PATCH/DELETE /tests
│   │   ├── run.py                     # POST /tests/run + WebSocket /ws/run
│   │   └── results.py                 # GET /results
│   └── deps.py                        # Dependencias compartidas (db connection)
│
├── cli/                               # CAPA 3a — CLI (cliente de la API)
│   ├── __init__.py
│   ├── main.py                        # Entrypoint: pqa
│   └── commands/
│       ├── __init__.py
│       ├── add.py                     # pqa test add
│       ├── edit.py                    # pqa test edit <ID>
│       ├── list.py                    # pqa test list
│       ├── run.py                     # pqa test run
│       ├── delete.py                  # pqa test delete <ID>
│       └── export.py                  # pqa test export (Atlas → JSON en disco)
│
├── dashboard/                         # CAPA 3b — Frontend React (cliente de la API)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── app/
│       │   ├── App.tsx                # Root con routing
│       │   └── styles/                # Variables globales + tema Prismatica
│       ├── features/
│       │   ├── test-list/             # Vista principal: tabla de tests con filtros
│       │   ├── test-detail/           # Vista detalle de un test
│       │   ├── test-form/             # Crear / editar un test
│       │   └── run-results/           # Vista de resultados de ejecución
│       ├── shared/
│       │   ├── ui/                    # Componentes libcss reutilizados + extensiones
│       │   ├── api/                   # Cliente HTTP para hablar con FastAPI
│       │   ├── model/                 # Zustand stores (tests, results, UI)
│       │   └── lib/                   # Utilidades (formateo, filtros, tipos)
│       └── types/
│           └── test.types.ts          # Interfaces TypeScript alineadas con Pydantic
│
├── test-definitions/                  # Fuente de verdad en git — sin cambios
│   ├── auth/
│   ├── gateway/
│   ├── infra/
│   ├── api/
│   ├── realtime/
│   ├── storage/
│   ├── ui/
│   └── schema/
│
├── scripts/
│   └── migrate_v1_to_v2.py           # Migración única: seed JSON existentes en Atlas
│
├── docs/
│   ├── test-template.json             # Referencia (ya no es el flujo principal)
│   ├── how-to-add-a-test.md           # Actualizado para pqa + dashboard
│   ├── ai-unblock-guide.md
│   └── demo-guide.md
│
├── requirements.txt                   # Dependencias Python
├── pyproject.toml                     # Entry point pqa + metadata
├── docker-compose.yml                 # Servicios bajo test (NO MongoDB QA)
├── Makefile                           # Adaptado a Python + React
└── .env.example                       # MONGO_URI_ATLAS + URLs de servicios
```

---

## 7. Esquema flexible de tests — Pydantic v2

### Por qué cambia el schema

En v1, todos los tests comparten los mismos 15+ campos obligatorios. Un test de smoke de infraestructura y un test de autenticación con payload tienen exactamente el mismo schema. Esto obliga a poner valores vacíos o nulos en campos que no aplican, y hace imposible representar tests de tipo bash o manual.

### Modelo base — 5 campos obligatorios para cualquier test

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Literal

class Domain(str, Enum):
    auth = "auth"
    gateway = "gateway"
    schema_ = "schema"
    api = "api"
    realtime = "realtime"
    storage = "storage"
    ui = "ui"
    infra = "infra"

class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class Status(str, Enum):
    draft = "draft"
    active = "active"
    skipped = "skipped"
    deprecated = "deprecated"

class TestBase(BaseModel):
    id:       str       = Field(..., pattern=r"^[A-Z]+-\d{3}$")
    title:    str       = Field(..., min_length=5)
    domain:   Domain
    priority: Priority
    status:   Status
```

Un test válido puede tener solo estos cinco campos. Esto permite documentar comportamiento esperado sin automatización.

### Extensión para tests HTTP

```python
class HttpExpected(BaseModel):
    statusCode:   int
    bodyContains: list[str] | None = None
    jwtClaims:    dict | None = None
    cookieSet:    str | None = None

class HttpTest(TestBase):
    type: Literal["http"]
    url: str
    method: str = Field(..., pattern=r"^(GET|POST|PUT|PATCH|DELETE)$")
    headers: dict[str, str] | None = None
    payload: dict | None = None
    expected: HttpExpected
    timeout_ms: int = 5000
    retries: int = 1
```

### Extensión para tests Bash/Script

```python
class BashTest(TestBase):
    type: Literal["bash"]
    script: str
    expected_exit_code: int = 0
    expected_output: str | None = None
    timeout_seconds: int = 30
```

### Extensión para tests manuales

```python
class ManualTest(TestBase):
    type: Literal["manual"] | None = None
    notes: str | None = None
```

### Campos opcionales comunes — cualquier tipo puede incluirlos

```python
# Estos se añaden a TestBase como opcionales
tags:          list[str] | None = None
phase:         str | None = None
layer:         str | None = None        # backend, frontend, infra, full-stack
service:       str | None = None
environment:   list[str] | None = None
preconditions: list[str] | None = None
dependencies:  list[str] | None = None
author:        str | None = None
notes:         str | None = None
```

### Compatibilidad con los 10 tests existentes

Los 10 JSON actuales son todos tipo HTTP. La migración los lee, los valida contra `HttpTest`, y los inserta en Atlas. Los campos que no encajan en el nuevo schema (como `component`) se almacenan en un campo `_legacy` para no perder información.

---

## 8. Capa 1 — Core Python

### `core/db.py` — Conexión Atlas

```python
import os
from pymongo import MongoClient
from pymongo.database import Database

_client: MongoClient | None = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI_ATLAS")
        if not uri:
            raise RuntimeError(
                "MONGO_URI_ATLAS not set. "
                "Copy .env.example to .env and configure your Atlas connection string."
            )
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")  # fail fast si Atlas no responde
    return _client

def get_db() -> Database:
    return get_client()["test_hub"]

def disconnect():
    global _client
    if _client:
        _client.close()
        _client = None
```

Sin fallback. Sin detección automática. Si Atlas no está configurado o no responde, el error es claro y directo.

### `core/git_export.py` — Exportar a JSON en disco

```python
import json
from pathlib import Path

DEFINITIONS_DIR = Path("test-definitions")

def export_test(test: dict) -> Path:
    """Escribe un test como JSON en test-definitions/{domain}/{id}.json"""
    domain = test["domain"]
    test_id = test["id"]

    folder = DEFINITIONS_DIR / domain
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{test_id}.json"

    # Eliminar campos internos de MongoDB
    clean = {k: v for k, v in test.items() if not k.startswith("_")}

    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n")
    return path
```

### `runner/executor.py` — Ejecutor HTTP

```python
import httpx
import time
from core.schema import HttpTest

async def execute_http_test(test: HttpTest) -> dict:
    start = time.perf_counter()
    error = None
    passed = False
    status_code = None

    try:
        async with httpx.AsyncClient(timeout=test.timeout_ms / 1000) as client:
            response = await client.request(
                method=test.method,
                url=test.url,
                headers=test.headers,
                json=test.payload if test.method in ("POST", "PUT", "PATCH") else None,
            )
            status_code = response.status_code
            body = response.text

            # Comprobar statusCode
            if response.status_code != test.expected.statusCode:
                error = f"expected {test.expected.statusCode}, got {response.status_code}"
            # Comprobar bodyContains
            elif test.expected.bodyContains:
                missing = [s for s in test.expected.bodyContains if s not in body]
                if missing:
                    error = f"body missing: {missing}"
            else:
                passed = True

            if not error:
                passed = True

    except httpx.TimeoutException:
        error = f"timeout after {test.timeout_ms}ms"
    except httpx.ConnectError:
        error = f"connection refused: {test.url}"
    except Exception as e:
        error = str(e)

    duration_ms = round((time.perf_counter() - start) * 1000)

    return {
        "test_id": test.id,
        "passed": passed,
        "duration_ms": duration_ms,
        "http_status": status_code,
        "error": error,
    }
```

### `runner/bash_executor.py` — Ejecutor Bash

```python
import subprocess
import time
from core.schema import BashTest

async def execute_bash_test(test: BashTest) -> dict:
    start = time.perf_counter()
    error = None
    passed = False

    try:
        result = subprocess.run(
            test.script,
            shell=True,
            capture_output=True,
            text=True,
            timeout=test.timeout_seconds,
        )

        if result.returncode != test.expected_exit_code:
            error = f"exit code: expected {test.expected_exit_code}, got {result.returncode}"
        elif test.expected_output and test.expected_output not in result.stdout:
            error = f"output missing: {test.expected_output}"
        else:
            passed = True

    except subprocess.TimeoutExpired:
        error = f"timeout after {test.timeout_seconds}s"
    except Exception as e:
        error = str(e)

    duration_ms = round((time.perf_counter() - start) * 1000)

    return {
        "test_id": test.id,
        "passed": passed,
        "duration_ms": duration_ms,
        "error": error,
    }
```

### `runner/results.py` — Persistencia de resultados

```python
from datetime import datetime, timezone
from core.db import get_db

def persist_result(result: dict, environment: str = "local", run_by: str = "developer"):
    db = get_db()
    doc = {
        **result,
        "environment": environment,
        "run_by": run_by,
        "executed_at": datetime.now(timezone.utc),
    }
    db["results"].insert_one(doc)
    return doc
```

---

## 9. Capa 2 — API FastAPI

### `api/main.py` — Entrypoint

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import tests, run, results

app = FastAPI(
    title="Prismatica QA API",
    version="1.0.0",
    description="API para el QA Hub de Prismatica / ft_transcendence",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tests.router, prefix="/tests", tags=["tests"])
app.include_router(run.router, prefix="/tests", tags=["run"])
app.include_router(results.router, prefix="/results", tags=["results"])
```

### Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/tests` | Listar tests con filtros (`?domain=auth&priority=P0&status=active`) |
| `GET` | `/tests/{id}` | Obtener un test por ID |
| `POST` | `/tests` | Crear un test nuevo (valida con Pydantic, escribe en Atlas + exporta JSON) |
| `PATCH` | `/tests/{id}` | Modificar un test existente |
| `DELETE` | `/tests/{id}` | Marcar como deprecated (soft delete) |
| `POST` | `/tests/run` | Ejecutar tests por filtros (body: `{domain?, priority?, id?}`) |
| `GET` | `/results` | Listar resultados con filtros (`?test_id=AUTH-003&limit=50`) |
| `GET` | `/results/summary` | Resumen por dominio: total, passed, failed, last run |
| `WS` | `/ws/run` | WebSocket — ejecución en vivo, envía resultado test por test |

### `api/routers/tests.py` — Ejemplo de endpoint

```python
from fastapi import APIRouter, Query, HTTPException
from core.db import get_db
from core.schema import HttpTest, BashTest, ManualTest
from core.git_export import export_test

router = APIRouter()

@router.get("")
async def list_tests(
    domain: str | None = Query(None),
    priority: str | None = Query(None),
    status: str | None = Query(None),
):
    db = get_db()
    query = {}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if status:
        query["status"] = status

    tests = list(db["tests"].find(query, {"_id": 0}))
    return {"tests": tests, "total": len(tests)}

@router.post("", status_code=201)
async def create_test(test: HttpTest | BashTest | ManualTest):
    db = get_db()

    # Verificar unicidad de ID
    if db["tests"].find_one({"id": test.id}):
        raise HTTPException(409, f"Test {test.id} already exists")

    doc = test.model_dump()
    db["tests"].insert_one(doc)

    # Exportar a JSON en disco
    path = export_test(doc)

    return {"id": test.id, "exported_to": str(path)}
```

### `api/routers/run.py` — Ejecución con WebSocket

```python
from fastapi import APIRouter, WebSocket
from core.db import get_db
from runner.executor import execute_http_test
from runner.bash_executor import execute_bash_test
from runner.results import persist_result
from core.schema import HttpTest, BashTest
import json

router = APIRouter()

@router.post("/run")
async def run_tests(
    domain: str | None = None,
    priority: str | None = None,
    test_id: str | None = None,
):
    """Ejecuta tests y devuelve resultados al terminar."""
    db = get_db()
    query = {"status": "active"}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if test_id:
        query["id"] = test_id

    tests = list(db["tests"].find(query, {"_id": 0}))
    all_results = []

    for t in tests:
        if t.get("type") == "bash":
            test_obj = BashTest(**t)
            result = await execute_bash_test(test_obj)
        elif t.get("type") == "manual":
            result = {"test_id": t["id"], "passed": None, "duration_ms": 0, "error": "manual — skip"}
        else:
            test_obj = HttpTest(**t)
            result = await execute_http_test(test_obj)

        persist_result(result)
        all_results.append(result)

    passed = sum(1 for r in all_results if r["passed"])
    failed = sum(1 for r in all_results if r["passed"] is False)

    return {
        "results": all_results,
        "summary": {"total": len(all_results), "passed": passed, "failed": failed},
    }


@router.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    """WebSocket: envía resultados test por test en tiempo real."""
    await ws.accept()
    data = await ws.receive_json()

    db = get_db()
    query = {"status": "active"}
    if data.get("domain"):
        query["domain"] = data["domain"]
    if data.get("priority"):
        query["priority"] = data["priority"]

    tests = list(db["tests"].find(query, {"_id": 0}))
    await ws.send_json({"type": "start", "total": len(tests)})

    passed = 0
    failed = 0

    for t in tests:
        if t.get("type") == "bash":
            result = await execute_bash_test(BashTest(**t))
        elif t.get("type") == "manual":
            result = {"test_id": t["id"], "passed": None, "duration_ms": 0, "error": "manual"}
        else:
            result = await execute_http_test(HttpTest(**t))

        persist_result(result)

        if result["passed"]:
            passed += 1
        elif result["passed"] is False:
            failed += 1

        await ws.send_json({"type": "result", **result})

    await ws.send_json({"type": "done", "passed": passed, "failed": failed})
    await ws.close()
```

---

## 10. Capa 3 — Dashboard React + libcss

### Principio de diseño

El dashboard usa los componentes de libcss (Button, FormField, ThemeToggle, SplitLayout, etc.) como base visual y añade componentes de dominio específicos del QA Hub. Sigue la arquitectura FSD de libcss:

```
dashboard/src/
├── app/                        # Inicialización + routing
├── features/                   # Features de negocio del dashboard
│   ├── test-list/             # Tabla de tests con filtros
│   ├── test-detail/           # Vista detalle
│   ├── test-form/             # Crear / editar
│   └── run-results/           # Vista de ejecución en vivo
└── shared/
    ├── ui/                    # Componentes reutilizados de libcss
    ├── api/                   # Cliente HTTP: fetchTests, runTests, etc.
    ├── model/                 # Zustand stores
    └── types/                 # TypeScript interfaces
```

### Vistas principales

**Vista 1 — Test List (página principal)**

Tabla con las columnas: ID, Domain, Priority, Status, Title, Last Run, Actions.

Filtros en barra superior: Domain (dropdown), Priority (dropdown), Status (dropdown), búsqueda por texto libre.

Acciones por fila: botón "Run" (ejecuta ese test individual), link a detalle.

Acciones globales: "Run filtered" (ejecuta todos los tests visibles), "Add test" (abre formulario).

**Vista 2 — Run Results (ejecución en vivo)**

Se conecta por WebSocket a `/ws/run`. Muestra una tabla que se llena test por test en tiempo real. Cada fila aparece con animación cuando el resultado llega. Al final muestra un resumen: passed/failed/total/duración.

**Vista 3 — Test Form (crear / editar)**

Formulario dinámico basado en el tipo de test seleccionado:
- Si es HTTP → muestra campos url, method, headers, payload, expected
- Si es bash → muestra campos script, expected_exit_code, expected_output
- Si es manual → muestra solo notes

Usa los componentes FormField y Button de libcss. Validación en cliente alineada con los modelos Pydantic del backend.

**Vista 4 — Test Detail**

Vista de solo lectura con toda la información de un test: metadatos, configuración, historial de ejecuciones recientes (últimas 20 de la colección `results`).

### Cliente API (`shared/api/client.ts`)

```typescript
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchTests(filters?: {
  domain?: string;
  priority?: string;
  status?: string;
}) {
  const params = new URLSearchParams();
  if (filters?.domain) params.set("domain", filters.domain);
  if (filters?.priority) params.set("priority", filters.priority);
  if (filters?.status) params.set("status", filters.status);

  const res = await fetch(`${API_BASE}/tests?${params}`);
  return res.json();
}

export async function runTests(filters: {
  domain?: string;
  priority?: string;
  id?: string;
}) {
  const res = await fetch(`${API_BASE}/tests/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters),
  });
  return res.json();
}

export function connectRunWebSocket(
  filters: { domain?: string; priority?: string },
  onResult: (result: any) => void,
  onDone: (summary: any) => void,
) {
  const ws = new WebSocket(`${API_BASE.replace("http", "ws")}/ws/run`);

  ws.onopen = () => ws.send(JSON.stringify(filters));

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "result") onResult(data);
    if (data.type === "done") onDone(data);
  };

  return ws;
}
```

### Integración con libcss

| Componente libcss | Uso en dashboard |
|-------------------|------------------|
| `Button` | Acciones: Run, Add, Edit, Filter, Export |
| `FormField` | Formulario de creación/edición de tests |
| `ThemeToggle` | Dark/light mode del dashboard |
| `SplitLayout` | Layout principal: sidebar de filtros + tabla |
| `LanguageSelector` | Si se implementa multi-idioma |
| `BrandLogo` | Branding Prismatica en header |
| `Icon` (Lucide) | Iconos de estado: check, x, clock, alert |
| `Sonner` (Toast) | Notificaciones: "Test created", "Run complete: 4 passed" |

---

## 11. El CLI — `pqa`

El CLI se conserva del Roadmap 2 con una diferencia fundamental: **ya no habla directamente con MongoDB.** El CLI es un cliente HTTP de la API FastAPI, igual que el dashboard.

### Estructura de subcomandos

```
pqa
└── test
    ├── add       — crear un test (interactivo o con flags)
    ├── edit      — modificar un test existente
    ├── delete    — marcar como deprecated
    ├── list      — listar tests con filtros
    ├── run       — ejecutar tests contra servicios
    └── export    — exportar tests de Atlas a JSON en disco
```

**Eliminado respecto al Roadmap 2:** `pqa test sync` — ya no existe la doble fuente.

### El CLI requiere que la API esté corriendo

```bash
# Terminal 1: levantar la API
make api       # → uvicorn api.main:app --reload --port 8000

# Terminal 2: usar el CLI
pqa test list
pqa test run --domain auth --priority P0
```

Esto es un tradeoff consciente. El CLI podría hablar directamente con MongoDB (como planteaba el Roadmap 2), pero eso duplicaría la lógica de validación y ejecución que ya vive en la API. Al hacer que el CLI sea cliente de la API, toda la lógica está en un solo sitio.

### Ejemplo: `pqa test run`

```
$ pqa test run --priority P0

  Running 4 tests (priority: P0, env: local)

  ┌─────────────┬────────┬──────┬──────────────────────────────┬───────────┐
  │ ID          │ Status │  ms  │ Title                        │ Error     │
  ├─────────────┼────────┼──────┼──────────────────────────────┼───────────┤
  │ INFRA-003   │  ✓     │  12  │ GoTrue health                │           │
  │ INFRA-004   │  ✓     │   8  │ PostgREST health             │           │
  │ INFRA-005   │  ✓     │  11  │ MinIO health                 │           │
  │ AUTH-003    │  ✓     │  15  │ No token returns 401         │           │
  └─────────────┴────────┴──────┴──────────────────────────────┴───────────┘

  4 passed · 0 failed · 46ms total · exit 0
```

### Excepción para CI

En CI (GitHub Actions), no se levanta la API. El step de CI ejecuta el runner directamente importando el core de Python:

```yaml
# En transcendence/.github/workflows/ci.yml
- name: Run QA smoke tests
  run: |
    git clone https://github.com/Univers42/QA.git
    cd QA
    pip install -r requirements.txt
    python -m runner.ci --priority P0
  env:
    MONGO_URI_ATLAS: ${{ secrets.MONGO_URI_ATLAS }}
```

`runner/ci.py` es un script mínimo que importa el core directamente — sin levantar FastAPI — para mantener el CI rápido y sin dependencias extra.

---

## 12. Plan de implementación por fases

Cada fase desbloquea la siguiente. Las estimaciones de tiempo son conservadoras para un equipo que está aprendiendo las tecnologías implicadas.

### Fase 0 — Limpieza y setup Python *(~2h · vjan-nie)*

**Objetivo:** el repositorio deja de ser Node.js y pasa a ser Python.

- [ ] Borrar: `package.json`, `package-lock.json`, `tsconfig.json`, `node_modules/`, `runner/src/cli.ts`, `scripts/db.ts`, `scripts/seed.ts`, `scripts/validate.ts`
- [ ] Crear `requirements.txt`:
  ```
  fastapi>=0.109.0
  uvicorn[standard]>=0.27.0
  typer[all]>=0.9.0
  rich>=13.0.0
  pymongo>=4.6.0
  httpx>=0.26.0
  pydantic>=2.5.0
  python-dotenv>=1.0.0
  websockets>=12.0
  ```
- [ ] Crear `pyproject.toml` con entry point `pqa`
- [ ] Adaptar `Makefile`:
  - `make install` → `pip install -e .`
  - `make api` → `uvicorn api.main:app --reload --port 8000`
  - `make test` → `pqa test run` (una vez exista el CLI)
  - `make dashboard` → `cd dashboard && npm run dev`
- [ ] Actualizar `.env.example` con `MONGO_URI_ATLAS`
- [ ] Verificar Python 3.11+ en todos los entornos del equipo
- [ ] Confirmar que `test-definitions/**/*.json` están intactos en git

### Fase 1 — Core: conexión y schema *(~3h · dlesieur)*

**Objetivo:** la base de datos y los modelos de datos funcionan.

- [ ] `core/__init__.py`
- [ ] `core/db.py` — conexión directa a Atlas, sin fallback
- [ ] `core/schema.py` — modelos Pydantic: `TestBase`, `HttpTest`, `BashTest`, `ManualTest`
- [ ] `core/git_export.py` — escribe JSON a `test-definitions/domain/ID.json`
- [ ] Tests unitarios mínimos del schema (pytest)
- [ ] Verificar conexión a Atlas desde terminal: `python -c "from core.db import get_db; print(get_db().list_collection_names())"`

### Fase 2 — Runner Python *(~4h · vjan-nie, en paralelo con Fase 1)*

**Objetivo:** los 4 tests activos pasan con el runner Python.

- [ ] `runner/__init__.py`
- [ ] `runner/executor.py` — ejecutor HTTP con httpx (reproduce comportamiento del runner TypeScript)
- [ ] `runner/bash_executor.py` — ejecutor bash con subprocess
- [ ] `runner/results.py` — persiste resultados en Atlas
- [ ] `runner/ci.py` — script mínimo para CI (importa core directamente)
- [ ] Verificar: INFRA-003, INFRA-004, INFRA-005, AUTH-003 pasan

### Fase 3 — Migración de datos *(~1h · ambos)*

**Objetivo:** los 10 tests existentes están en Atlas y los 4 activos pasan.

- [ ] `scripts/migrate_v1_to_v2.py` — lee los JSON de `test-definitions/`, los valida contra Pydantic, los inserta en Atlas con upsert
- [ ] Verificar que los 10 tests aparecen en Atlas
- [ ] Re-ejecutar los 4 tests activos con el runner Python
- [ ] Re-exportar JSON con `core/git_export.py` para confirmar round-trip limpio

### Fase 4 — API FastAPI *(~6h · dlesieur)*

**Objetivo:** la API expone el core como endpoints REST.

- [ ] `api/__init__.py`
- [ ] `api/main.py` — app FastAPI con CORS
- [ ] `api/deps.py` — dependencias compartidas
- [ ] `api/routers/tests.py` — CRUD de tests (GET, POST, PATCH, DELETE)
- [ ] `api/routers/run.py` — POST /tests/run + WebSocket /ws/run
- [ ] `api/routers/results.py` — GET /results + GET /results/summary
- [ ] Verificar con `curl` o Swagger UI (FastAPI auto-genera docs en `/docs`)
- [ ] Añadir `make api` al Makefile

### Fase 5 — CLI `pqa` *(~4h · vjan-nie)*

**Objetivo:** el CLI funciona como cliente de la API.

- [ ] `cli/__init__.py`
- [ ] `cli/main.py` — entrypoint con grupo de comandos `test`
- [ ] `cli/commands/list.py` — listado con filtros (tabla Rich)
- [ ] `cli/commands/run.py` — ejecución con tabla de resultados
- [ ] `cli/commands/add.py` — modo interactivo + `--quick`
- [ ] `cli/commands/edit.py` — edición con diff preview
- [ ] `cli/commands/delete.py` — soft delete (deprecated)
- [ ] `cli/commands/export.py` — genera JSON en `test-definitions/`
- [ ] Verificar: `pqa test run --priority P0` pasa los 4 tests

### Fase 6 — Dashboard React + libcss *(~8h · serjimen + dlesieur)*

**Objetivo:** el dashboard web funciona como cliente de la API.

- [ ] `dashboard/` — scaffold Vite + React + TypeScript
- [ ] Integrar libcss como dependencia local o copiada
- [ ] `shared/api/client.ts` — cliente HTTP para la API
- [ ] `shared/model/` — stores Zustand (tests, results, filters)
- [ ] `shared/types/test.types.ts` — interfaces alineadas con Pydantic
- [ ] `features/test-list/` — tabla de tests con filtros y acciones
- [ ] `features/run-results/` — ejecución en vivo vía WebSocket
- [ ] `features/test-form/` — formulario dinámico crear/editar
- [ ] `features/test-detail/` — vista detalle con historial de resultados
- [ ] Añadir `make dashboard` al Makefile

### Fase 7 — Documentación y CI *(~2h · dlesieur)*

**Objetivo:** todo está documentado y el CI funciona.

- [ ] Actualizar `README.md` — nuevo stack, nuevos comandos, nueva arquitectura
- [ ] Actualizar `docs/how-to-add-a-test.md` — flujo con dashboard y `pqa`
- [ ] Actualizar `docs/ai-unblock-guide.md` con contexto v3
- [ ] Step CI en `transcendence`: `pip install -r requirements.txt && python -m runner.ci --priority P0`
- [ ] Este documento: marcar como completado

---

## 13. Tradeoffs asumidos y decisiones pendientes

### Tradeoffs asumidos

| Tradeoff | Decisión | Razón |
|----------|----------|-------|
| Atlas único vs Atlas + Docker local | Atlas único | Elimina toda la complejidad de sync. Justificado en §4. |
| CLI como cliente de API vs acceso directo a MongoDB | Cliente de API | Una sola fuente de lógica de negocio. El CLI no duplica validación ni ejecución. |
| CI importa core directamente (sin API) | Excepción aceptada | El CI necesita ser rápido y sin dependencias extra. `runner/ci.py` importa el core sin levantar FastAPI. |
| JSON en disco + Atlas | Ambos con roles distintos | Git para historial y trazabilidad. Atlas para estado operacional. No se sincronizan — guardan cosas diferentes. |
| Dashboard en repo QA vs repo separado | Mismo repo | El dashboard es parte del sistema QA, no una aplicación independiente. Compartir tipos y documentación es más fácil en un solo repo. |
| WebSocket para ejecución en vivo vs polling | WebSocket | Más complejo de implementar pero mejor UX. El resultado aparece test por test en tiempo real. |
| Ejecución secuencial | Suficiente para <200 tests | Migrar a `asyncio.gather()` cuando el tiempo de suite supere 30s. |

### Decisiones pendientes — necesitan respuesta del equipo

**¿Cómo se integra libcss?**
Tres opciones: (a) copiar los componentes al dashboard, (b) publicar libcss como paquete npm privado, (c) usar un monorepo con workspaces. La opción (a) es la más rápida para empezar. La (b) es la más limpia a largo plazo. Consultar con serjimen.

**¿Autocompletado del CLI activado en `make install`?**
`typer` puede instalar autocompletado en bash/zsh. ¿Automático o manual?

**¿TTL de 90 días en results es suficiente?**
El TTL index purga resultados automáticamente. ¿El equipo necesita historial más largo? Si sí, considerar exportar resultados antiguos a JSON antes de purgarlos.

**¿Autenticación en la API?**
Por ahora, la API no tiene auth — cualquiera con acceso a la red puede crear/borrar tests. Aceptable en local y en la red de 42. Si la API se expone a internet (staging, demos), añadir API key o JWT mínimo.

---

## 14. Progress Against Objectives

### Fase 0 — Limpieza y setup Python

| Tarea | Owner | Estado |
|-------|-------|--------|
| Borrar artefactos Node | vjan-nie | ⏳ Pendiente |
| `requirements.txt` y `pyproject.toml` | vjan-nie | ⏳ Pendiente |
| `Makefile` adaptado a Python + React | vjan-nie | ⏳ Pendiente |
| Verificar Python 3.11+ | Ambos | ⏳ Pendiente |

### Fase 1 — Core: conexión y schema

| Tarea | Owner | Estado |
|-------|-------|--------|
| `core/db.py` — Atlas directo | dlesieur | ⏳ Pendiente |
| `core/schema.py` — Pydantic v2 | dlesieur | ⏳ Pendiente |
| `core/git_export.py` | dlesieur | ⏳ Pendiente |
| Tests unitarios del schema | dlesieur | ⏳ Pendiente |

### Fase 2 — Runner Python

| Tarea | Owner | Estado |
|-------|-------|--------|
| `runner/executor.py` (HTTP) | vjan-nie | ⏳ Pendiente |
| `runner/bash_executor.py` | vjan-nie | ⏳ Pendiente |
| `runner/results.py` (Atlas) | vjan-nie | ⏳ Pendiente |
| `runner/ci.py` (CI directo) | vjan-nie | ⏳ Pendiente |
| 4 tests activos pasando | vjan-nie | ⏳ Pendiente |

### Fase 3 — Migración de datos

| Tarea | Owner | Estado |
|-------|-------|--------|
| `scripts/migrate_v1_to_v2.py` | Ambos | ⏳ Pendiente |
| 10 tests en Atlas | Ambos | ⏳ Pendiente |
| 4 tests verificados post-migración | Ambos | ⏳ Pendiente |

### Fase 4 — API FastAPI

| Tarea | Owner | Estado |
|-------|-------|--------|
| `api/main.py` + CORS | dlesieur | ⏳ Pendiente |
| CRUD tests (`api/routers/tests.py`) | dlesieur | ⏳ Pendiente |
| Run + WebSocket (`api/routers/run.py`) | dlesieur | ⏳ Pendiente |
| Results (`api/routers/results.py`) | dlesieur | ⏳ Pendiente |
| Swagger UI verificado | dlesieur | ⏳ Pendiente |

### Fase 5 — CLI `pqa`

| Tarea | Owner | Estado |
|-------|-------|--------|
| `pqa test list` | vjan-nie | ⏳ Pendiente |
| `pqa test run` | vjan-nie | ⏳ Pendiente |
| `pqa test add` (interactivo + --quick) | vjan-nie | ⏳ Pendiente |
| `pqa test edit` | vjan-nie | ⏳ Pendiente |
| `pqa test delete` | vjan-nie | ⏳ Pendiente |
| `pqa test export` | vjan-nie | ⏳ Pendiente |

### Fase 6 — Dashboard React + libcss

| Tarea | Owner | Estado |
|-------|-------|--------|
| Scaffold Vite + React + TS | serjimen | ⏳ Pendiente |
| Integrar libcss | serjimen | ⏳ Pendiente |
| Cliente API (`shared/api/`) | serjimen | ⏳ Pendiente |
| Stores Zustand | serjimen + dlesieur | ⏳ Pendiente |
| Test List (tabla + filtros) | serjimen + dlesieur | ⏳ Pendiente |
| Run Results (WebSocket live) | dlesieur | ⏳ Pendiente |
| Test Form (crear/editar) | serjimen | ⏳ Pendiente |
| Test Detail (historial) | dlesieur | ⏳ Pendiente |

### Fase 7 — Documentación y CI

| Tarea | Owner | Estado |
|-------|-------|--------|
| README actualizado | dlesieur | ⏳ Pendiente |
| `how-to-add-a-test.md` actualizado | dlesieur | ⏳ Pendiente |
| Step CI en `transcendence` | Ambos | ⏳ Pendiente |

---

## 15. Next Steps

Orden de prioridad estricto — cada fase desbloquea la siguiente.

```
🔴 Fase 0 — vjan-nie (~2h)
    Limpiar Node · instalar Python · adaptar Makefile
    Desbloquea: todo lo demás
        │
        ├─────────────────────────────────────────┐
        ▼                                         ▼
🔴 Fase 1 — dlesieur (~3h)               🔴 Fase 2 — vjan-nie (~4h)
    core/db.py                                runner Python
    core/schema.py                            bash executor
    core/git_export.py                        results persistence
    pytest mínimo                             4 tests pasando
        │                                         │
        └──────────────┬──────────────────────────┘
                       ▼
                🟡 Fase 3 — ambos (~1h)
                    migrate_v1_to_v2.py
                    10 tests en Atlas
                    4 tests verificados
                       │
                       ▼
                🟡 Fase 4 — dlesieur (~6h)
                    API FastAPI completa
                    Swagger UI funcionando
                       │
                       ├──────────────────────────┐
                       ▼                          ▼
                🟢 Fase 5 — vjan-nie (~4h)  🟢 Fase 6 — serjimen + dlesieur (~8h)
                    CLI pqa completo              Dashboard React + libcss
                    Cliente de la API             Cliente de la API
                       │                          │
                       └──────────┬───────────────┘
                                  ▼
                           🟢 Fase 7 — dlesieur (~2h)
                               README · how-to · CI
```

### Criterio de éxito

La v3 está completa cuando se cumplen estas cinco condiciones simultáneamente:

1. `pqa test run --priority P0` pasa los 4 tests activos existentes
2. El dashboard muestra los 10 tests en una tabla con filtros funcionando
3. Un developer puede crear un test desde el dashboard y verlo aparecer en `test-definitions/`
4. Un developer puede lanzar tests desde el dashboard y ver resultados en tiempo real
5. `node_modules/` ya no existe en el repositorio

---

*Este documento refleja la estrategia acordada tras el análisis del Roadmap 2 y la propuesta de integración del dashboard con libcss.*
*Actualizar cuando una fase se complete o una decisión cambie.*
*Anterior: [roadmap-1.md](roadmap-1.md) · Main README: [README.md](README.md)*
