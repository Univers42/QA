"""
MongoDB Atlas connection management — single source of truth for all database access.

Design Principles:
    - Singleton pattern: Only one client connection per process
    - Fail-fast on startup: Explicit error if Atlas is unreachable
    - Connection pooling: pymongo handles pool internally
    - No fallback: Always uses Atlas, never local Docker

Usage:
    from core.db import get_db, get_client, ensure_indexes
    
    # Get database handle
    db = get_db()  # Returns Database for "test_hub"
    tests = db["tests"].find({"status": "active"})
    
    # Setup (call once at app startup)
    ensure_indexes()

Connection Flow:
    1. get_client() creates MongoClient on first call
    2. Validates connection with admin.command("ping")
    3. Returns cached client for subsequent calls
    4. disconnect() closes connection when app shuts down

Environment:
    Requires: MONGO_URI_ATLAS — MongoDB Atlas connection string
    Loaded from: .env file via python-dotenv
    Fallback: Explicit error with setup instructions

Dependencies:
    - core.config.Settings: For environment validation
    - python-dotenv: For .env file loading
    - pymongo: MongoDB Python driver with async support
"""

from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from core.config import Settings

# Load environment variables from .env file
load_dotenv()

# Global client singleton
_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """
    Get or create MongoDB Atlas client.
    
    Implements singleton pattern with lazy initialization:
    - First call: Creates connection, validates with ping
    - Subsequent calls: Returns cached client
    - Errors: Fails fast with explicit error message
    
    Returns:
        MongoClient connected to MongoDB Atlas
        
    Raises:
        RuntimeError: If MONGO_URI_ATLAS not set or connection fails
        
    Example:
        client = get_client()
        db = client["test_hub"]
        tests = db["tests"].find_one({"id": "AUTH-001"})
    """
    global _client

    if _client is None:
        uri = Settings.MONGO_URI
        if not uri:
            raise RuntimeError(
                "MONGO_URI_ATLAS environment variable not set.\n"
                "Setup instructions:\n"
                "  1. Copy configuration: cp .env.example .env\n"
                "  2. Add your MongoDB Atlas connection string to .env\n"
                "  3. Format: MONGO_URI_ATLAS=mongodb+srv://....mongodb.net/...\n"
                "\n"
                "Create free cluster at: https://www.mongodb.com/cloud/atlas"
            )

        try:
            # Create client with fail-fast timeout (5 seconds)
            _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            
            # Verify connection before returning
            _client.admin.command("ping")
            
        except Exception as e:
            _client = None
            raise RuntimeError(f"MongoDB Atlas connection failed: {str(e)}") from e

    return _client


def get_db() -> Database:
    """
    Get database handle for "test_hub" database in Atlas.
    
    All test definitions and results are stored in this database.
    
    Returns:
        pymongo.database.Database instance
        
    Example:
        db = get_db()
        test = db["tests"].find_one({"id": "AUTH-001"})
        results = db["results"].find({"test_id": "AUTH-001"})
    """
    return get_client()["test_hub"]


def disconnect() -> None:
    """
    Close MongoDB connection and reset singleton.
    
    Safe to call multiple times (idempotent).
    Should be called at application shutdown to clean up resources.
    
    Used in:
        - CLI command teardown (finally block)
        - API server shutdown event
        - Test cleanup
        
    Example:
        try:
            db = get_db()
            # ... execute tests ...
        finally:
            disconnect()
    """
    global _client
    if _client:
        _client.close()
        _client = None


def ensure_indexes() -> None:
    """
    Create all required database indexes.
    
    Indexes optimize query performance for common patterns:
    - Unique constraint on test ID
    - Compound index for frequent filter combinations
    - Single-field indexes for individual filters
    - Compound index for result history queries
    - TTL index for automatic result cleanup (90 days)
    
    Called during:
        - Initial setup (scripts/verify_setup.py)
        - Migration (scripts/migrate_v1_to_v2.py)
        - Can be called multiple times (MongoDB ignores duplicates)
    
    Collections:
        - tests: Test definitions from roadmap 1-6
        - results: Execution history with auto-cleanup
        
    Performance Impact:
        - Index creation is fast for small collections
        - Does not block queries (background index creation)
    """
    db = get_db()

    # ─── Tests Collection Indexes ────────────────────────────────────

    # Unique constraint: prevent duplicate test IDs
    db["tests"].create_index("id", unique=True)

    # Compound index: most common query pattern (filters + status)
    db["tests"].create_index([("domain", 1), ("priority", 1), ("status", 1)])

    # Individual field indexes (Roadmap 6 — Registry fields)
    db["tests"].create_index("repo")
    db["tests"].create_index("layer")
    db["tests"].create_index("author")
    db["tests"].create_index("group")
    db["tests"].create_index("runner")

    # ─── Results Collection Indexes ──────────────────────────────────

    # Compound index: find latest results for a test, ordered by time
    db["results"].create_index([("test_id", 1), ("executed_at", -1)])

    # Single index: filter results by repository
    db["results"].create_index("repo")

    # TTL index: auto-delete results older than 90 days
    # Required due to Atlas M0 tier 512MB storage limit
    # Results older than 90 days are automatically purged by MongoDB
    db["results"].create_index(
        "executed_at",
        expireAfterSeconds=90 * 24 * 3600,  # 90 days in seconds
    )
