"""Database connection retry logic with exponential backoff.

Implements FR-023: 3-retry connection loss recovery with exponential backoff
and user notification.

Constitutional Requirements:
- Thread-based operations only (uses time.sleep, not asyncio)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from collections.abc import Callable
import logging
import time
from typing import TypeVar

from psycopg import OperationalError

logger: logging.Logger = logging.getLogger(__name__)

# Type variable for return type of retryable function
# pylint: disable=invalid-name,redefined-outer-name
T = TypeVar("T")


def retry_with_backoff(
    operation: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> T:
    """Retry an operation with exponential backoff on connection failures.

    Implements FR-023 retry logic:
    - Retries on OperationalError only (connection failures)
    - Exponential backoff delays: 1s, 2s, 4s (for max_retries=3)
    - User notification: "Reconnecting..." printed before each retry
    - Other exceptions propagate immediately without retry

    Args:
        operation: Callable to execute (no arguments)
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for each retry delay (default: 2.0)

    Returns:
        Result of successful operation execution

    Raises:
        OperationalError: If all retry attempts exhausted
        RuntimeError: If retry loop exits unexpectedly
        Exception: Other exceptions propagated immediately without retry

    Example:
        >>> def connect_to_db() -> Connection:
        ...     return psycopg.connect(conninfo)
        >>> conn = retry_with_backoff(connect_to_db, max_retries=3)
    """
    attempt: int = 0
    delay: float = initial_delay

    while True:
        try:
            attempt += 1
            result: T = operation()
            logger.info(
                "Operation succeeded",
                extra={"attempt": attempt, "max_retries": max_retries},
            )
            return result

        except OperationalError as e:
            # Log the failure
            logger.warning(
                "Operation failed, checking retry policy",
                extra={
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error": str(e),
                },
            )

            # Check if we've exhausted all attempts
            if attempt >= max_retries:
                # Apply final backoff delay before giving up (per FR-023)
                if max_retries > 0:
                    time.sleep(delay)

                # Log final failure and re-raise
                logger.error(
                    "Operation failed after all retry attempts",
                    extra={
                        "attempt": attempt,
                        "max_retries": max_retries,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

            # Retry with backoff - user notification per FR-023
            print(f"Reconnecting... (attempt {attempt + 1}/{max_retries})")

            # Exponential backoff delay
            time.sleep(delay)
            delay *= backoff_factor

        except Exception as e:
            # Non-retryable exception - log and propagate immediately
            logger.error(
                "Non-retryable error in operation",
                extra={
                    "attempt": attempt,
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise


def retry_connection(
    connect_fn: Callable[[], T],
    context: str = "database",
) -> T:
    """Convenience wrapper for retrying database connections.

    Uses default FR-023 retry parameters (3 retries, 1s/2s/4s delays).

    Args:
        connect_fn: Function that returns a database connection
        context: Description of connection for logging (default: "database")

    Returns:
        Database connection or result

    Raises:
        OperationalError: If connection fails after all retries
    """
    logger.info("Attempting %s connection with retry", context)

    try:
        return retry_with_backoff(
            operation=connect_fn,
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
        )
    except OperationalError:
        logger.error("Failed to connect to %s after all retries", context)
        raise
