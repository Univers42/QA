from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .catalog import DOMAINS, LAYERS, LEGACY_EXECUTORS, LEGACY_TEST_TYPES, PRIORITIES, STATUSES

ID_RE = re.compile(r"^[A-Z]+-\d+$")

COMMON_FIELDS = {
    "id",
    "title",
    "domain",
    "priority",
    "status",
    "tags",
    "phase",
    "layer",
    "environment",
    "preconditions",
    "notes",
}
TYPE_FIELDS = {
    "type",
    "url",
    "method",
    "timeout_seconds",
    "headers",
    "payload",
    "expected",
    "script",
    "expected_exit_code",
    "expected_output",
}
LEGACY_FIELDS = {"executor", "timeout_ms"}


class Domain(str, Enum):
    AUTH = "auth"
    GATEWAY = "gateway"
    SCHEMA = "schema"
    API = "api"
    REALTIME = "realtime"
    STORAGE = "storage"
    UI = "ui"
    INFRA = "infra"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Status(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SKIPPED = "skipped"
    DEPRECATED = "deprecated"


class Layer(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    CONTRACT = "contract"
    SMOKE = "smoke"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ModelValidationError(ValueError):
    pass


def require_string(doc: dict[str, Any], field: str, *, min_length: int = 1) -> str:
    value = doc.get(field)
    if not isinstance(value, str) or len(value.strip()) < min_length:
        raise ModelValidationError(f"Field '{field}' must be a string with at least {min_length} character(s)")
    return value.strip()


def optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ModelValidationError("Optional string field must be a string")
    stripped = value.strip()
    return stripped or None


def optional_string_list(value: Any) -> list[str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ModelValidationError("Optional list field must be a list of strings")
    cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
    return cleaned or None


def optional_string_dict(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ModelValidationError("Field must be an object")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ModelValidationError("Headers must be a string-to-string object")
        result[key] = item
    return result or None


def optional_layer(doc: dict[str, Any], detected_type: str) -> str | None:
    raw_layer = doc.get("layer")
    if isinstance(raw_layer, str) and raw_layer in LAYERS:
        return raw_layer

    raw_type = doc.get("type")
    if isinstance(raw_type, str) and raw_type in LEGACY_TEST_TYPES and detected_type != raw_type:
        return raw_type

    return None


def validate_test_id(test_id: str, domain: str) -> None:
    match = ID_RE.match(test_id)
    if not match:
        raise ModelValidationError("Field 'id' must match DOMAIN-NNN")

    expected_prefix = DOMAINS[domain].prefix
    actual_prefix = test_id.split("-", 1)[0]
    if actual_prefix != expected_prefix:
        raise ModelValidationError(
            f"Field 'id' must use prefix '{expected_prefix}-' for domain '{domain}'"
        )


def detect_test_type(doc: dict[str, Any]) -> str:
    raw_type = doc.get("type")
    if raw_type in ("http", "bash", "manual"):
        return raw_type
    if raw_type == "script":
        return "bash"

    raw_executor = doc.get("executor")
    if raw_executor in LEGACY_EXECUTORS:
        return "bash" if raw_executor == "script" else str(raw_executor)

    if doc.get("script"):
        return "bash"
    if doc.get("url") or doc.get("method") or (isinstance(doc.get("expected"), dict) and "statusCode" in doc["expected"]):
        return "http"
    return "manual"


@dataclass(frozen=True)
class TestBase:
    id: str
    title: str
    domain: Domain
    priority: Priority
    status: Status
    tags: list[str] | None = None
    phase: str | None = None
    layer: Layer | None = None
    environment: list[str] | None = None
    preconditions: list[str] | None = None
    notes: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_doc(cls, doc: dict[str, Any], detected_type: str) -> "TestBase":
        test_id = require_string(doc, "id")
        title = require_string(doc, "title", min_length=5)
        domain_value = require_string(doc, "domain")
        domain = Domain(domain_value)
        validate_test_id(test_id, domain.value)
        priority = Priority(require_string(doc, "priority"))
        status = Status(require_string(doc, "status"))

        raw_layer = optional_layer(doc, detected_type)
        layer = Layer(raw_layer) if raw_layer else None

        extras = {
            key: value
            for key, value in doc.items()
            if key not in COMMON_FIELDS | TYPE_FIELDS | LEGACY_FIELDS
        }

        return cls(
            id=test_id,
            title=title,
            domain=domain,
            priority=priority,
            status=status,
            tags=optional_string_list(doc.get("tags")),
            phase=optional_string(doc.get("phase")),
            layer=layer,
            environment=optional_string_list(doc.get("environment")),
            preconditions=optional_string_list(doc.get("preconditions")),
            notes=optional_string(doc.get("notes")),
            extras=extras,
        )

    def common_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "status": self.status.value,
        }
        if self.tags:
            result["tags"] = self.tags
        if self.phase:
            result["phase"] = self.phase
        if self.layer:
            result["layer"] = self.layer.value
        if self.environment:
            result["environment"] = self.environment
        if self.preconditions:
            result["preconditions"] = self.preconditions
        if self.notes:
            result["notes"] = self.notes
        return {**result, **self.extras}


@dataclass(frozen=True)
class HttpExpected:
    status_code: int
    body_contains: list[str] | None = None
    json_path: dict[str, Any] | None = None

    @classmethod
    def from_doc(cls, expected: Any) -> "HttpExpected":
        if not isinstance(expected, dict):
            raise ModelValidationError("HTTP tests require an 'expected' object")
        status_code = expected.get("statusCode")
        if not isinstance(status_code, int):
            raise ModelValidationError("HTTP tests require expected.statusCode as an integer")
        body_contains = optional_string_list(expected.get("bodyContains"))
        json_path = expected.get("jsonPath")
        if json_path is not None and not isinstance(json_path, dict):
            raise ModelValidationError("expected.jsonPath must be an object")
        return cls(status_code=status_code, body_contains=body_contains, json_path=json_path)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"statusCode": self.status_code}
        if self.body_contains:
            result["bodyContains"] = self.body_contains
        if self.json_path:
            result["jsonPath"] = self.json_path
        return result


@dataclass(frozen=True)
class HttpTest:
    base: TestBase
    url: str
    method: HttpMethod
    timeout_seconds: int = 5
    headers: dict[str, str] | None = None
    payload: dict[str, Any] | None = None
    expected: HttpExpected | None = None

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "HttpTest":
        base = TestBase.from_doc(doc, "http")
        url = require_string(doc, "url")
        method = HttpMethod(require_string(doc, "method"))
        timeout_seconds = doc.get("timeout_seconds")
        if timeout_seconds is None and isinstance(doc.get("timeout_ms"), int):
            timeout_seconds = max(1, int(doc["timeout_ms"] / 1000))
        if timeout_seconds is None:
            timeout_seconds = 5
        if not isinstance(timeout_seconds, int):
            raise ModelValidationError("HTTP tests require timeout_seconds as an integer")
        headers = optional_string_dict(doc.get("headers"))
        payload = doc.get("payload")
        if payload is not None and not isinstance(payload, dict):
            raise ModelValidationError("HTTP payload must be an object")
        expected = HttpExpected.from_doc(doc.get("expected"))
        return cls(
            base=base,
            url=url,
            method=method,
            timeout_seconds=timeout_seconds,
            headers=headers,
            payload=payload,
            expected=expected,
        )

    def to_dict(self) -> dict[str, Any]:
        result = self.base.common_dict()
        result.update(
            {
                "type": "http",
                "url": self.url,
                "method": self.method.value,
                "timeout_seconds": self.timeout_seconds,
                "expected": self.expected.to_dict() if self.expected else {},
            }
        )
        if self.headers:
            result["headers"] = self.headers
        if self.payload is not None:
            result["payload"] = self.payload
        return result


@dataclass(frozen=True)
class BashTest:
    base: TestBase
    script: str
    expected_exit_code: int = 0
    expected_output: str | None = None
    timeout_seconds: int = 30

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "BashTest":
        base = TestBase.from_doc(doc, "bash")
        script = require_string(doc, "script")

        expected_exit_code = doc.get("expected_exit_code")
        if expected_exit_code is None and isinstance(doc.get("expected"), dict):
            expected_exit_code = doc["expected"].get("exitCode")
        if expected_exit_code is None:
            expected_exit_code = 0
        if not isinstance(expected_exit_code, int):
            raise ModelValidationError("Bash tests require expected_exit_code as an integer")

        expected_output = doc.get("expected_output")
        if expected_output is None and isinstance(doc.get("expected"), dict):
            legacy_output = doc["expected"].get("outputContains")
            if isinstance(legacy_output, list) and legacy_output:
                expected_output = legacy_output[0]
        expected_output = optional_string(expected_output)

        timeout_seconds = doc.get("timeout_seconds")
        if timeout_seconds is None and isinstance(doc.get("timeout_ms"), int):
            timeout_seconds = max(1, int(doc["timeout_ms"] / 1000))
        if timeout_seconds is None:
            timeout_seconds = 30
        if not isinstance(timeout_seconds, int):
            raise ModelValidationError("Bash tests require timeout_seconds as an integer")

        return cls(
            base=base,
            script=script,
            expected_exit_code=expected_exit_code,
            expected_output=expected_output,
            timeout_seconds=timeout_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        result = self.base.common_dict()
        result.update(
            {
                "type": "bash",
                "script": self.script,
                "expected_exit_code": self.expected_exit_code,
                "timeout_seconds": self.timeout_seconds,
            }
        )
        if self.expected_output:
            result["expected_output"] = self.expected_output
        return result


@dataclass(frozen=True)
class ManualTest:
    base: TestBase
    type: str | None = "manual"

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "ManualTest":
        base = TestBase.from_doc(doc, "manual")
        raw_type = doc.get("type")
        if raw_type not in (None, "manual"):
            raise ModelValidationError("Manual tests must have type 'manual' or no type")
        return cls(base=base, type="manual" if raw_type is not None else None)

    def to_dict(self) -> dict[str, Any]:
        result = self.base.common_dict()
        result["type"] = "manual"
        return result


def parse_test(doc: dict[str, Any]) -> HttpTest | BashTest | ManualTest:
    detected_type = detect_test_type(doc)
    if detected_type == "http":
        return HttpTest.from_doc(doc)
    if detected_type == "bash":
        return BashTest.from_doc(doc)
    return ManualTest.from_doc(doc)


def canonicalize_test(doc: dict[str, Any]) -> dict[str, Any]:
    return parse_test(doc).to_dict()


def validation_errors(doc: dict[str, Any]) -> list[str]:
    try:
        canonicalize_test(doc)
    except (KeyError, TypeError, ValueError, ModelValidationError) as exc:
        return [str(exc)]
    return []
