"""
Quick setup verification — run after 'make install' to confirm Atlas connects.

Usage:
    python scripts/verify_setup.py

Expected output:
    ✓ Atlas connection successful
    ✓ Database: test_hub
    ✓ Indexes created
    ✓ Collections: [...]
"""

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import disconnect, ensure_indexes, get_db


def main():
    try:
        db = get_db()
        print("  ✓  Atlas connection successful")
        print(f"  ✓  Database: {db.name}")

        ensure_indexes()
        print("  ✓  Indexes created")

        collections = db.list_collection_names()
        print(
            f"  ✓  Collections: {collections if collections else '(empty — ready for migration)'}"
        )

    except Exception as e:
        print(f"  ✗  Connection failed: {e}")
        sys.exit(1)
    finally:
        disconnect()

    print()
    print("  Setup OK — Atlas is ready.")


if __name__ == "__main__":
    main()
