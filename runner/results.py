"""
Result persistence — writes test execution results to Atlas.

Each run produces one document per test in the 'results' collection.
Results older than 90 days are auto-purged by the TTL index (see core/db.py).

Usage:
    from runner.results import persist_result
    persist_result(result_dict, environment="local", run_by="developer")
"""

from datetime import UTC, datetime

from core.db import get_db


def persist_result(
    result: dict,
    environment: str = "local",
    run_by: str = "developer",
) -> dict:
    """Write a single test result to the results collection.

    Args:
        result: Dict from executor (test_id, passed, duration_ms, etc.)
        environment: "local", "staging", or "production"
        run_by: "developer", "ci-pipeline", or "dashboard"

    Returns:
        The inserted document.
    """
    db = get_db()
    doc = {
        **result,
        "environment": environment,
        "run_by": run_by,
        "executed_at": datetime.now(UTC),
    }
    db["results"].insert_one(doc)
    return doc
