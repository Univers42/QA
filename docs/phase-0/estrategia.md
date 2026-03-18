================================================================================
          ESTRATEGIA DEVOPS PARA MICROSERVICIOS Y TDD
================================================================================

Este es un giro de guion ambicioso y necesario. Pasar de un monorepo en Docker 
a una arquitectura de microservicios orquestada por Kubernetes (K8s) con una 
filosofía TDD y Template-First es subir a la "Champions League" del DevOps.

El plan de tu compañera para el QA y Pentesting es brillante en cuanto al "qué", 
pero el riesgo radica en el "cómo" y en la posible fragmentación. Si tenemos 6+ 
repositorios (auth, gateway, schema, etc.) y cada uno gestiona su propio Husky, 
sus reglas de ESLint y su CI de forma independiente, en un mes tendremos 6 
versiones distintas de la "verdad". El mantenimiento será una pesadilla.

A continuación, presento el análisis crítico, el nuevo diseño arquitectónico y 
el Plan de Acción detallado para empezar a trabajar hoy mismo.

--------------------------------------------------------------------------------
1. CRÍTICA PRAGMÁTICA AL PLAN DEL FRONTEND (Y LA SOLUCIÓN)
--------------------------------------------------------------------------------
El plan propuesto es excelente para un frontend aislado, pero en nuestro nuevo 
ecosistema distribuido tiene tres "puntos ciegos" que debemos abordar:

A. Husky vs. Native Hooks
El Problema: Husky requiere tener Node.js instalado en la máquina host del 
desarrollador. En un ecosistema de microservicios, podríamos tener un servicio 
escrito en Go o Rust. ¿Vamos a obligar al equipo a instalar Node.js globalmente 
solo para poder hacer un commit en un repositorio de Go?
El Veredicto: Mantener nuestro sistema de 'scripts/hooks' nativos (el patrón 
que adaptamos de transcendence). Al usar 'git config core.hooksPath', el sistema 
se basa en Bash estándar, es agnóstico al lenguaje y añade cero dependencias externas.

B. La Trampa de la Duplicación (CI/CD)
El Problema: Crear un archivo '.github/workflows/ci-fast.yml' distinto dentro 
de cada uno de los 6 repositorios. Si mañana queremos añadir un escaneo de 
vulnerabilidades de Docker, tendríamos que abrir 6 Pull Requests separadas.
El Veredicto: Usar "Reusable Workflows" (Workflows Reutilizables). Crearemos un 
pipeline maestro en nuestro repositorio central ('baas-infra'). Los demás 
repositorios solo tendrán un archivo de 3 líneas que básicamente dirá: "Llama 
al pipeline de baas-infra y pásale mi código".

C. El TDD en el Frontend
El Problema: Intentar hacer TDD puro (Red-Green-Refactor) sobre componentes 
visuales (React/Vue) genera tests frágiles que se rompen cada vez que cambia 
un color o un margen.
El Veredicto: Dividir la estrategia.
- Para la lógica pura (shared-library, auth, validación de formularios): TDD 
  estricto con Jest.
- Para el Frontend visual: Component Testing y los Smoke Tests E2E con Playwright 
  que propone tu compañera.

--------------------------------------------------------------------------------
2. EL "BLUE-PRINT" (TEMPLATE ESTÁNDAR DE REPOSITORIO)
--------------------------------------------------------------------------------
Para garantizar la escalabilidad, la regla de oro es que cada uno de nuestros 6 
repositorios debe nacer de una estructura idéntica (Standard Service Layout).

Estructura Obligatoria para cada Repo:
.
├── .git/
├── .github/
│   └── workflows/
│       └── pipeline.yml       # Just calls the baas-infra template (See Section 7)
├── k8s/                       # Kubernetes deployment manifests for this service
├── scripts/
│   ├── hooks/                 # The 5 standardized quality hooks
│   └── security/              # QA scripts from your colleague (xss, headers)
├── src/
│   ├── domain/                # Pure business logic (TDD happens here)
│   └── infrastructure/        # Adapters (DB connections, external APIs)
├── tests/
│   ├── unit/                  # TDD Unit Tests
│   └── e2e/                   # Playwright smoke tests
├── Makefile                   # The Standardized Orchestrator
└── Dockerfile                 # Multi-stage build (dev/prod)

