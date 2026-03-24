"""
Git export — write test documents to test-definitions/ as JSON files.

The JSON files in test-definitions/ are the historical source of truth
(committed to git). Atlas is the operational source of truth. This module
bridges the two: it takes a test dict from Atlas and writes it to disk
in the correct domain folder.

Usage:
    from core.git_export import export_test, export_all_tests

    path = export_test(test_dict)
    # → test-definitions/auth/AUTH-001.json

    paths = export_all_tests(list_of_dicts)
    # → [Path(...), Path(...), ...]
"""

import json
from pathlib import Path


DEFINITIONS_DIR = Path("test-definitions")

# Fields that are internal to MongoDB and should not appear in the JSON files
INTERNAL_FIELDS = {"_id", "_legacy"}


def export_test(test: dict) -> Path:
    """Write a single test to test-definitions/{domain}/{id}.json.

    Returns the Path where the file was written.
    """
    domain = test["domain"]
    test_id = test["id"]

    folder = DEFINITIONS_DIR / domain
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{test_id}.json"

    # Remove MongoDB internal fields
    clean = {k: v for k, v in test.items() if k not in INTERNAL_FIELDS}

    path.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def export_all_tests(tests: list[dict]) -> list[Path]:
    """Write multiple tests to disk. Returns list of written paths."""
    return [export_test(t) for t in tests]
