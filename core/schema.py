"""
Test definition models — Pydantic v2 schema validation.

Roadmap 6: Test Registry model.
  - HttpTest / BashTest / ManualTest — legacy DDA types (backward compatible)
  - RegistryEntry — new: metadata for scripts that live in external repos

Usage:
    from core.schema import parse_test

    data = {"id": "AUTH-001", "title": "Login works", ...}
    test = parse_test(data)  # Returns the correct subtype or raises ValidationError
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────


class Domain(StrEnum):
    auth = "auth"
    gateway = "gateway"
    schema_ = "schema"
    api = "api"
    realtime = "realtime"
    storage = "storage"
    ui = "ui"
    infra = "infra"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Status(StrEnum):
    draft = "draft"
    active = "active"
    skipped = "skipped"
    deprecated = "deprecated"


class Layer(StrEnum):
    backend = "backend"
    frontend = "frontend"
    database = "database"
    infra = "infra"
    full_stack = "full-stack"


class Runner(StrEnum):
    http = "http"
    bash = "bash"
    jest = "jest"
    pytest = "pytest"
    manual = "manual"


# ── Base model — 5 required fields for any test ──────────


class TestBase(BaseModel):
    """Minimum viable test definition. Valid on its own for manual/spec tests."""

    id: str = Field(..., pattern=r"^[A-Z]+-[A-Z0-9]+$", examples=["AUTH-001", "BAAS-PHASE08"])
    title: str = Field(..., min_length=5)
    domain: Domain
    priority: Priority
    status: Status

    # Optional metadata — any test type can include these
    description: str | None = None
    tags: list[str] | None = None
    phase: str | None = None
    layer: Layer | None = None
    type: str | None = None
    service: str | None = None
    component: str | None = None
    environment: list[str] | None = None
    preconditions: list[str] | None = None
    dependencies: list[str] | None = None
    author: str | None = None
    notes: str | None = None

    # ── Roadmap 6: Registry fields ──
    repo: str | None = None
    runner: Runner | None = None
    script: str | None = None
    group: str | None = None
    env_vars: dict[str, str] | None = None
    created_at: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    model_config = {"extra": "allow"}


# ── HTTP test ────────────────────────────────────────────


class HttpExpected(BaseModel):
    """Assertions for an HTTP response."""

    statusCode: int
    bodyContains: list[str] | None = None
    jwtClaims: dict | None = None
    cookieSet: str | None = None

    model_config = {"extra": "allow"}


class HttpTest(TestBase):
    """Test that makes an HTTP call and checks the response."""

    type: Literal["http"] | str = "http"
    url: str
    method: str = Field(..., pattern=r"^(GET|POST|PUT|PATCH|DELETE)$")
    headers: dict[str, str] | None = None
    payload: dict | None = None
    expected: HttpExpected
    timeout_ms: int = 5000
    retries: int = 1


# ── Bash test ────────────────────────────────────────────


class BashTest(TestBase):
    """Test that runs a shell command and checks exit code / output."""

    type: Literal["bash"]
    script: str
    expected_exit_code: int = 0
    expected_output: str | None = None
    timeout_seconds: int = 30


# ── Manual test ──────────────────────────────────────────


class ManualTest(TestBase):
    """Specification-only test — requires human verification."""

    type: Literal["manual"] | None = None


# ── Discriminated union ──────────────────────────────────

AnyTest = Annotated[
    HttpTest | BashTest | ManualTest,
    Field(discriminator="type"),
]


# ── Parser ───────────────────────────────────────────────


def parse_test(data: dict) -> HttpTest | BashTest | ManualTest:
    """Parse a raw dict into the correct test model.

    Detection logic:
      - If "type" == "bash"   → BashTest
      - If "type" == "manual" → ManualTest
      - If "url" is present   → HttpTest (even if type is missing — v1 compat)
      - Otherwise             → ManualTest (bare spec)

    Auto-sets author from PQA_USER if not provided.
    """
    # Auto-fill author from PQA_USER if missing
    if not data.get("author"):
        pqa_user = os.getenv("PQA_USER", "")
        if pqa_user:
            data = {**data, "author": pqa_user}

    # Auto-fill timestamps
    now = datetime.now(UTC).isoformat()
    if not data.get("created_at"):
        data = {**data, "created_at": now}
    data = {**data, "updated_at": now}

    test_type = data.get("type")

    if test_type == "bash":
        return BashTest(**data)
    elif test_type == "manual":
        return ManualTest(**data)
    elif test_type == "http" or "url" in data:
        data_copy = {**data}
        if "type" not in data_copy or data_copy["type"] not in ("http", "bash", "manual"):
            data_copy["type"] = "http"
        return HttpTest(**data_copy)
    else:
        return ManualTest(**data)
