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
from core.git_export import export_test


router = APIRouter()


@router.get("")
async def list_tests(
    domain: str | None = Query(None, description="Filter by domain (auth, infra, etc.)"),
    priority: str | None = Query(None, description="Filter by priority (P0, P1, P2, P3)"),
    status: str | None = Query(None, description="Filter by status (active, draft, etc.)"),
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
    writes to Atlas, and exports to JSON on disk.
    """
    # Validate with Pydantic
    try:
        test = parse_test(body)
    except Exception as e:
        raise HTTPException(422, f"Validation error: {e}")

    # Check uniqueness
    if db["tests"].find_one({"id": test.id}):
        raise HTTPException(409, f"Test {test.id} already exists")

    doc = test.model_dump(exclude_none=False)
    db["tests"].insert_one(doc)

    # Export to JSON on disk
    path = export_test(doc)

    return {"id": test.id, "status": "created", "exported_to": str(path)}


@router.patch("/{test_id}")
async def update_test(
    test_id: str,
    body: dict,
    db: Database = Depends(get_database),
):
    """Update an existing test definition.

    Merges the provided fields with the existing document,
    re-validates, and exports to JSON.
    """
    existing = db["tests"].find_one({"id": test_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, f"Test {test_id} not found")

    # Merge: existing fields + new fields (new wins)
    merged = {**existing, **body}
    merged["id"] = test_id  # ID cannot change

    # Re-validate
    try:
        test = parse_test(merged)
    except Exception as e:
        raise HTTPException(422, f"Validation error: {e}")

    doc = test.model_dump(exclude_none=False)
    db["tests"].update_one({"id": test_id}, {"$set": doc})

    # Re-export to JSON
    path = export_test(doc)

    return {"id": test_id, "status": "updated", "exported_to": str(path)}


@router.delete("/{test_id}")
async def delete_test(
    test_id: str,
    db: Database = Depends(get_database),
):
    """Soft-delete a test — sets status to 'deprecated'.

    The test remains in Atlas and in the JSON file for traceability.
    """
    existing = db["tests"].find_one({"id": test_id})
    if not existing:
        raise HTTPException(404, f"Test {test_id} not found")

    db["tests"].update_one({"id": test_id}, {"$set": {"status": "deprecated"}})

    # Update the JSON file too
    updated = db["tests"].find_one({"id": test_id}, {"_id": 0})
    export_test(updated)

    return {"id": test_id, "status": "deprecated"}
