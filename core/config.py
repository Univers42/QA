"""
Configuration and environment validation.

Centralizes all environment variable handling and boot-time validation.
Follows 12-factor app methodology: config external to code.

Usage:
    from core.config import Settings
    
    # At application startup
    Settings.validate()
    
    # Access values
    db_uri = Settings.MONGO_URI
    user = Settings.PQA_USER
"""

import os
from typing import Optional


class Settings:
    """
    Application settings from environment variables.
    
    All configuration is loaded from environment at class instantiation time.
    Use Settings.validate() at app startup to fail fast on missing config.
    """

    # ─── Database Configuration ───────────────────────────────────────
    MONGO_URI: str = os.getenv("MONGO_URI_ATLAS", "")
    """MongoDB Atlas connection string. Required for all database operations."""

    # ─── User Context ────────────────────────────────────────────────
    PQA_USER: Optional[str] = os.getenv("PQA_USER")
    """Current user identifier. Used by CLI for --mine flag and audit trail."""

    # ─── Logging Configuration ────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    """Log level: DEBUG, INFO, WARNING, ERROR. Default: INFO"""

    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
    """Log format: json or text. Default: json (better for prod parsing)"""

    # ─── Execution Configuration ──────────────────────────────────────
    DEFAULT_TIMEOUT_SECONDS: int = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "30"))
    """Default timeout for test execution in seconds. Can be overridden per test."""

    GIT_COMMIT_ON_CHANGES: bool = os.getenv("GIT_COMMIT_ON_CHANGES", "true").lower() == "true"
    """Whether to auto-commit changes after add/edit/delete. Default: true"""

    # ─── Feature Flags ────────────────────────────────────────────────
    ENABLE_WEBSOCKET_STREAMING: bool = os.getenv("ENABLE_WEBSOCKET_STREAMING", "true").lower() == "true"
    """Enable WebSocket streaming for test results. Default: true"""

    @staticmethod
    def validate() -> None:
        """
        Validate required configuration at application startup.
        
        Raises:
            ValueError: If required configuration is missing.
            
        Usage:
            At application startup (main.py, cli/main.py):
                Settings.validate()
        """
        errors = []

        # Required: Database connection
        if not Settings.MONGO_URI:
            errors.append("MONGO_URI_ATLAS environment variable must be set")

        if errors:
            error_msg = "\n  ".join(["Configuration Error:"] + errors)
            raise ValueError(error_msg)

    @staticmethod
    def summary() -> dict:
        """
        Return current configuration as dict (for logging/debugging).
        
        Sensitive values (passwords, tokens) are masked.
        """
        return {
            "mongo_uri": "***" if Settings.MONGO_URI else "NOT_SET",
            "pqa_user": Settings.PQA_USER or "NOT_SET",
            "log_level": Settings.LOG_LEVEL,
            "log_format": Settings.LOG_FORMAT,
            "default_timeout_seconds": Settings.DEFAULT_TIMEOUT_SECONDS,
            "git_commit_on_changes": Settings.GIT_COMMIT_ON_CHANGES,
            "enable_websocket_streaming": Settings.ENABLE_WEBSOCKET_STREAMING,
        }
