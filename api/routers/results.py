"""
Results router — query test execution history.

Endpoints:
    GET /results            List results with optional filters
    GET /results/summary    Aggregate pass/fail counts by domain
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
    """List execution results, most recent first."""
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

    return {"results": results, "total": len(results)}


@router.get("/summary")
async def results_summary(
    db: Database = Depends(get_database),
):
    """Aggregate summary: pass/fail counts per domain.

    Returns one entry per domain with total tests, active count,
    last run stats, etc.
    """
    pipeline = [
        {"$match": {"status": {"$in": ["active", "draft", "skipped"]}}},
        {"$group": {
            "_id": "$domain",
            "total": {"$sum": 1},
            "active": {"$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}},
            "draft": {"$sum": {"$cond": [{"$eq": ["$status", "draft"]}, 1, 0]}},
            "skipped": {"$sum": {"$cond": [{"$eq": ["$status", "skipped"]}, 1, 0]}},
        }},
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
