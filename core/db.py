"""
MongoDB Atlas connection — single source of truth for all database access.

Every module that needs MongoDB imports from here. No fallback to local Docker.
If Atlas is unreachable, the error is immediate and explicit.

Usage:
    from core.db import get_db
    db = get_db()
    tests = db["tests"].find({"status": "active"})
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

load_dotenv()

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return a cached MongoClient connected to Atlas. Raises on failure."""
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI_ATLAS")
        if not uri:
            raise RuntimeError(
                "MONGO_URI_ATLAS is not set.\n"
                "Copy .env.example to .env and add your Atlas connection string:\n"
                "  cp .env.example .env"
            )
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Fail fast: verify Atlas is reachable before returning
        _client.admin.command("ping")
    return _client


def get_db() -> Database:
    """Return the test_hub database handle."""
    return get_client()["test_hub"]


def disconnect() -> None:
    """Close the MongoDB connection. Safe to call multiple times."""
    global _client
    if _client:
        _client.close()
        _client = None


def ensure_indexes() -> None:
    """Create required indexes if they don't exist.

    Called once during setup or migration. Safe to run multiple times —
    MongoDB ignores duplicate index creation.
    """
    db = get_db()

    # Unique constraint on test ID — prevents duplicate definitions
    db["tests"].create_index("id", unique=True)

    # Compound index for the most common query pattern: filter by domain + priority + status
    db["tests"].create_index([("domain", 1), ("priority", 1), ("status", 1)])

    # Results: find latest runs for a test, ordered by time
    db["results"].create_index([("test_id", 1), ("executed_at", -1)])

    # Results: auto-purge after 90 days (Atlas M0 has 512MB limit)
    db["results"].create_index("executed_at", expireAfterSeconds=90 * 24 * 3600)
