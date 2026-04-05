"""
Run router — execute tests and stream results.

Endpoints:
    POST /tests/run     Execute tests by filters, return all results at once.
    WS   /ws/run        WebSocket: stream results test-by-test in real time.

Test Discovery & Execution:
    1. Receives filter parameters (domain, priority, repo, layer, test_id)
    2. Builds MongoDB query using QueryBuilder (only active tests)
    3. Fetches matching tests from database
    4. Executes each test with appropriate runner (HTTP, Bash, Jest, Pytest)
    5. Persists results to 'results' collection
    6. Returns all results or streams via WebSocket

Dependencies:
    - api.deps.get_database: MongoDB connection from pool
    - runner.registry_executor.execute_registered_test: Test execution dispatcher
    - runner.results.persist_result: Result storage
    - core.query_builder.QueryBuilder: Safe MongoDB query building
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pymongo.database import Database

from api.deps import get_database
from core.query_builder import QueryBuilder
from runner.registry_executor import execute_registered_test
from runner.results import persist_result

router = APIRouter()


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
    """
    Execute all matching active tests and return results.

    Query Parameters:
        domain: Filter by test domain (auth, gateway, schema, etc.)
        priority: Filter by priority level (P0, P1, P2, P3)
        id (test_id): Run a specific test by ID
        repo: Filter by repository name
        layer: Filter by test layer (backend, frontend, infra, etc.)
        repo_root: Base directory for script execution (default: current dir)

    Returns:
        JSON with 'results' array and 'summary' (total, passed, failed, duration_ms)
    """
    # Build query for active tests only
    query = (
        QueryBuilder()
        .with_status("active")
        .with_domain(domain)
        .with_priority(priority)
        .with_test_id(test_id)
        .with_repo(repo)
        .with_layer(layer)
        .build()
    )

    tests = list(db["tests"].find(query, {"_id": 0}))

    all_results = []
    for t in tests:
        # Determine runner from registry entry or legacy type field
        runner = t.get("runner") or t.get("type", "http")
        entry = {**t, "runner": runner}

        result = await execute_registered_test(entry, repo_root=repo_root)
        persist_result(result, run_by="api", repo=t.get("repo"))
        all_results.append(result)

    # Calculate summary statistics
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
    """
    WebSocket endpoint: stream test results one by one.

    Client receives:
    - "start": Initial message with total test count
    - "result": Each test result as it completes
    - "done": Final summary with passed/failed/duration

    Flow:
    1. Accept WebSocket connection
    2. Receive JSON with filters: {domain?, priority?, id?, repo?, layer?, repo_root?}
    3. Stream results as tests execute
    4. Close with final summary
    """
    await ws.accept()

    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return

    db = get_database()

    # Build query for active tests using centralized QueryBuilder
    query = (
        QueryBuilder()
        .with_status("active")
        .with_domain(data.get("domain"))
        .with_priority(data.get("priority"))
        .with_test_id(data.get("id"))
        .with_repo(data.get("repo"))
        .with_layer(data.get("layer"))
        .build()
    )

    tests = list(db["tests"].find(query, {"_id": 0}))

    # Send initial message
    await ws.send_json({"type": "start", "total": len(tests)})

    repo_root = data.get("repo_root", ".")
    passed = 0
    failed = 0
    total_ms = 0

    # Stream results
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

    # Send final summary
    await ws.send_json(
        {"type": "done", "passed": passed, "failed": failed, "duration_ms": total_ms}
    )
    await ws.close()
