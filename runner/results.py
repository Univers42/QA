"""
Result persistence — writes test execution results to Atlas.

Each run produces one document per test in the 'results' collection.
Results older than 90 days are auto-purged by the TTL index (see core/db.py).

Usage:
    from runner.results import persist_result
    persist_result(result_dict, environment="local", run_by="developer")
"""

import os
import subprocess
from datetime import UTC, datetime

from core.db import get_db


def _get_git_sha() -> str | None:
    """Get the current git SHA, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def persist_result(
    result: dict,
    environment: str = "local",
    run_by: str = "developer",
    repo: str | None = None,
) -> dict:
    """Write a single test result to the results collection.

    Args:
        result: Dict from executor (test_id, passed, duration_ms, etc.)
        environment: "local", "staging", or "production"
        run_by: "developer", "ci-pipeline", "cli", "api", or "dashboard"
        repo: Repository context (e.g. "mini-baas-infra")

    Returns:
        The inserted document.
    """
    db = get_db()
    pqa_user = os.getenv("PQA_USER", "")

    doc = {
        **result,
        "environment": environment,
        "run_by": pqa_user if pqa_user else run_by,
        "repo": repo or result.get("repo"),
        "git_sha": _get_git_sha(),
        "executed_at": datetime.now(UTC),
    }
    db["results"].insert_one(doc)
    return doc
