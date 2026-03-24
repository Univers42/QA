"""
Run router — execute tests and stream results.

Endpoints:
    POST /tests/run     Execute tests by filters, return all results at once
    WS   /ws/run        WebSocket: stream results test-by-test in real time
"""

import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from pymongo.database import Database

from api.deps import get_database
from runner.executor import execute_http_test
from runner.bash_executor import execute_bash_test
from runner.results import persist_result


router = APIRouter()


async def _execute_test(test: dict) -> dict:
    """Route a test to the correct executor based on its type."""
    test_type = test.get("type", "http")

    if test_type == "bash":
        return await execute_bash_test(test)
    elif test_type == "manual":
        return {
            "test_id": test["id"],
            "passed": None,
            "duration_ms": 0,
            "error": "manual — skipped",
        }
    else:
        return await execute_http_test(test)


def _build_query(
    domain: str | None = None,
    priority: str | None = None,
    test_id: str | None = None,
) -> dict:
    """Build a MongoDB filter for active tests."""
    query: dict = {"status": "active"}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if test_id:
        query["id"] = test_id
    return query


@router.post("/run")
async def run_tests(
    domain: str | None = Query(None),
    priority: str | None = Query(None),
    test_id: str | None = Query(None, alias="id"),
    db: Database = Depends(get_database),
):
    """Execute all matching active tests and return results."""
    query = _build_query(domain, priority, test_id)
    tests = list(db["tests"].find(query, {"_id": 0}))

    all_results = []
    for t in tests:
        result = await _execute_test(t)
        persist_result(result, run_by="api")
        all_results.append(result)

    passed = sum(1 for r in all_results if r["passed"] is True)
    failed = sum(1 for r in all_results if r["passed"] is False)
    total_ms = sum(r["duration_ms"] for r in all_results)

    return {
        "results": all_results,
        "summary": {
            "total": len(all_results),
            "passed": passed,
            "failed": failed,
            "duration_ms": total_ms,
        },
    }


@router.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    """WebSocket endpoint: stream test results one by one.

    Client sends a JSON message with optional filters:
        {"domain": "auth", "priority": "P0"}

    Server responds with:
        {"type": "start", "total": N}
        {"type": "result", "test_id": "...", "passed": true, ...}  (N times)
        {"type": "done", "passed": N, "failed": N, "duration_ms": N}
    """
    await ws.accept()

    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return

    db = get_database()
    query = _build_query(
        domain=data.get("domain"),
        priority=data.get("priority"),
        test_id=data.get("id"),
    )
    tests = list(db["tests"].find(query, {"_id": 0}))

    await ws.send_json({"type": "start", "total": len(tests)})

    passed = 0
    failed = 0
    total_ms = 0

    for t in tests:
        result = await _execute_test(t)
        persist_result(result, run_by="dashboard")

        if result["passed"] is True:
            passed += 1
        elif result["passed"] is False:
            failed += 1
        total_ms += result["duration_ms"]

        await ws.send_json({"type": "result", **result})

    await ws.send_json({
        "type": "done",
        "passed": passed,
        "failed": failed,
        "duration_ms": total_ms,
    })
    await ws.close()
