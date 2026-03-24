"""
Migrate v1 test definitions (JSON on disk) into Atlas.

Reads every .json file under test-definitions/, validates against the
Pydantic schema, and upserts into the Atlas 'tests' collection.

Run once after setting up the Python environment:
    python scripts/migrate_v1_to_v2.py

Safe to run multiple times — uses upsert on the 'id' field.
"""

import json
import sys
import os
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db, ensure_indexes, disconnect
from core.schema import parse_test


DEFINITIONS_DIR = Path("test-definitions")

# Map folder names to domain values (handles v1 'gw' → 'gateway')
FOLDER_TO_DOMAIN = {
    "gw": "gateway",
}


def load_json_files() -> list[tuple[Path, dict]]:
    """Walk test-definitions/ and load all .json files."""
    files = []
    for json_path in sorted(DEFINITIONS_DIR.rglob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            files.append((json_path, data))
        except json.JSONDecodeError as e:
            print(f"  ✗  SKIP  {json_path} — invalid JSON: {e}")
    return files


def migrate():
    db = get_db()
    ensure_indexes()
    tests_col = db["tests"]

    files = load_json_files()
    if not files:
        print("  ⚠  No JSON files found in test-definitions/")
        return

    print(f"  ℹ  Found {len(files)} test definition(s)\n")

    ok = 0
    failed = 0

    for path, data in files:
        test_id = data.get("id", path.stem)

        # Fix domain if folder name doesn't match domain value
        folder_name = path.parent.name
        if folder_name in FOLDER_TO_DOMAIN:
            data["domain"] = FOLDER_TO_DOMAIN[folder_name]

        try:
            # Validate against Pydantic schema
            test = parse_test(data)
            doc = test.model_dump(exclude_none=False)

            # Upsert into Atlas — safe to run multiple times
            tests_col.update_one(
                {"id": test.id},
                {"$set": doc},
                upsert=True,
            )
            status = doc.get("status", "?")
            print(f"  ✓  {test_id:<12} {status:<10} {path}")
            ok += 1

        except Exception as e:
            print(f"  ✗  {test_id:<12} FAILED     {path}")
            print(f"     → {e}")
            failed += 1

    print()
    print(f"  {'─' * 50}")
    print(f"  Migrated : {ok}")
    print(f"  Failed   : {failed}")
    print(f"  Total    : {ok + failed}")
    print(f"  {'─' * 50}")

    if failed == 0:
        print(f"\n  ✓  All tests migrated to Atlas successfully.")
    else:
        print(f"\n  ⚠  {failed} test(s) failed validation — fix and re-run.")


if __name__ == "__main__":
    try:
        migrate()
    finally:
        disconnect()
