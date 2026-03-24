"""
CI runner — execute tests directly without the API layer.

Used in GitHub Actions where starting a full FastAPI server is unnecessary.
Reads from Atlas, runs tests, persists results, and exits with code 0 or 1.

Usage:
    python -m runner.ci --priority P0
    python -m runner.ci --domain auth --priority P1
"""

import asyncio
import argparse
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db, disconnect
from runner.executor import execute_http_test
from runner.bash_executor import execute_bash_test
from runner.results import persist_result


def build_query(domain: str | None, priority: str | None) -> dict:
    """Build a MongoDB query from CLI filters."""
    query = {"status": "active"}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    return query


async def run_tests(domain: str | None, priority: str | None) -> list[dict]:
    """Fetch and execute all matching tests."""
    db = get_db()
    query = build_query(domain, priority)
    tests = list(db["tests"].find(query, {"_id": 0}))

    if not tests:
        print(f"  ⚠  No active tests found matching filters")
        return []

    results = []
    for t in tests:
        test_type = t.get("type", "http")

        if test_type == "bash":
            result = await execute_bash_test(t)
        elif test_type == "manual":
            result = {"test_id": t["id"], "passed": None, "duration_ms": 0, "error": "manual — skipped"}
        else:
            result = await execute_http_test(t)

        persist_result(result, environment="ci", run_by="ci-pipeline")
        results.append(result)

    return results


def print_results(results: list[dict]):
    """Print a pass/fail table to the terminal."""
    print()
    print(f"  {'ID':<14} {'Status':<8} {'ms':>6}  {'Error'}")
    print(f"  {'─' * 60}")

    for r in results:
        icon = "✓" if r["passed"] else "✗"
        error = r.get("error") or ""
        print(f"  {r['test_id']:<14} {icon:<8} {r['duration_ms']:>5}  {error}")

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if r["passed"] is False)
    total_ms = sum(r["duration_ms"] for r in results)

    print(f"  {'─' * 60}")
    print(f"  {passed} passed · {failed} failed · {total_ms}ms total")
    print()


def main():
    parser = argparse.ArgumentParser(description="Prismatica QA — CI test runner")
    parser.add_argument("--domain", type=str, default=None, help="Filter by domain")
    parser.add_argument("--priority", type=str, default=None, help="Filter by priority")
    args = parser.parse_args()

    try:
        results = asyncio.run(run_tests(args.domain, args.priority))
        print_results(results)

        failed = sum(1 for r in results if r["passed"] is False)
        sys.exit(1 if failed > 0 else 0)
    finally:
        disconnect()


if __name__ == "__main__":
    main()
