"""
Shared dependencies for FastAPI route handlers.

Provides the database handle as a dependency that can be injected
into any endpoint using FastAPI's Depends() mechanism.
"""

from pymongo.database import Database

from core.db import get_db


def get_database() -> Database:
    """Dependency: returns the test_hub database handle."""
    return get_db()
