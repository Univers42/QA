"""
Centralized constants and enums for test management.

This module consolidates all domain-level constants (domains, priorities, statuses)
to ensure single source of truth across API, CLI, and runner modules.

Example:
    from core.constants import Domain, Priority, DOMAIN_HELP
    
    # Using enums
    active_domains = [Domain.AUTH, Domain.GATEWAY]
    
    # Using helper mappings
    help_text = DOMAIN_HELP[Domain.AUTH]
    id_prefix = REPO_TO_DOMAIN_PREFIX.get("mini-baas-infra", "UNKNOWN")
"""

from enum import StrEnum


class Domain(StrEnum):
    """Test domain enumeration — groups tests by service/feature area."""

    AUTH = "auth"
    GATEWAY = "gateway"
    SCHEMA = "schema"
    API = "api"
    REALTIME = "realtime"
    STORAGE = "storage"
    UI = "ui"
    INFRA = "infra"


class Priority(StrEnum):
    """Test priority levels — execution order and importance."""

    P0 = "P0"  # Critical path / full system
    P1 = "P1"  # Core functionality
    P2 = "P2"  # Important features
    P3 = "P3"  # Optional features


class Status(StrEnum):
    """Test lifecycle status — draft → active → skipped/deprecated."""

    DRAFT = "draft"  # Not ready, under development
    ACTIVE = "active"  # Ready to execute
    SKIPPED = "skipped"  # Intentionally skipped
    DEPRECATED = "deprecated"  # No longer valid (soft delete)


class Layer(StrEnum):
    """Test target layer — where the test exercises code."""

    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    INFRA = "infra"
    FULL_STACK = "full-stack"


class Runner(StrEnum):
    """Test execution engine/framework."""

    HTTP = "http"  # REST API testing (httpx)
    BASH = "bash"  # Shell script execution
    JEST = "jest"  # JavaScript testing
    PYTEST = "pytest"  # Python testing
    MANUAL = "manual"  # Manual / specification test


# ─── Domain Descriptions (for CLI help text) ───────────────────────────

DOMAIN_HELP = {
    Domain.AUTH: "GoTrue — authentication, login, OAuth, JWT, sessions",
    Domain.GATEWAY: "API Gateway — routing, rate limiting, auth middleware",
    Domain.SCHEMA: "Database schema — migrations, DDL, constraints",
    Domain.API: "Core REST API — endpoints, resources, business logic",
    Domain.REALTIME: "Realtime — WebSockets, subscriptions, pub/sub",
    Domain.STORAGE: "Cloud storage — file upload/download, CDN",
    Domain.UI: "User interface — web app, responsive, accessibility",
    Domain.INFRA: "Infrastructure — CI/CD, monitoring, databases, k8s",
}


# ─── Repository to Domain Prefix Mapping ──────────────────────────────
# Used by register_cmd.py to auto-generate test IDs from external repos.
# Format: {repo_name: id_prefix}
# Example: register tests from 'mini-baas-infra' repo → BAAS-001, BAAS-002, ...

REPO_TO_DOMAIN_PREFIX = {
    "mini-baas-infra": "BAAS",
    "transcendence": "FT",
    "qa": "QA",
}


# ─── Status Filter Presets ────────────────────────────────────────────

ACTIVE_STATUSES = [Status.ACTIVE]  # For queries that only want executable tests
INACTIVE_STATUSES = [Status.DRAFT, Status.SKIPPED, Status.DEPRECATED]
ALL_STATUSES = [Status.DRAFT, Status.ACTIVE, Status.SKIPPED, Status.DEPRECATED]


# ─── Valid Filter Combinations ────────────────────────────────────────

FILTERABLE_FIELDS = [
    "domain",
    "priority",
    "status",
    "layer",
    "repo",
    "runner",
    "author",
    "group",
]
"""Fields that can be used in MongoDB queries to filter tests."""

REQUIRED_TEST_FIELDS = [
    "id",
    "title",
    "domain",
    "priority",
    "status",
]
"""Minimum fields required for valid test definition."""
