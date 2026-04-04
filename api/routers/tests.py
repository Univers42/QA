"""
Tests router — CRUD operations on test definitions.

Endpoints:
    GET    /tests          List tests with optional filters
    GET    /tests/{id}     Get a single test by ID
    POST   /tests          Create a new test
    PATCH  /tests/{id}     Update an existing test
    DELETE /tests/{id}     Soft-delete (set status to deprecated)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from api.deps import get_database
from core.schema import parse_test

router = APIRouter()


@router.get("")
async def list_tests(
    domain: str | None = Query(None, description="Filter by domain"),
    priority: str | None = Query(None, description="Filter by priority"),
    status: str | None = Query(None, description="Filter by status"),
    repo: str | None = Query(None, description="Filter by repository"),
    layer: str | None = Query(None, description="Filter by development layer"),
    author: str | None = Query(None, description="Filter by codeowner"),
    group: str | None = Query(None, description="Filter by team group"),
    runner: str | None = Query(None, description="Filter by runner type"),
    db: Database = Depends(get_database),
):
    """List all test definitions, with optional filters."""
    query: dict = {}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if status:
        query["status"] = status
    if repo:
        query["repo"] = repo
    if layer:
        query["layer"] = layer
    if author:
        query["author"] = author
    if group:
        query["group"] = group
    if runner:
        query["runner"] = runner

    tests = list(db["tests"].find(query, {"_id": 0}))
    return {"tests": tests, "total": len(tests)}


@router.get("/{test_id}")
async def get_test(
    test_id: str,
    db: Database = Depends(get_database),
):
    """Get a single test definition by ID."""
    test = db["tests"].find_one({"id": test_id}, {"_id": 0})
    if not test:
        raise HTTPException(404, f"Test {test_id} not found")
    return test


@router.post("", status_code=201)
async def create_test(
    body: dict,
    db: Database = Depends(get_database),
):
    """Create a new test definition.

    Validates against Pydantic schema, checks ID uniqueness,
    and writes to Atlas.
    """
    try:
        test = parse_test(body)
    except Exception as e:
        raise HTTPException(422, f"Validation error: {e}") from None

    if db["tests"].find_one({"id": test.id}):
        raise HTTPException(409, f"Test {test.id} already exists")

    doc = test.model_dump(exclude_none=False)
    db["tests"].insert_one(doc)

    return {"id": test.id, "status": "created"}


@router.patch("/{test_id}")
async def update_test(
    test_id: str,
    body: dict,
    db: Database = Depends(get_database),
):
    """Update an existing test definition."""
    existing = db["tests"].find_one({"id": test_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, f"Test {test_id} not found")

    merged = {**existing, **body}
    merged["id"] = test_id

    try:
        test = parse_test(merged)
    except Exception as e:
        raise HTTPException(422, f"Validation error: {e}") from None

    doc = test.model_dump(exclude_none=False)
    db["tests"].update_one({"id": test_id}, {"$set": doc})

    return {"id": test_id, "status": "updated"}


@router.delete("/{test_id}")
async def delete_test(
    test_id: str,
    db: Database = Depends(get_database),
):
    """Soft-delete a test — sets status to 'deprecated'."""
    existing = db["tests"].find_one({"id": test_id})
    if not existing:
        raise HTTPException(404, f"Test {test_id} not found")

    db["tests"].update_one({"id": test_id}, {"$set": {"status": "deprecated"}})
    return {"id": test_id, "status": "deprecated"}