--------------------------------------------------------------------------------
3. EL "SUPER-MAKEFILE" UNIVERSAL (EL CONTRATO)
--------------------------------------------------------------------------------
El Makefile de cada servicio actúa como un "contrato". No importa si el 
desarrollador está trabajando en el repo de NestJS o en uno de Python; el 
comando debe ser exactamente el mismo. Esto elimina la fricción cognitiva al 
cambiar de microservicio.

Ejemplo de Makefile Universal:

~~~makefile
# ==============================================================================
# UNIVERSAL SERVICE CONTRACT
# ==============================================================================
include .env
export

.PHONY: all dev test lint typecheck secure install-hooks

# --- 1. TDD & Development Flow ---
dev: ## 🔥 Start local development in Watch Mode
	@make docker-up
	@docker exec -it $(CONTAINER) pnpm run start:dev

test: ## 🧪 Run tests in Watch Mode (TDD Friendly)
	@docker exec -it $(CONTAINER) pnpm run test:watch

# --- 2. Quality Shield (Mandatory in all repos) ---
lint: ## 🔍 Check style (Front: stylelint/eslint | Back: eslint)
	@docker exec $(CONTAINER) pnpm lint

typecheck: ## 🏗️ Check types
	@docker exec $(CONTAINER) pnpm typecheck

secure: ## 🛡️ Run local Pentesting (QA Layer)
	@bash scripts/security/headers.sh
	@bash scripts/security/xss-check.sh

