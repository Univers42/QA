from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .catalog import DOMAINS, METHODS, PRIORITIES, STATUSES, TEST_TYPES, normalize_domain

REQUIRED_FIELDS = ("id", "title", "domain", "type", "layer", "priority", "expected", "status")
FIELD_ORDER = (
    "id",
    "title",
    "description",
    "domain",
    "type",
    "layer",
    "priority",
    "tags",
    "service",
    "component",
    "environment",
    "dependencies",
    "preconditions",
    "expected",
    "url",
    "method",
    "headers",
    "payload",
    "timeout_ms",
    "retries",
    "author",
    "phase",
    "status",
    "notes",
)

ID_RE = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<number>\d+)$")


@dataclass(frozen=True)
class DefinitionFile:
    path: Path
    doc: dict[str, Any] | None
    error: str | None = None


def iter_definition_files(tests_dir: Path, domain: str | None = None) -> Iterable[Path]:
    roots: list[Path]
    if domain:
        roots = [tests_dir / DOMAINS[normalize_domain(domain)].folder]
    else:
        roots = [entry for entry in tests_dir.iterdir() if entry.is_dir()]

    for root in roots:
        if not root.exists():
            continue
        yield from sorted(root.glob("*.json"))


def read_definition_files(tests_dir: Path, domain: str | None = None) -> list[DefinitionFile]:
    items: list[DefinitionFile] = []
    for path in iter_definition_files(tests_dir, domain):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("JSON root must be an object")
            items.append(DefinitionFile(path=path, doc=data))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            items.append(DefinitionFile(path=path, doc=None, error=str(exc)))
    return items


def validation_errors(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in doc or doc[field] in (None, ""):
            errors.append(f"Missing required field: {field}")

    domain = doc.get("domain")
    if domain and domain not in DOMAINS:
        errors.append(f"Invalid domain: {domain}")

    test_type = doc.get("type")
    if test_type and test_type not in TEST_TYPES:
        errors.append(f"Invalid type: {test_type}")

    priority = doc.get("priority")
    if priority and priority not in PRIORITIES:
        errors.append(f"Invalid priority: {priority}")

    status = doc.get("status")
    if status and status not in STATUSES:
        errors.append(f"Invalid status: {status}")

    method = doc.get("method")
    if method and method not in METHODS:
        errors.append(f"Invalid method: {method}")

    expected = doc.get("expected")
    if expected is not None and not isinstance(expected, dict):
        errors.append("Field 'expected' must be an object")

    return errors


def next_test_id(domain: str, tests_dir: Path) -> str:
    spec = DOMAINS[normalize_domain(domain)]
    highest = 0

    for item in read_definition_files(tests_dir, spec.key):
        if not item.doc:
            continue
        raw_id = str(item.doc.get("id", "")).strip()
        match = ID_RE.match(raw_id)
        if match and match.group("prefix") == spec.prefix:
            highest = max(highest, int(match.group("number")))

    return f"{spec.prefix}-{highest + 1:03d}"


def definition_path(tests_dir: Path, domain: str, test_id: str) -> Path:
    spec = DOMAINS[normalize_domain(domain)]
    return tests_dir / spec.folder / f"{test_id}.json"


def compact_definition(doc: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}

    for key in FIELD_ORDER:
        if key not in doc:
            continue

        value = doc[key]
        if key == "expected" and isinstance(value, dict):
            value = {name: part for name, part in value.items() if part not in (None, "", [], {})}
            compact[key] = value
            continue

        if value in (None, "", [], {}):
            continue
        compact[key] = value

    for key, value in doc.items():
        if key in compact or key.startswith("_"):
            continue
        if value in (None, "", [], {}):
            continue
        compact[key] = value

    return compact


def write_definition(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(compact_definition(doc), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

