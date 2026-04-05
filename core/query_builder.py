"""
Query builder for MongoDB test filters.

Provides a fluent interface to construct MongoDB filter queries from optional parameters.
Eliminates query building duplication across api/routers/run.py, 
cli/commands/list_cmd.py, and cli/commands/run_cmd.py.

Usage:
    from core.query_builder import QueryBuilder
    
    # Build a query for active tests in auth domain
    query = QueryBuilder()
        .with_status("active")
        .with_domain("auth")
        .with_priority("P0")
        .build()
    
    # Now use in MongoDB
    results = db["tests"].find(query, {"_id": 0})
    
    # Can also build for draft tests
    all_query = QueryBuilder()
        .with_domain("auth")
        .build()  # No status filter → includes draft, active, etc.
"""

from typing import Optional


class QueryBuilder:
    """
    Fluent builder for MongoDB test filter queries.
    
    Handles optional filters gracefully:
    - Only includes matched fields where value is not None
    - Chains with .with_X() methods for readability
    - Builds final dict on .build()
    
    Example:
        query = QueryBuilder()
            .with_domain("auth")
            .with_priority("P0")
            .with_status("active")
            .build()
        # Result: {"domain": "auth", "priority": "P0", "status": "active"}
    """

    def __init__(self):
        """Initialize empty query dict."""
        self._query: dict = {}

    def with_domain(self, domain: Optional[str]) -> "QueryBuilder":
        """Filter by test domain (auth, gateway, schema, etc.)."""
        if domain:
            self._query["domain"] = domain
        return self

    def with_priority(self, priority: Optional[str]) -> "QueryBuilder":
        """Filter by priority level (P0, P1, P2, P3)."""
        if priority:
            self._query["priority"] = priority
        return self

    def with_status(self, status: Optional[str]) -> "QueryBuilder":
        """Filter by status (active, draft, skipped, deprecated)."""
        if status:
            self._query["status"] = status
        return self

    def with_statuses(self, statuses: Optional[list[str]]) -> "QueryBuilder":
        """
        Filter by one of multiple statuses.
        
        Args:
            statuses: List of status values to match
            
        Example:
            .with_statuses(["active", "draft"])
        """
        if statuses and len(statuses) > 0:
            self._query["status"] = {"$in": statuses}
        return self

    def with_layer(self, layer: Optional[str]) -> "QueryBuilder":
        """Filter by test layer (backend, frontend, database, infra, full-stack)."""
        if layer:
            self._query["layer"] = layer
        return self

    def with_repo(self, repo: Optional[str]) -> "QueryBuilder":
        """Filter by repository name."""
        if repo:
            self._query["repo"] = repo
        return self

    def with_runner(self, runner: Optional[str]) -> "QueryBuilder":
        """Filter by runner type (http, bash, jest, pytest, manual)."""
        if runner:
            self._query["runner"] = runner
        return self

    def with_author(self, author: Optional[str]) -> "QueryBuilder":
        """Filter by test author (who created/maintains the test)."""
        if author:
            self._query["author"] = author
        return self

    def with_group(self, group: Optional[str]) -> "QueryBuilder":
        """Filter by test group (logical grouping within domain)."""
        if group:
            self._query["group"] = group
        return self

    def with_test_id(self, test_id: Optional[str]) -> "QueryBuilder":
        """Filter by specific test ID (exact match)."""
        if test_id:
            self._query["id"] = test_id
        return self

    def with_custom_filter(self, field: str, value: any) -> "QueryBuilder":
        """
        Add a custom MongoDB filter for fields not covered by with_X methods.
        
        Args:
            field: MongoDB field name (e.g., "created_at")
            value: Value or MongoDB operator dict (e.g., {"$gt": 100})
        """
        if value is not None:
            self._query[field] = value
        return self

    def build(self) -> dict:
        """
        Finalize and return the MongoDB filter query dict.
        
        Returns:
            dict: MongoDB filter ready for db.collection.find(query)
            
        Example:
            query = QueryBuilder().with_domain("auth").with_status("active").build()
            # {"domain": "auth", "status": "active"}
        """
        return self._query.copy()

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"QueryBuilder({self._query})"
