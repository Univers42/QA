"""
Results router — query test execution history and analytics.

Endpoints and Operations:
    GET /results           List execution results with optional filters (most recent first)
    GET /results/summary   Aggregate statistics: pass/fail/draft counts grouped by domain

Data Model:
    Each result document in 'results' collection contains:
    - test_id: Reference to test in 'tests' collection
    - passed: bool | None (True=pass, False=fail, None=skipped/error)
    - exit_code: int (process/HTTP status)
    - duration_ms: int (execution time)
    - executed_at: datetime (ISO 8601 timestamp)
    - run_by: str (which system executed: 'api', 'cli', 'dashboard', 'ci')
    - repo: str (which repository)
    - error: str | None (error message if failed)

Features:
    - History filtered by test_id for tracking individual test trends
    - Pass/fail filtering for result analysis
    - Domain-level aggregation for dashboard widgets
    - TTL index auto-purges results older than 90 days

Dependencies:
    - api.deps.get_database: MongoDB connection
"""

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from api.deps import get_database

router = APIRouter()


@router.get("")
async def list_results(
    test_id: str | None = Query(None, description="Filter by test ID"),
    passed: bool | None = Query(None, description="Filter by pass/fail"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    db: Database = Depends(get_database),
):
    """
    List execution results, ordered by most recent first.
    
    Query Parameters:
        test_id: Filter results for a specific test (for trend analysis)
        passed: Filter by result (true=pass, false=fail, null=error/skipped)
        limit: Maximum number of results (default: 50, max: 500)
    
    Returns:
        JSON with 'results' array and 'total' count.
        
    Notes:
        - Results older than 90 days are auto-deleted (TTL index)
        - Sorted by executed_at descending (newest first)
        - MongoDB _id field excluded from response
    """
    # Build query for filtering
    query: dict = {}
    if test_id:
        query["test_id"] = test_id
    if passed is not None:
        query["passed"] = passed

    results = list(
        db["results"]
        .find(query, {"_id": 0})
        .sort("executed_at", -1)
        .limit(limit)
    )

    return {
        "results": results,
        "total": len(results),
        "limit": limit,
    }


@router.get("/summary")
async def results_summary(
    db: Database = Depends(get_database),
):
    """
    Aggregate summary: count of tests by domain and status.
    
    Returns one entry per domain showing total tests, active count,
    draft count, and skipped count.
    
    Used for:
        - Dashboard widgets showing test distribution
        - Team overview of test coverage per domain
        - Identifying domains with many draft tests
    
    Returns:
        JSON with 'domains' array, each containing:
        - domain: Domain name
        - total: Total tests in domain
        - active: Count of active (executable) tests
        - draft: Count of draft (not yet ready) tests
        - skipped: Count of intentionally skipped tests
        
    Notes:
        - Aggregates from 'tests' collection, not 'results'
        - Results are sorted alphabetically by domain
    """
    # Aggregate by domain with status breakdown
    pipeline = [
        # Only count non-deprecated tests
        {"$match": {"status": {"$in": ["active", "draft", "skipped"]}}},
        # Group by domain, count by status
        {
            "$group": {
                "_id": "$domain",
                "total": {"$sum": 1},
                "active": {"$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}},
                "draft": {"$sum": {"$cond": [{"$eq": ["$status", "draft"]}, 1, 0]}},
                "skipped": {"$sum": {"$cond": [{"$eq": ["$status", "skipped"]}, 1, 0]}},
            }
        },
        # Sort alphabetically
        {"$sort": {"_id": 1}},
    ]

    domains = list(db["tests"].aggregate(pipeline))

    return {
        "domains": [
            {
                "domain": d["_id"],
                "total": d["total"],
                "active": d["active"],
                "draft": d["draft"],
                "skipped": d["skipped"],
            }
            for d in domains
        ]
    }
