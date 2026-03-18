================================================================================
          MICROSERVICES & TDD DEVOPS STRATEGY
================================================================================

This is an ambitious and necessary pivot. Transitioning from a Docker-based 
monorepo to a Kubernetes (K8s) orchestrated microservices architecture, driven 
by a TDD and Template-First philosophy, is stepping into the "Champions League" 
of DevOps.

Your colleague's plan for QA and Pentesting is brilliant regarding the "what," 
but the risk lies in the "how" and the potential for fragmentation. If we have 
6+ repositories (auth, gateway, schema, etc.) and each manages its own Husky, 
ESLint rules, and CI pipelines independently, within a month we will have 6 
different versions of the "truth." Maintenance will become a nightmare.

Below is the critical analysis, the new architectural blueprint, and the 
detailed Action Plan to get started today.

--------------------------------------------------------------------------------
1. PRAGMATIC CRITIQUE OF THE FRONTEND PLAN (AND THE SOLUTION)
--------------------------------------------------------------------------------
The proposed plan is excellent for an isolated frontend, but in our new 
distributed ecosystem, it has three "blind spots" we must address:

A. Husky vs. Native Hooks
The Problem: Husky requires Node.js to be installed on the developer's host 
machine. In a microservices ecosystem, we might eventually have a service 
written in Go or Rust. Are we going to force the team to install Node.js globally 
just to commit code to a Go repository?
The Verdict: Keep our native 'scripts/hooks' system (the pattern we adapted 
from transcendence). By using 'git config core.hooksPath', the system relies on 
standard Bash, remains language-agnostic, and adds zero external dependencies.

B. The Duplication Trap (CI/CD)
The Problem: Creating a distinct '.github/workflows/ci-fast.yml' file inside 
each of the 6 repositories. If tomorrow we want to add a Docker vulnerability 
scan, we would have to open 6 separate Pull Requests.
The Verdict: Use "Reusable Workflows." We will create a master pipeline in our 
central repository ('baas-infra'). The other repositories will only contain a 
3-line file that essentially says: "Call the baas-infra pipeline and pass my 
code to it."

C. TDD in the Frontend
The Problem: Attempting pure TDD (Red-Green-Refactor) on visual UI components 
(React/Vue) generates fragile tests that break every time a color or margin changes.
The Verdict: Split the strategy.
- For pure logic (shared-library, auth, form validations): Strict TDD with Jest.
- For the visual Frontend: Component Testing and the E2E Smoke Tests with 
  Playwright that your colleague proposed.

--------------------------------------------------------------------------------
2. THE "BLUE-PRINT" (STANDARD REPOSITORY TEMPLATE)
--------------------------------------------------------------------------------
To ensure scalability, the golden rule is that every single one of our 6 
repositories must be born from an identical structure (Standard Service Layout).

Mandatory Structure for Every Repo:
.
├── .git/
├── .github/
│   └── workflows/
│       └── pipeline.yml       <-- Just calls the baas-infra template (See Section 7)
├── k8s/                       <-- Kubernetes deployment manifests for this service
├── scripts/
│   ├── hooks/                 <-- The 5 standardized quality hooks
│   └── security/              <-- QA scripts from your colleague (xss, headers)
├── src/
│   ├── domain/                <-- Pure business logic (TDD happens here)
│   └── infrastructure/        <-- Adapters (DB connections, external APIs)
├── tests/
│   ├── unit/                  <-- TDD Unit Tests
│   └── e2e/                   <-- Playwright smoke tests
├── Makefile                   <-- The Standardized Orchestrator
└── Dockerfile                 <-- Multi-stage build (dev/prod)

--------------------------------------------------------------------------------
3. THE UNIVERSAL "SUPER-MAKEFILE" (THE CONTRACT)
--------------------------------------------------------------------------------
The Makefile in each service acts as a "contract." It doesn't matter if the 
developer is working in the NestJS repo or a Python repo; the command must be 
exactly the same. This eliminates cognitive friction when switching microservices.

Universal Makefile Example:

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
4. TDD IMPLEMENTATION: "RED-GREEN-REFACTOR" FLOW
--------------------------------------------------------------------------------
For TDD to be a reality and not just a buzzword, the environment must be highly 
reactive. 

1. RED (Fail): The dev runs 'make test'. The container stays alive listening 
   (Watch Mode). The dev creates 'auth.spec.ts' and writes a failing test. The 
   console instantly turns red.
2. GREEN (Pass): The dev writes the minimum logic in 'auth.service.ts'. The 
   console turns green automatically, without needing to restart the command.
3. REFACTOR: The dev cleans the code, knowing the console will alert them if 
   they break anything.

Didactic Example: Required configuration in the service's package.json:
"scripts": {
  "test:unit": "jest",
  "test:watch": "jest --watchAll"  <-- CRITICAL FOR TDD
}

--------------------------------------------------------------------------------
5. THE SMART HOOK (MULTI-LANGUAGE BARRIER)
--------------------------------------------------------------------------------
Instead of relying on Husky, our 'pre-push' hook must be intelligent enough to 
detect the type of repository it resides in and apply the correct tests.

Example 'scripts/hooks/pre-push':

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
6. ACTION PLAN (2-LAYER STRATEGY)
--------------------------------------------------------------------------------
To maintain momentum without paralyzing the team, we will divide the work.

LAYER A: THE SOLID FOUNDATION (Week 1 - DevOps Responsibility)
1. 'baas-infra' Repository: Create this central hub. Its sole purpose is to host 
   the reusable '.github/workflows' and base Docker images.
2. Repo Template: Apply the Standard Service Layout (Universal Makefile, 
   native hooks) to the current QA repository.
3. Local K8s Environment: Prepare a script (e.g., 'make k8s-dev') that spins 
   up Minikube or K3d locally so the team can test the API Gateway interacting 
   with the Auth Service.

LAYER B: SPECIALIZATION & QA (Week 1 - Colleague's Responsibility)
Once she receives the QA repository with the Makefile and hooks pre-installed, 
she will focus on:
1. Smoke Tests (Playwright): Add the Playwright suite in 'tests/e2e/' to ensure 
   protected routes reject unauthenticated access.
2. Basic Fuzzing: Populate 'tests/security/payloads/' with .txt files containing 
   SQL injection and XSS strings.
3. Shield Integration: Create 'scripts/security/xss-check.sh' to read those 
   payloads, and add 'make secure' to the pre-push hook so security QA runs 
   automatically before touching 'develop'.

--------------------------------------------------------------------------------
7. THE REUSABLE CI/CD ARCHITECTURE (GITHUB ACTIONS)
--------------------------------------------------------------------------------
This is how we solve the "Duplication Trap". We create one Master Workflow, 
and all microservices just call it.

FILE 1: THE MASTER WORKFLOW (Located in 'Univers42/baas-infra' repository)
Path: .github/workflows/reusable-service-ci.yml

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

FILE 2: THE CALLER WORKFLOW (Located in 'auth-service', 'api-gateway', etc.)
Path: .github/workflows/pipeline.yml

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

CONCLUSION
Treating infrastructure and quality configuration as "Shared Code" is the only 
way to survive microservices. With this plan, you guarantee that human errors 
are caught on the developer's local machine or the centralized CI, regardless 
of which microservice they are working on.
================================================================================