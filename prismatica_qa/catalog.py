from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainSpec:
    key: str
    label: str
    folder: str
    prefix: str
    service: str
    layer: str
    base_url_env: str | None


DOMAINS: dict[str, DomainSpec] = {
    "auth": DomainSpec("auth", "Authentication", "auth", "AUTH", "auth-service", "backend", "GOTRUE_URL"),
    "gateway": DomainSpec("gateway", "Gateway", "gw", "GW", "api-gateway", "infra", "KONG_URL"),
    "schema": DomainSpec("schema", "Schema", "schema", "SCH", "schema-service", "backend", None),
    "api": DomainSpec("api", "API", "api", "API", "dynamic-api", "backend", "POSTGREST_URL"),
    "realtime": DomainSpec("realtime", "Realtime", "realtime", "RT", "realtime", "backend", "REALTIME_URL"),
    "storage": DomainSpec("storage", "Storage", "storage", "STG", "minio", "backend", "MINIO_URL"),
    "ui": DomainSpec("ui", "Frontend", "ui", "UI", "frontend", "frontend", "FRONTEND_URL"),
    "infra": DomainSpec("infra", "Infrastructure", "infra", "INFRA", "infrastructure", "infra", None),
}

DOMAIN_ALIASES = {
    "gw": "gateway",
    "gateway": "gateway",
}

TEST_TYPES = ("unit", "integration", "e2e", "smoke", "contract")
PRIORITIES = ("P0", "P1", "P2", "P3")
STATUSES = ("active", "draft", "deprecated", "skipped")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
BODY_METHODS = {"POST", "PUT", "PATCH"}

DEFAULT_TYPE = "integration"
DEFAULT_PRIORITY = "P1"
DEFAULT_STATUS = "draft"
DEFAULT_PHASE = "phase-0"


def normalize_domain(value: str) -> str:
    normalized = value.strip().lower()
    normalized = DOMAIN_ALIASES.get(normalized, normalized)
    if normalized not in DOMAINS:
        allowed = ", ".join(DOMAINS)
        raise ValueError(f"Invalid domain '{value}'. Allowed values: {allowed}")
    return normalized

