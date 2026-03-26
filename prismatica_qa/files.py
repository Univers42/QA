from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .catalog import DOMAINS, normalize_domain
from .models import canonicalize_test, validation_errors as model_validation_errors

REQUIRED_FIELDS = ("id", "title", "domain", "priority", "status")
FIELD_ORDER = (
    "id",
    "title",
    "description",
    "domain",
    "type",
    "suite",
    "module",
    "component",
    "priority",
    "status",
    "tags",
    "phase",
    "layer",
    "environment",
    "preconditions",
    "notes",
    "url",
    "method",
    "headers",
    "payload",
    "timeout_seconds",
    "expected",
    "script",
    "working_dir",
    "expected_exit_code",
    "expected_output",
)

ID_RE = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<number>\d+)$")


@dataclass(frozen=True)
class DefinitionFile:
    path: Path
    doc: dict[str, Any] | None
    error: str | None = None


# Yield JSON definition files from one definition root, optionally filtered by domain.
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


# Load JSON definitions from one root and keep file-level read or parse errors.
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


# Merge definition files coming from multiple roots into one ordered list.
def read_definition_files_from_roots(definition_dirs: Iterable[Path], domain: str | None = None) -> list[DefinitionFile]:
    items: list[DefinitionFile] = []
    seen_paths: set[Path] = set()

    for definition_dir in definition_dirs:
        if not definition_dir.exists():
            continue
        for item in read_definition_files(definition_dir, domain):
            if item.path in seen_paths:
                continue
            seen_paths.add(item.path)
            items.append(item)

    items.sort(key=lambda item: str(item.path))
    return items


# Validate required fields before delegating to the canonical model validator.
def validation_errors(doc: dict[str, Any]) -> list[str]:
    for field in REQUIRED_FIELDS:
        if field not in doc or doc[field] in (None, ""):
            return [f"Missing required field: {field}"]
    return model_validation_errors(doc)


# Compute the next domain-specific test identifier across one or more roots.
def next_test_id(domain: str, tests_dirs: Path | Iterable[Path]) -> str:
    spec = DOMAINS[normalize_domain(domain)]
    highest = 0
    roots = [tests_dirs] if isinstance(tests_dirs, Path) else list(tests_dirs)

    for item in read_definition_files_from_roots(roots, spec.key):
        if not item.doc:
            continue
        raw_id = str(item.doc.get("id", "")).strip()
        match = ID_RE.match(raw_id)
        if match and match.group("prefix") == spec.prefix:
            highest = max(highest, int(match.group("number")))

    return f"{spec.prefix}-{highest + 1:03d}"


# Resolve the repository path where a definition JSON file should be written.
def definition_path(tests_dir: Path, domain: str, test_id: str) -> Path:
    spec = DOMAINS[normalize_domain(domain)]
    return tests_dir / spec.folder / f"{test_id}.json"


# Canonicalize and compact a definition before serializing it to JSON.
def compact_definition(doc: dict[str, Any]) -> dict[str, Any]:
    doc = canonicalize_test(doc)
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


# Write one canonicalized test definition to disk.
def write_definition(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(compact_definition(doc), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
