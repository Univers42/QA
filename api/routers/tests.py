"""
Tests router — CRUD operations on test definitions.

Endpoints and Operations:
    GET    /tests          List all tests with optional filters
    GET    /tests/{id}     Get a specific test by ID
    POST   /tests          Create a new test (validates with Pydantic)
    PATCH  /tests/{id}     Update an existing test
    DELETE /tests/{id}     Soft-delete: sets status to "deprecated"

CRUD Flow:
    Create:  POST /tests → Validate pydantic → Check ID uniqueness → Insert
    Read:    GET /tests or GET /tests/{id} → Query database
    Update:  PATCH /tests/{id} → Merge → Re-validate → Update document
    Delete:  DELETE /tests/{id} → Set status="deprecated" (soft delete)

All operations integrate with MongoDB Atlas directly via pymongo.

Dependencies:
    - api.deps.get_database: MongoDB connection pooling
    - core.schema.parse_test: Pydantic validation
    - core.query_builder.QueryBuilder: Safe filter construction
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from api.deps import get_database
from core.query_builder import QueryBuilder
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
    """
    List all test definitions, with optional filters.
    
    Query Parameters:
        domain: Filter by domain (auth, gateway, schema, etc.)
        priority: Filter by priority (P0, P1, P2, P3)
        status: Filter by status (active, draft, skipped, deprecated)
        repo: Filter by repository name
        layer: Filter by layer (backend, frontend, infra, full-stack)
        author: Filter by test author
        group: Filter by team group
        runner: Filter by runner type (http, bash, jest, pytest)
    
    Returns:
        JSON with 'tests' array and 'total' count.
        
    Notes:
        - All filters are optional and can be combined
        - No filters returns all tests
        - Does not include MongoDB _id field
    """
    # Build query using centralized QueryBuilder
    query = (
        QueryBuilder()
        .with_domain(domain)
        .with_priority(priority)
        .with_status(status)
        .with_repo(repo)
        .with_layer(layer)
        .with_author(author)
        .with_group(group)
        .with_runner(runner)
        .build()
    )

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
