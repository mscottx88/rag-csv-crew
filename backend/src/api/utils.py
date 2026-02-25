"""Common utility functions for API route handlers.

Provides reusable patterns for error handling, database connection management,
and logging to reduce code duplication across route handlers.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import logging
from typing import Any

from fastapi import HTTPException, status

from backend.src.db.connection import DatabaseConnectionPool, get_global_pool
from backend.src.utils.logging import log_event


def get_pool_with_error_handling(
    logger: logging.Logger, event_name: str, user: str | None = None
) -> DatabaseConnectionPool:
    """Get global database connection pool with standard error handling.

    Args:
        logger: Logger instance for error logging
        event_name: Event name for logging (e.g., "login_failed", "upload_failed")
        user: Optional username for logging context

    Returns:
        DatabaseConnectionPool instance

    Raises:
        HTTPException: 500 Internal Server Error if pool not initialized

    Example:
        ```python
        pool: DatabaseConnectionPool = get_pool_with_error_handling(
            logger=logger,
            event_name="login_failed",
            user=username
        )
        ```
    """
    try:
        pool: DatabaseConnectionPool = get_global_pool()
        return pool
    except RuntimeError as e:
        log_kwargs: dict[str, Any] = {
            "logger": logger,
            "level": "error",
            "event": event_name,
            "extra": {"error": "Database pool not initialized"},
        }
        if user:
            log_kwargs["user"] = user
        log_event(**log_kwargs)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection unavailable",
        ) from e


def handle_http_exception_or_generic(
    exc: Exception,
    logger: logging.Logger,
    event_name: str,
    default_status_code: int,
    default_detail: str,
) -> HTTPException:
    """Handle exception with proper logging, preserving HTTPException or wrapping generic exceptions.  # pylint: disable=line-too-long

    Args:
        exc: Exception that was raised
        logger: Logger instance for error logging
        event_name: Event name for logging
        default_status_code: HTTP status code to use for generic exceptions
        default_detail: Error detail message for generic exceptions

    Returns:
        HTTPException to be raised

    Example:
        ```python
        except HTTPException:
            raise
        except Exception as e:
            raise handle_http_exception_or_generic(
                exc=e,
                logger=logger,
                event_name="operation_failed",
                default_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                default_detail="Operation failed",
            )
        ```
    """
    if isinstance(exc, HTTPException):
        return exc

    log_event(
        logger=logger,
        level="error",
        event=event_name,
        user=None,  # System event, no user context
        extra={"error": str(exc)},
    )
    return HTTPException(
        status_code=default_status_code,
        detail=default_detail,
    )
