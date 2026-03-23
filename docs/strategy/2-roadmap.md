# Prismatica QA — Roadmap 2

*Nueva estrategia: Python, CLI interactivo (`pqa`), Atlas como backend primario.*

*Marzo 2026 · Version 1.0 · dlesieur & vjan-nie*

---

## Table of Contents

- [1. Por qué cambiamos de estrategia](#1-por-qué-cambiamos-de-estrategia)
- [2. Qué cambia respecto a la v1](#2-qué-cambia-respecto-a-la-v1)
- [3. Nuevo stack técnico](#3-nuevo-stack-técnico)
- [4. Nueva estructura del repositorio](#4-nueva-estructura-del-repositorio)
- [5. Esquema flexible de tests](#5-esquema-flexible-de-tests)
- [6. El CLI — `pqa`](#6-el-cli--pqa)
- [7. El flujo completo de principio a fin](#7-el-flujo-completo-de-principio-a-fin)
- [8. Estrategia offline — Docker como fallback real](#8-estrategia-offline--docker-como-fallback-real)
- [9. Plan de migración — de v1 a v2](#9-plan-de-migración--de-v1-a-v2)
- [10. Tradeoffs críticos y decisiones pendientes](#10-tradeoffs-críticos-y-decisiones-pendientes)
- [11. Progress Against Objectives](#11-progress-against-objectives)
- [12. Next Steps](#12-next-steps)

---

## 1. Por qué cambiamos de estrategia

El Roadmap 1 cerró el pipeline básico: MongoDB local, tests en JSON, runner TypeScript, 4 tests activos pasando. Sin embargo, el feedback del equipo identificó tres problemas estructurales que frenarían la adopción a escala.

**Problema 1 — Node es el lenguaje incorrecto para QA**
El runner y los scripts de QA no son una aplicación web. No necesitan el ecosistema de Node. Python es más políglota dentro del equipo, más directo para scripting HTTP, y no arrastra la complejidad de TypeScript + ts-node para lo que es esencialmente automatización de pruebas.

**Problema 2 — Los JSON a mano matan la adopción**
Escribir un fichero de 20 campos para cada test, validarlo, seedearlo manualmente y commitearlo es demasiada fricción. Si añadir un test cuesta 10 minutos, los developers no lo hacen. La solución no es simplificar el schema — es eliminar la edición manual de JSON del flujo de trabajo principal.

**Problema 3 — MongoDB local no da visibilidad de equipo**
Con cada developer corriendo su propia instancia local, los resultados son invisibles para los demás. Los tests que pasan en local de un developer no se saben hasta el CI. Perdemos la capacidad de usar los resultados como documentación viva del estado del sistema.

---

## 2. Qué cambia respecto a la v1

| Aspecto | v1 (Roadmap 1) | v2 (este roadmap) |
|---------|---------------|-------------------|
| Lenguaje | TypeScript / Node.js | Python 3.11+ |
| Interfaz principal | Editar JSON a mano + `make seed` | CLI interactivo `pqa` |
| Fuente de verdad para ejecución | MongoDB local (Docker) | Atlas (compartido) |
| Fuente de verdad para historial | JSON en git | JSON en git (sin cambios) |
| Validación | `make validate` (AJV) | Pydantic v2 dentro del CLI |
| Tipos de test soportados | HTTP únicamente | HTTP + Bash/Script + Manual |
| Offline | No contemplado | `pqa test sync --to-local` |
| Resultados visibles al equipo | No (local únicamente) | Sí (Atlas compartido) |

Lo que **no cambia**:
- Los JSON en `test-definitions/` siguen existiendo y siguen commiteándose en git
- El flujo TDD (draft → active → passing) no cambia
- La estructura de dominios y prioridades no cambia
- La compatibilidad con CI (exit 0 / exit 1) no cambia

---

## 3. Nuevo stack técnico

### Eliminado

- `package.json`, `tsconfig.json`, `node_modules/`
- `runner/src/cli.ts` (TypeScript)
- `scripts/db.ts`, `scripts/seed.ts`, `scripts/validate.ts`
- Comandos `make seed` y `make validate` como flujos principales

### Añadido

| Librería | Rol |
|----------|-----|
| `typer` | Framework CLI — subcomandos, autocompletado, ayuda automática |
| `rich` | Output en terminal — tablas, colores, progress bars |
| `pymongo` | Driver MongoDB — conexión a Atlas y a Docker local |
| `httpx` | Cliente HTTP async — llamadas a servicios bajo test |
| `pydantic v2` | Validación de schema flexible — reemplaza AJV |
| `python-dotenv` | Lectura de variables de entorno desde `.env` |

La elección de `typer` + `rich` es deliberada. `typer` genera ayuda automática (`pqa --help`, `pqa test add --help`), autocompletado en bash/zsh, y subcomandos anidados con mínimo código. `rich` da tablas, diffs en color y spinners sin dependencias adicionales.

### Instalación

```bash
# Crear entorno virtual (una vez)
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Instalar dependencias
pip install -r requirements.txt

# Instalar pqa como comando local
pip install -e .
```

Tras la instalación, `pqa` está disponible como comando en el shell activo.

---

## 4. Nueva estructura del repositorio

```
prismatica-qa/
├── cli/
│   ├── main.py                  # entrypoint: pqa
│   └── commands/
│       ├── add.py               # pqa test add
│       ├── edit.py              # pqa test edit <ID>
│       ├── list.py              # pqa test list
│       ├── delete.py            # pqa test delete <ID>
│       ├── run.py               # pqa test run
│       ├── export.py            # pqa test export  (Atlas → JSON en disco)
│       └── sync.py              # pqa test sync    (Atlas ↔ Docker local)
├── runner/
│   ├── executor.py              # ejecuta tests tipo http
│   ├── bash_executor.py         # ejecuta tests tipo bash/script
│   └── results.py               # persiste resultados en MongoDB
├── core/
│   ├── db.py                    # conexión MongoDB (Atlas + fallback local)
│   ├── schema.py                # modelos Pydantic (schema flexible)
│   └── git_export.py            # escribe JSON en test-definitions/
├── test-definitions/            # JSON auto-generados — fuente de verdad en git
│   ├── auth/
│   ├── gateway/
│   ├── infra/
│   ├── api/
│   ├── realtime/
│   ├── storage/
│   ├── ui/
│   └── schema/
├── scripts/
│   └── migrate_v1_to_v2.py      # migración única desde el schema v1
├── docs/
│   ├── test-template.json       # referencia (ya no es el flujo principal)
│   ├── how-to-add-a-test.md     # actualizado para pqa
│   ├── ai-unblock-guide.md
│   └── demo-guide.md
├── requirements.txt
├── pyproject.toml               # define el comando pqa (entry point)
├── Makefile                     # adaptado a Python
├── docker-compose.yml           # sin cambios — MongoDB fallback
└── .env.example
```

---

## 5. Esquema flexible de tests

### El problema del schema v1

En v1, todos los tests comparten los mismos 15+ campos. Un test de smoke de infraestructura y un test de autenticación con payload tienen exactamente el mismo schema. Esto fuerza a poner valores vacíos o nulos en campos que no aplican, y hace imposible representar tests de tipo bash o manual.

### La solución: modelo base + extensiones por tipo

Pydantic v2 permite definir un modelo base con los campos mínimos obligatorios, y modelos derivados que añaden campos específicos por tipo. El CLI y el runner detectan el tipo y validan el modelo correcto.

**Campos obligatorios — solo estos cinco para cualquier test:**

```python
class TestBase(BaseModel):
    id:       str       # "AUTH-042" — validado contra Atlas para unicidad
    title:    str       # mínimo 5 caracteres
    domain:   Domain    # enum: auth, gateway, schema, api, realtime, storage, ui, infra
    priority: Priority  # enum: P0, P1, P2, P3
    status:   Status    # enum: draft, active, skipped, deprecated
```

Un test válido puede tener solo estos cinco campos. Esto permite documentar comportamiento esperado sin automatización — útil para tests manuales o features aún no implementadas.

**Extensión para tests HTTP:**

```python
class HttpTest(TestBase):
    type: Literal["http"]
    url: str
    method: HttpMethod           # GET POST PUT PATCH DELETE
    headers: dict | None = None
    payload: dict | None = None
    expected: HttpExpected       # statusCode + bodyContains + jsonPath assertions
```

**Extensión para tests Bash/Script:**

```python
class BashTest(TestBase):
    type: Literal["bash"]
    script: str                  # bash inline o path relativo a un .sh
    expected_exit_code: int = 0
    expected_output: str | None = None
    timeout_seconds: int = 30
```

Ejemplo de test bash — verifica que PostgreSQL acepta conexiones:

```json
{
  "id": "INFRA-006",
  "title": "PostgreSQL acepta conexiones en :5432",
  "domain": "infra",
  "priority": "P0",
  "status": "active",
  "type": "bash",
  "script": "pg_isready -h localhost -p 5432 -U postgres",
  "expected_exit_code": 0
}
```

**Test manual — el más ligero posible:**

```python
class ManualTest(TestBase):
    type: Literal["manual"] | None = None
    notes: str | None = None
    # nada más — válido con los 5 campos base
```

Ejemplo — documenta un comportamiento que requiere verificación humana:

```json
{
  "id": "UI-001",
  "title": "El formulario de login muestra error en campo vacío",
  "domain": "ui",
  "priority": "P2",
  "status": "draft",
  "type": "manual",
  "notes": "Verificar visualmente que aparece mensaje de validación inline sin enviar el formulario"
}
```

### Campos opcionales comunes (cualquier tipo puede incluirlos)

```python
tags:          list[str] | None     # ["smoke", "regression", "security"]
phase:         str | None           # "phase-0", "phase-1" — liga tests a migraciones
layer:         Layer | None         # unit, integration, e2e, contract
environment:   list[str] | None     # ["local", "staging", "production"]
preconditions: list[str] | None     # ["Requiere CREATE SCHEMA auth en PostgreSQL"]
notes:         str | None           # cualquier observación libre
```

---

## 6. El CLI — `pqa`

`pqa` es el **Prismatica QA CLI** — la interfaz de línea de comandos que reemplaza la edición manual de JSON, `make seed` y `make validate`. Habla directamente con MongoDB (Atlas en condiciones normales, Docker local en offline) y exporta automáticamente los tests a JSON en disco para que git mantenga el historial.

### Estructura de subcomandos

```
pqa
└── test
    ├── add       — crear un nuevo test (interactivo o con flags)
    ├── edit      — modificar un test existente
    ├── delete    — marcar como deprecated o eliminar
    ├── list      — listar tests con filtros
    ├── run       — ejecutar tests contra servicios
    ├── export    — exportar tests de Atlas a JSON en disco
    └── sync      — sincronizar entre Atlas y Docker local
```

### `pqa test add` — modo interactivo

```
$ pqa test add

  Domain [auth/gateway/infra/api/realtime/storage/ui/schema]: auth
  Next available ID in domain: AUTH-004
  Use AUTH-004? [Y/n]: y
  Title: Login con credenciales expiradas devuelve 401
  Type [http/bash/manual]: http
  Priority [P0/P1/P2/P3]: P1
  URL: http://localhost:9999/token
  Method [GET/POST/PUT/PATCH/DELETE]: POST

  Add headers? [y/N]: n
  Add payload? [y/N]: y
  Payload (JSON): {"email": "test@prismatica.dev", "password": "expired123"}

  Expected status code [200]: 401
  Expected body contains (comma-separated, optional): error

  ┌─────────────────────────────────────────────────────┐
  │  AUTH-004 · P1 · auth · http                        │
  │  Login con credenciales expiradas devuelve 401       │
  │  POST http://localhost:9999/token → 401              │
  └─────────────────────────────────────────────────────┘

  Confirm? [Y/n]: y

  ✓ AUTH-004 saved to Atlas
  ✓ Exported to test-definitions/auth/AUTH-004.json
  ✓ Run: git add test-definitions/auth/AUTH-004.json && git commit -m "test(auth): add AUTH-004"
```

La validación de unicidad de ID ocurre antes de mostrar el formulario — el CLI consulta Atlas y sugiere el siguiente ID disponible.

### `pqa test add --quick` — una línea, sin prompts

Para developers que prefieren trabajar sin modo interactivo:

```bash
pqa test add \
  --id AUTH-005 \
  --title "Token refresh devuelve nuevo access_token" \
  --domain auth \
  --priority P1 \
  --type http \
  --url http://localhost:9999/token \
  --method POST \
  --expected-status 200 \
  --expected-body access_token
```

### `pqa test run` — ejecución con filtros

```bash
pqa test run                              # todo lo que esté active
pqa test run --domain auth               # solo dominio auth
pqa test run --priority P0              # solo tests bloqueantes
pqa test run --domain auth --priority P1
pqa test run --env staging              # contra staging
pqa test run --id AUTH-003              # un test específico
```

Output en terminal:

```
Running 4 tests (domain: all, priority: all, env: local)

  ┌─────────────┬────────┬──────┬──────────────────────────────────────┬──────────────┐
  │ ID          │ Status │  ms  │ Title                                │ Error        │
  ├─────────────┼────────┼──────┼──────────────────────────────────────┼──────────────┤
  │ INFRA-003   │  ✓     │  12  │ GoTrue health                        │              │
  │ INFRA-004   │  ✓     │   8  │ PostgREST health                     │              │
  │ INFRA-005   │  ✓     │  11  │ MinIO health                         │              │
  │ AUTH-003    │  ✓     │  15  │ No token returns 401                 │              │
  └─────────────┴────────┴──────┴──────────────────────────────────────┴──────────────┘

  4 passed · 0 failed · 46ms total · exit 0
```

Con fallos:

```
  │ AUTH-004    │  ✗     │  11  │ Login expirado devuelve 401          │ got 500      │

  3 passed · 1 failed · exit 1
```

El runner escribe cada resultado en la colección `results` de Atlas con timestamp, duración, entorno y git SHA del commit actual.

### `pqa test list` — inspección rápida

```bash
pqa test list
pqa test list --domain auth
pqa test list --status draft
pqa test list --priority P0
pqa test list --type bash
```

Output:

```
  Tests · 10 total · 4 active · 4 draft · 2 skipped

  ┌─────────────┬──────────┬──────┬────────┬────────────────────────────────────────┐
  │ ID          │ Domain   │ Prio │ Status │ Title                                  │
  ├─────────────┼──────────┼──────┼────────┼────────────────────────────────────────┤
  │ INFRA-003   │ infra    │ P0   │ active │ GoTrue health                          │
  │ INFRA-004   │ infra    │ P0   │ active │ PostgREST health                       │
  │ AUTH-003    │ auth     │ P0   │ active │ No token returns 401                   │
  │ AUTH-001    │ auth     │ P0   │ draft  │ Login returns access_token             │
  └─────────────┴──────────┴──────┴────────┴────────────────────────────────────────┘
```

### `pqa test edit <ID>` — modificar un test existente

```bash
pqa test edit AUTH-003
```

Abre el documento actual en un formulario interactivo idéntico al de `add`, con los valores actuales pre-rellenos. Al confirmar:

1. Actualiza el documento en Atlas
2. Sobreescribe el JSON en `test-definitions/`
3. Muestra el diff en terminal antes de confirmar si hay cambios significativos

### `pqa test export` — Atlas → JSON en disco

Exporta los documentos de Atlas a sus ficheros JSON correspondientes. Útil tras un `sync` o para asegurarse de que git está al día con Atlas.

```bash
pqa test export              # exporta todos los tests
pqa test export --domain auth
pqa test export --since 2026-03-20    # solo tests modificados desde esa fecha
```

Si el fichero ya existe y hay diferencias, muestra el diff antes de sobreescribir:

```
  AUTH-003.json — changes detected:
  - "status": "skipped"
  + "status": "active"

  Overwrite? [Y/n]:
```

### `pqa test sync` — migración offline

```bash
# Antes de una sesión sin conexión
pqa test sync --to-local
# Copia tests y resultados de Atlas a Docker local

# Cuando vuelve la conexión
pqa test sync --to-atlas
# Sube cambios locales a Atlas
# Si hay conflictos: "last write wins" con warning en terminal
```

---

## 7. El flujo completo de principio a fin

### Escribir un test nuevo

```
Developer
    │
    ▼
pqa test add                    ← CLI interactivo o --quick
    │
    ├── valida unicidad de ID contra Atlas
    ├── valida schema con Pydantic v2
    │
    ├──► Atlas                  ← escritura primaria
    │       tests collection
    │
    └──► test-definitions/      ← exportación automática
              domain/ID.json
                   │
                   ▼
            git commit          ← developer commitea
                   │
                   ▼
            git history         ← trazabilidad permanente
```

### Ejecutar tests

```
pqa test run [--domain X] [--priority Y] [--env Z]
    │
    ├── lee tests de Atlas (status: active + filtros)
    ├── para cada test:
    │       ├── tipo http → runner/executor.py
    │       ├── tipo bash → runner/bash_executor.py
    │       └── tipo manual → skip con nota
    ├── escribe resultados en Atlas (results collection)
    └── imprime tabla en terminal
              │
              ▼
        exit 0 / exit 1        ← compatible con CI
```

### Diagrama completo

```
┌─────────────────────────────────────────────────┐
│  Git (fuente de verdad histórica)               │
│  test-definitions/**/*.json                     │
└───────────────┬─────────────────────────────────┘
                │ commit automático tras add/edit
                ▼
┌─────────────────────────────────────────────────┐
│  Atlas M0 (fuente de verdad operacional)        │
│  tests collection + results collection          │
└──────┬───────────────────────┬──────────────────┘
       │                       │
       │ pqa test run          │ pqa test sync --to-local
       ▼                       ▼
┌──────────────┐    ┌──────────────────────────────┐
│  Runner      │    │  Docker local (fallback)      │
│  Python      │    │  mongo:7 · :27017             │
└──────┬───────┘    └──────────────────────────────┘
       │ HTTP / bash
       ▼
┌─────────────────────────────────────────────────┐
│  Servicios bajo test (mini-baas-infra)          │
│  GoTrue · PostgREST · MinIO · Kong · Realtime   │
└─────────────────────────────────────────────────┘
```

---

## 8. Estrategia offline — Docker como fallback real

`core/db.py` implementa la lógica de conexión con detección automática de disponibilidad:

```python
def get_client() -> MongoClient:
    atlas_uri = os.getenv("MONGO_URI_ATLAS")
    local_uri  = os.getenv("MONGO_URI_LOCAL", "mongodb://localhost:27017")

    if atlas_uri:
        try:
            client = MongoClient(atlas_uri, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            return client   # Atlas disponible — flujo normal
        except Exception:
            print("[warn] Atlas unreachable — falling back to local MongoDB")

    return MongoClient(local_uri)  # Docker local
```

### Flujo de trabajo offline deliberado

```bash
# Antes de desconectarte
pqa test sync --to-local
make up                         # Docker local corriendo

# Sesión offline — pqa funciona normalmente contra Docker local
pqa test add ...
pqa test run ...

# Cuando vuelves a tener red
pqa test sync --to-atlas        # sube cambios locales
pqa test export                 # regenera JSON en disco
git add test-definitions/
git commit -m "chore: sync tests after offline session"
```

### Comportamiento del sync en caso de conflicto

La estrategia por defecto es **last-write-wins con warning**:

```
  Conflict detected on AUTH-004:
    Atlas version:  modified 2026-03-22 10:15 by vjan-nie
    Local version:  modified 2026-03-22 11:30 by dlesieur

  [1] Keep Atlas version
  [2] Keep local version
  [3] Show diff and decide

  Choice [1/2/3]:
```

---

## 9. Plan de migración — de v1 a v2

### Fase M0 — Limpieza y setup Python *(~2h · vjan-nie)*

- [ ] Borrar `package.json`, `tsconfig.json`, `node_modules/`, `runner/src/`
- [ ] Crear `requirements.txt` con las dependencias listadas en §3
- [ ] Crear `pyproject.toml` con el entry point `pqa`
- [ ] Adaptar `Makefile`: `make install` → `pip install -e .`, `make test` → `pqa test run`
- [ ] Verificar Python 3.11+ en todos los entornos del equipo
- [ ] Actualizar `.env.example` con `MONGO_URI_ATLAS` y `MONGO_URI_LOCAL`

### Fase M1 — Core: conexión y schema *(~3h · dlesieur)*

- [ ] `core/db.py` — conexión con fallback Atlas → local
- [ ] `core/schema.py` — modelos Pydantic: `TestBase`, `HttpTest`, `BashTest`, `ManualTest`
- [ ] `core/git_export.py` — escribe JSON a `test-definitions/domain/ID.json`
- [ ] Tests unitarios mínimos del schema (pytest)

### Fase M2 — Runner Python *(~4h · vjan-nie)*

- [ ] `runner/executor.py` — reproduces el comportamiento del runner TypeScript actual (HTTP)
- [ ] `runner/bash_executor.py` — soporte para tests tipo bash
- [ ] `runner/results.py` — persiste resultados en Atlas
- [ ] Verificar que los 4 tests activos (INFRA-003, INFRA-004, INFRA-005, AUTH-003) siguen pasando

### Fase M3 — CLI `pqa` *(~6h · dlesieur)*

- [ ] `cli/main.py` — entrypoint con grupo de comandos `test`
- [ ] `cli/commands/add.py` — modo interactivo + flags `--quick`
- [ ] `cli/commands/run.py` — reemplaza `make test`
- [ ] `cli/commands/list.py` — listado con filtros
- [ ] `cli/commands/edit.py` — edición con diff preview
- [ ] `cli/commands/export.py` — genera JSON en `test-definitions/`
- [ ] `cli/commands/sync.py` — Atlas ↔ local con resolución de conflictos

### Fase M4 — Migración de datos existentes *(~1h · ambos)*

- [ ] Ejecutar `scripts/migrate_v1_to_v2.py` — adapta los 10 tests existentes al nuevo schema
- [ ] Re-exportar a JSON con `pqa test export`
- [ ] Verificar que los 4 tests activos siguen pasando con el runner Python
- [ ] Commitar los JSON actualizados

### Fase M5 — Documentación y CI *(~2h · dlesieur)*

- [ ] Actualizar `README.md` — nuevo stack, nuevos comandos
- [ ] Actualizar `docs/how-to-add-a-test.md` — flujo con `pqa`
- [ ] Actualizar step de CI en `transcendence` (`npm install` → `pip install -e .`)
- [ ] Actualizar `docs/ai-unblock-guide.md` con contexto v2

---

## 10. Tradeoffs críticos y decisiones pendientes

### Tradeoffs asumidos

| Tradeoff | Decisión tomada | Razón |
|----------|----------------|-------|
| JSON en disco vs solo Atlas | Ambos — Atlas para ejecución, JSON para historial | Git es irremplazable para trazabilidad y resolución de conflictos entre branches |
| git add automático vs manual | El CLI exporta JSON y **avisa**, el developer hace el commit | El developer mantiene control sobre el historial; evita commits sucios |
| Atlas M0 gratuito (512MB) | Aceptable para el volumen previsto | ~365MB/año a 100 tests × 10 runs/día; monitorizar a partir de 200 tests activos |
| Ejecución secuencial vs paralela | Secuencial por ahora | Suficiente para <200 tests; migrar a `asyncio` + `anyio` cuando el tiempo de suite supere 30s |
| Conflictos en sync | Last-write-wins con prompt de resolución | Suficiente mientras los conflictos sean raros; revisar si el equipo crece |

### Decisiones aún abiertas — necesitan respuesta del equipo

**¿Autocompletado de shell activado por defecto?**
`typer` puede instalar autocompletado en bash/zsh con `pqa --install-completion`. ¿Lo activamos en `make install` automáticamente o lo dejamos opcional?

**¿`pqa test run` persiste resultados en Atlas también en local/offline?**
En modo offline, ¿los resultados se guardan en Docker local y se sincronizan después con `--to-atlas`, o se descartan?
Recomendación: guardar en local con flag `synced: false` y sincronizar en el próximo `sync --to-atlas`.

**¿Cómo se gestiona la capacidad de Atlas M0?**
Atlas M0 tiene 512MB. ¿Añadimos un TTL index en `results` para purgar automáticamente resultados con más de 90 días?

---

## 11. Progress Against Objectives

### Fase M0 — Limpieza y setup Python

| Tarea | Owner | Estado |
|-------|-------|--------|
| Borrar artefactos Node | vjan-nie | ⏳ Pendiente |
| `requirements.txt` y `pyproject.toml` | vjan-nie | ⏳ Pendiente |
| `Makefile` adaptado a Python | vjan-nie | ⏳ Pendiente |
| Verificar Python 3.11+ en entornos del equipo | Ambos | ⏳ Pendiente |

### Fase M1 — Core

| Tarea | Owner | Estado |
|-------|-------|--------|
| `core/db.py` con fallback | dlesieur | ⏳ Pendiente |
| `core/schema.py` Pydantic v2 | dlesieur | ⏳ Pendiente |
| `core/git_export.py` | dlesieur | ⏳ Pendiente |

### Fase M2 — Runner Python

| Tarea | Owner | Estado |
|-------|-------|--------|
| `runner/executor.py` (HTTP) | vjan-nie | ⏳ Pendiente |
| `runner/bash_executor.py` | vjan-nie | ⏳ Pendiente |
| `runner/results.py` (Atlas) | vjan-nie | ⏳ Pendiente |
| 4 tests activos pasando con runner Python | vjan-nie | ⏳ Pendiente |

### Fase M3 — CLI `pqa`

| Tarea | Owner | Estado |
|-------|-------|--------|
| `pqa test add` (interactivo + --quick) | dlesieur | ⏳ Pendiente |
| `pqa test run` | dlesieur | ⏳ Pendiente |
| `pqa test list` | dlesieur | ⏳ Pendiente |
| `pqa test edit` | dlesieur | ⏳ Pendiente |
| `pqa test export` | dlesieur | ⏳ Pendiente |
| `pqa test sync` | dlesieur | ⏳ Pendiente |

### Fase M4 — Migración de datos

| Tarea | Owner | Estado |
|-------|-------|--------|
| `scripts/migrate_v1_to_v2.py` | Ambos | ⏳ Pendiente |
| 4 tests activos verificados post-migración | Ambos | ⏳ Pendiente |

### Fase M5 — Documentación y CI

| Tarea | Owner | Estado |
|-------|-------|--------|
| README actualizado | dlesieur | ⏳ Pendiente |
| `how-to-add-a-test.md` actualizado | dlesieur | ⏳ Pendiente |
| Step CI actualizado en `transcendence` | Ambos | ⏳ Pendiente |

---

## 12. Next Steps

Orden de prioridad estricto — cada fase desbloquea la siguiente.

```
🔴 M0 — vjan-nie
    Limpiar Node, instalar Python, adaptar Makefile
    Duración estimada: 2h
    Desbloquea: todo lo demás
        │
        ▼
🔴 M1 — dlesieur (en paralelo con M2 una vez M0 complete)
    core/db.py · core/schema.py · core/git_export.py
    Duración estimada: 3h
        │
        ▼
🔴 M2 — vjan-nie (en paralelo con M1)
    runner Python · bash executor · results persistence
    Verificar 4 tests activos pasando
    Duración estimada: 4h
        │
        ▼
🟡 M3 — dlesieur
    CLI pqa completo
    Duración estimada: 6h
        │
        ▼
🟡 M4 — ambos
    Migración de datos existentes · verificación
    Duración estimada: 1h
        │
        ▼
🟢 M5 — dlesieur
    Documentación · CI
    Duración estimada: 2h
        │
        ▼
🟢 Fases F3–F5 del roadmap original
    CI en transcendence · dashboard · WebSocket runner
    (sin cambios respecto a lo planificado)
```

### Criterio de éxito de la migración

La v2 está completa cuando se cumplen estas cuatro condiciones simultáneamente:

1. `pqa test run --priority P0` pasa los 4 tests activos existentes
2. Un developer nuevo puede añadir un test completo con `pqa test add` en menos de 2 minutos sin leer documentación
3. El JSON resultante aparece en `test-definitions/` y es commitable
4. `node_modules/` ya no existe en el repositorio

---

*Este documento refleja la estrategia acordada tras el feedback del equipo en marzo de 2026.*
*Actualizar cuando una fase se complete o una decisión cambie.*
*Anterior: [roadmap-1.md](roadmap-1.md) · Siguiente: roadmap-3.md (post-migración)*
