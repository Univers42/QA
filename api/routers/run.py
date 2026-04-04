"""
Run router — execute tests and stream results.

Endpoints:
    POST /tests/run     Execute tests by filters, return all results at once
    WS   /ws/run        WebSocket: stream results test-by-test in real time
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pymongo.database import Database

from api.deps import get_database
from runner.registry_executor import execute_registered_test
from runner.results import persist_result

router = APIRouter()


def _build_query(
    domain: str | None = None,
    priority: str | None = None,
    test_id: str | None = None,
    repo: str | None = None,
    layer: str | None = None,
) -> dict:
    """Build a MongoDB filter for active tests."""
    query: dict = {"status": "active"}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if test_id:
        query["id"] = test_id
    if repo:
        query["repo"] = repo
    if layer:
        query["layer"] = layer
    return query


@router.post("/run")
async def run_tests(
    domain: str | None = Query(None),
    priority: str | None = Query(None),
    test_id: str | None = Query(None, alias="id"),
    repo: str | None = Query(None),
    layer: str | None = Query(None),
    repo_root: str = Query(".", description="Path to repo root for script-based tests"),
    db: Database = Depends(get_database),
):
    """Execute all matching active tests and return results."""
    query = _build_query(domain, priority, test_id, repo, layer)
    tests = list(db["tests"].find(query, {"_id": 0}))

    all_results = []
    for t in tests:
        # Determine runner from registry entry or legacy type
        runner = t.get("runner") or t.get("type", "http")
        entry = {**t, "runner": runner}

        result = await execute_registered_test(entry, repo_root=repo_root)
        persist_result(result, run_by="api", repo=t.get("repo"))
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
    """WebSocket endpoint: stream test results one by one."""
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
        repo=data.get("repo"),
        layer=data.get("layer"),
    )
    tests = list(db["tests"].find(query, {"_id": 0}))

    await ws.send_json({"type": "start", "total": len(tests)})

    repo_root = data.get("repo_root", ".")
    passed = 0
    failed = 0
    total_ms = 0

    for t in tests:
        runner = t.get("runner") or t.get("type", "http")
        entry = {**t, "runner": runner}

        result = await execute_registered_test(entry, repo_root=repo_root)
        persist_result(result, run_by="dashboard", repo=t.get("repo"))

        if result["passed"] is True:
            passed += 1
        elif result["passed"] is False:
            failed += 1
        total_ms += result["duration_ms"]

        await ws.send_json({"type": "result", **result})

    await ws.send_json(
        {"type": "done", "passed": passed, "failed": failed, "duration_ms": total_ms}
    )
    await ws.close()