# --- 3. DevOps Shield Installation ---
install-hooks: ## 🛡️ Install standardized native hooks
	@git config --local core.hooksPath scripts/hooks
	@chmod +x scripts/hooks/*
	@echo "DevOps Shield Active."
~~~

--------------------------------------------------------------------------------
4. IMPLEMENTACIÓN DE TDD: FLUJO "RED-GREEN-REFACTOR"
--------------------------------------------------------------------------------
Para que el TDD sea una realidad y no solo una palabra de moda, el entorno debe 
ser altamente reactivo.

1. RED (Falla): El dev ejecuta 'make test'. El contenedor se queda escuchando 
   (Watch Mode). El dev crea 'auth.spec.ts' y escribe un test que falla. La 
   consola se pone roja al instante.
2. GREEN (Pasa): El dev escribe la lógica mínima en 'auth.service.ts'. La 
   consola se pone verde automáticamente, sin necesidad de reiniciar el comando.
3. REFACTOR: El dev limpia el código, sabiendo que la consola le avisará si 
   rompe algo.

Ejemplo Didáctico: Configuración requerida en el package.json del servicio:
"scripts": {
  "test:unit": "jest",
  "test:watch": "jest --watchAll"  # CRITICAL FOR TDD
}

--------------------------------------------------------------------------------
5. EL HOOK INTELIGENTE (BARRERA MULTI-LENGUAJE)
--------------------------------------------------------------------------------
En lugar de depender de Husky, nuestro hook 'pre-push' debe ser lo suficientemente 
inteligente para detectar el tipo de repositorio en el que reside y aplicar los 
tests correctos.

Ejemplo 'scripts/hooks/pre-push':

~~~bash
#!/bin/bash
# Adaptive DevOps Shield
. "$(dirname "$0")/log_hook.sh"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$CURRENT_BRANCH" == "develop" || "$CURRENT_BRANCH" == "main" ]]; then
    log_info "Detecting project type for Quality Checks..."

    # If it's a Node/TypeScript microservice
    if [ -f "package.json" ]; then
        log_info "Node.js project detected."
        make lint && make typecheck && make test:unit
    # If it's a Go microservice (future-proofing)
    elif [ -f "go.mod" ]; then
        log_info "Go project detected."
        go fmt ./... && go test ./...
    else
        log_warn "Unknown project type. Skipping specific linters."
    fi

    if [ $? -ne 0 ]; then
        log_error "Quality check FAILED. Push blocked."
        exit 1
    fi
fi
exit 0
~~~

--------------------------------------------------------------------------------
6. PLAN DE ACCIÓN (ESTRATEGIA EN 2 CAPAS)
--------------------------------------------------------------------------------
Para mantener el ritmo sin paralizar al equipo, dividiremos el trabajo.

CAPA A: LA BASE SÓLIDA (Semana 1 - Responsabilidad DevOps)
1. Repositorio 'baas-infra': Crear este hub central. Su único propósito es alojar 
   los workflows reutilizables de GitHub Actions y las imágenes base de Docker.
2. Template de Repo: Aplicar el Standard Service Layout (Makefile universal, 
   hooks nativos) al repositorio de QA actual.
3. Entorno Local K8s: Preparar un script (ej. 'make k8s-dev') que levante Minikube 
   o K3d localmente para que el equipo pueda probar el API Gateway interactuando 
   con el Auth Service.

CAPA B: ESPECIALIZACIÓN Y QA (Semana 1 - Responsabilidad de tu compañera)
Una vez que reciba el repositorio de QA con el Makefile y los hooks preinstalados, 
se centrará en:
1. Smoke Tests (Playwright): Añadir la suite de Playwright en 'tests/e2e/' para 
   asegurar que las rutas protegidas rechazan el acceso sin autenticar.
2. Fuzzing Básico: Poblar 'tests/security/payloads/' con archivos .txt que 
   contengan inyecciones SQL y cadenas XSS.
3. Integración del Escudo: Crear 'scripts/security/xss-check.sh' para leer esos 
   payloads, y añadir 'make secure' al hook pre-push para que el QA de seguridad 
   se ejecute automáticamente antes de tocar 'develop'.

--------------------------------------------------------------------------------
7. LA ARQUITECTURA CI/CD REUTILIZABLE (GITHUB ACTIONS)
--------------------------------------------------------------------------------
Así es como resolvemos la "Trampa de la Duplicación". Creamos un Workflow Maestro, 
y todos los microservicios simplemente lo llaman.

ARCHIVO 1: EL WORKFLOW MAESTRO (Ubicado en el repo 'Univers42/baas-infra')
Ruta: .github/workflows/reusable-service-ci.yml

~~~yaml
name: Reusable Service CI
on:
  workflow_call:
    inputs:
      service_name:
        required: true
        type: string
      node_version:
        required: false
        type: string
        default: '20'

jobs:
  quality-gates:
    name: ${{ inputs.service_name }} Quality Gates
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node_version }}
          cache: 'pnpm'

      - name: Install dependencies
        run: npm install -g pnpm && pnpm install

      - name: 🔍 Linting & Formatting
        run: make lint

      - name: 🏗️ Type Checking
        run: make typecheck

      - name: 🧪 TDD Unit Tests
        run: make test

      - name: 🛡️ Security Smoke Tests
        run: make secure
~~~

ARCHIVO 2: EL WORKFLOW LLAMADOR (Ubicado en 'auth-service', 'api-gateway', etc.)
Ruta: .github/workflows/pipeline.yml

~~~yaml
name: Auth Service Pipeline

on:
  push:
    branches: [ "develop", "main" ]
  pull_request:
    branches: [ "develop", "main" ]

jobs:
  # This single block delegates all CI logic to the master repository
  call-master-ci:
    uses: Univers42/baas-infra/.github/workflows/reusable-service-ci.yml@main
    with:
      service_name: 'auth-service'
      node_version: '20'
~~~

CONCLUSIÓN
Tratar la configuración de infraestructura y calidad como "Código Compartido" 
(Shared Code) es la única manera de sobrevivir a los microservicios. Con este 
plan, garantizamos que los errores humanos se detecten en la máquina local del 
desarrollador o en el CI centralizado, independientemente del microservicio en 
el que estén trabajando.
================================================================================