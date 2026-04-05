"""
Structured logging configuration.

Provides centralized, production-ready logging throughout the application.
Supports both JSON (for cloud/production) and text (for local development) formats.

Key Benefits:
- Consistent log format across modules (API, CLI, runner)
- Structured fields enable easy searching/filtering in production
- Context tracking (request_id, test_id, etc.)
- Proper error capture with stack traces

Usage:
    from core.logging import get_logger
    
    # Get logger for a module
    logger = get_logger(__name__)
    
    # Log levels
    logger.debug("setup", extra={"module": "auth"})
    logger.info("test_started", extra={"test_id": "AUTH-001"})
    logger.warning("timeout_exceeded", extra={"timeout_ms": 5000})
    logger.error("execution_failed", extra={"test_id": "AUTH-001", "error": str(e)})
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Optional

from core.config import Settings


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.
    
    Each log entry is a JSON object with:
    - timestamp: ISO 8601 datetime
    - level: Log level (DEBUG, INFO, WARNING, ERROR)
    - logger: Module/logger name
    - message: Main log message
    - extra: Additional context fields
    - exception: Stack trace (if error)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra fields from logger.info(..., extra={...})
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry.update(record.extra)

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter for local development.
    
    Format: [2024-04-05 14:30:45] INFO — logger_name → message (extra)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as readable text."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        # Build extra field string
        extra_str = ""
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            extra_items = [f"{k}={v}" for k, v in record.extra.items()]
            extra_str = f" ({', '.join(extra_items)})" if extra_items else ""

        message = record.getMessage()
        logger_name = record.name.split(".")[-1]  # Show only last component

        # Include exception if present
        exc_str = ""
        if record.exc_info:
            exc_str = f"\n{self.formatException(record.exc_info)}"

        return f"[{timestamp}] {level:7} — {logger_name:15} → {message}{extra_str}{exc_str}"


def _setup_logging(format_type: str = "json", level: str = "INFO") -> None:
    """
    Configure root logger for the application.
    
    Args:
        format_type: "json" for production or "text" for development
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper()))

    # Apply formatter
    if format_type == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str, extra: Optional[dict] = None) -> logging.LoggerAdapter:
    """
    Get a logger for a specific module.
    
    Args:
        name: Logger name (typically __name__ from calling module)
        extra: Default extra context for all logs from this logger
        
    Returns:
        LoggerAdapter: Logger with structured logging support
        
    Example:
        logger = get_logger("core.db")
        logger.info("connected", extra={"host": "cluster0.mongodb.net"})
    """
    logger = logging.getLogger(name)

    # Return adapter to support extra dict easily
    return logging.LoggerAdapter(logger, extra or {})


# ─── Export common helper functions ────────────────────────────────────

def setup_logging_from_config() -> None:
    """Set up logging based on Settings from core.config."""
    _setup_logging(
        format_type=Settings.LOG_FORMAT,
        level=Settings.LOG_LEVEL,
    )


# Initialize logging on module import
setup_logging_from_config()
