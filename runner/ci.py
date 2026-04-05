"""
CI runner — standalone test execution for CI/CD pipelines.

Executes tests directly without the FastAPI API layer, making it ideal for
GitHub Actions, GitLab CI, or other CI/CD systems where spinning up a server
adds unnecessary overhead.

Flow:
    1. Parse CLI arguments (--domain, --priority filters)
    2. Connect to MongoDB Atlas
    3. Query for matching active tests
    4. Execute each test with appropriate runner (HTTP, Bash, Jest, Pytest)
    5. Persist results to database
    6. Print summary table
    7. Exit with code 0 (all pass) or 1 (any failures)

Usage:
    python -m runner.ci --domain auth --priority P0
    python -m runner.ci --priority P1
    python -m runner.ci  # All active tests

Environment:
    Requires MONGO_URI_ATLAS environment variable to be set.
    
Integration:
    GitHub Actions example:
        - name: Run QA Tests
          env:
            MONGO_URI_ATLAS: ${{ secrets.MONGO_URI }}
          run: python -m runner.ci --priority P0

Dependencies:
    - core.db: MongoDB connection
    - core.query_builder.QueryBuilder: Safe query construction
    - runner.registry_executor.execute_registered_test: Unified executor
    - runner.results.persist_result: Result persistence
"""

import argparse
import asyncio
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import disconnect, get_db
from core.query_builder import QueryBuilder
from runner.registry_executor import execute_registered_test
from runner.results import persist_result


async def run_tests(domain: str | None, priority: str | None) -> list[dict]:
    """
    Fetch and execute all matching active tests.
    
    Connects to MongoDB Atlas, finds tests matching filters,
    executes each with appropriate runner, and persists results.
    
    Args:
        domain: Filter by domain (optional)
        priority: Filter by priority level (optional)
        
    Returns:
        List of result dicts with passed, error, duration_ms, etc.
    """
    db = get_db()

    # Build query for active tests using centralized QueryBuilder
    query = (
        QueryBuilder()
        .with_status("active")
        .with_domain(domain)
        .with_priority(priority)
        .build()
    )

    tests = list(db["tests"].find(query, {"_id": 0}))

    if not tests:
        print("  ⚠️  No active tests found matching filters")
        return []

    print(f"  Running {len(tests)} test(s)...\n")

    results = []
    for t in tests:
        # Determine runner from registry entry or fall back to legacy 'type'
        runner = t.get("runner") or t.get("type", "http")
        entry = {**t, "runner": runner}

        result = await execute_registered_test(entry, repo_root=".")
        persist_result(result, environment="ci", run_by="ci-pipeline")
        results.append(result)

    return results


def print_results(results: list[dict]) -> None:
    """
    Print formatted results table to stdout.
    
    Shows:
    - Test ID
    - Pass/fail icon (✓/✗)
    - Execution time in milliseconds
    - Error message (if failed)
    - Summary: passed/failed/total time
    
    Args:
        results: List of result dicts from test execution
    """
    print()
    print(f"  {'ID':<14} {'Status':<8} {'ms':>6}  {'Error'}")
    print(f"  {'─' * 65}")

    for r in results:
        # Color-code status icon
        icon = "✓" if r["passed"] is True else ("✗" if r["passed"] is False else "—")
        error = r.get("error") or ""
        # Truncate long error messages
        error = error[:50] if len(error) > 50 else error
        print(f"  {r['test_id']:<14} {icon:<8} {r['duration_ms']:>5}  {error}")

    # Calculate and print summary
    passed = sum(1 for r in results if r["passed"] is True)
    failed = sum(1 for r in results if r["passed"] is False)
    total_ms = sum(r["duration_ms"] for r in results)

    print(f"  {'─' * 65}")
    print(f"  {passed} passed · {failed} failed · {total_ms}ms total")
    print()


def main() -> None:
    """
    Parse CLI arguments and execute test suite.
    
    Arguments:
        --domain: Filter by domain name
        --priority: Filter by priority level
    """
    parser = argparse.ArgumentParser(
        description="QA System — CI Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m runner.ci                          # All active tests
  python -m runner.ci --domain auth            # Auth domain only
  python -m runner.ci --priority P0             # P0 tests only
  python -m runner.ci --domain auth --priority P0  # Combined filters
        """,
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter by domain (auth, gateway, schema, api, etc.)",
    )
    parser.add_argument(
        "--priority",
        type=str,
        default=None,
        help="Filter by priority level (P0, P1, P2, P3)",
    )

    args = parser.parse_args()

    try:
        # Execute tests and handle results
        results = asyncio.run(run_tests(args.domain, args.priority))

        if results:
            print_results(results)

        # Exit with appropriate code
        failed_count = sum(1 for r in results if r["passed"] is False)
        sys.exit(1 if failed_count > 0 else 0)

    finally:
        disconnect()


if __name__ == "__main__":
    main()
