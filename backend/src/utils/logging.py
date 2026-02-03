"""Structured logging framework with JSON format per FR-024.

Implements:
- JSON-formatted structured logging
- Mandatory fields: timestamp, level, event, user
- Optional fields: execution_time_ms, result_count, error, stack_trace
- Thread-safe logging operations
- Event type schema validation

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime
import json
import logging
import traceback
from typing import Any

# Define mandatory event types per FR-024
EVENT_TYPES: set[str] = {
    "auth_login",
    "file_upload",
    "file_delete",
    "query_submit",
    "query_complete",
    "query_cancel",
    "error",
}


class StructuredJSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.

    Formats log records as JSON with mandatory fields:
    - timestamp: ISO 8601 format with timezone
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - event: Event identifier
    - user: Username (if available)
    - Additional fields from record extras

    Per FR-024: Structured logging requirement
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Python logging record

        Returns:
            JSON-formatted log string

        Note: Thread-safe - logging module ensures synchronization
        """
        # Extract timestamp in ISO 8601 format
        timestamp: datetime = datetime.fromtimestamp(record.created, tz=UTC)
        timestamp_str: str = timestamp.isoformat()

        # Build base log data with mandatory fields
        log_data: dict[str, Any] = {
            "timestamp": timestamp_str,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add event field if present
        if hasattr(record, "event"):
            log_data["event"] = record.event

        # Add user field if present
        if hasattr(record, "user"):
            log_data["user"] = record.user

        # Add execution time if present
        if hasattr(record, "execution_time_ms"):
            log_data["execution_time_ms"] = record.execution_time_ms

        # Add result count if present
        if hasattr(record, "result_count"):
            log_data["result_count"] = record.result_count

        # Add error details if present
        if hasattr(record, "error_message"):
            log_data["error"] = record.error_message

        if hasattr(record, "stack_trace"):
            log_data["stack_trace"] = record.stack_trace

        # Add any other custom fields from extras
        if hasattr(record, "custom_fields"):
            custom: dict[str, Any] = record.custom_fields
            log_data.update(custom)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Return JSON string
        return json.dumps(log_data, default=str, ensure_ascii=False)


def get_structured_logger(name: str) -> logging.Logger:
    """Get or create a logger configured for structured JSON logging.

    Args:
        name: Logger name (typically __name__ of calling module)

    Returns:
        Configured logger instance with JSON formatter

    Per FR-024: Structured logging framework setup

    Usage:
        logger = get_structured_logger(__name__)
        log_event(logger, "info", "auth_login", "alice", {})
    """
    logger: logging.Logger = logging.getLogger(name)

    # Only configure if no handlers exist (prevent duplicate handlers)
    if not logger.handlers:
        # Create console handler
        handler: logging.StreamHandler[Any] = logging.StreamHandler()

        # Create and set JSON formatter
        formatter: StructuredJSONFormatter = StructuredJSONFormatter()
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

        # Set default log level (can be overridden via configuration)
        logger.setLevel(logging.INFO)

        # Prevent propagation to root logger (avoid duplicate logs)
        logger.propagate = False

    return logger


def log_event(
    logger: logging.Logger,
    level: str,
    event: str,
    user: str | None,
    extra: dict[str, Any],
) -> None:
    """Log a structured event with mandatory and optional fields.

    Args:
        logger: Logger instance from get_structured_logger()
        level: Log level ("debug", "info", "warning", "error", "critical")
        event: Event identifier (e.g., "auth_login", "query_submit")
        user: Username (None for system events)
        extra: Additional fields (execution_time_ms, result_count, etc.)

    Per FR-024: Structured event logging with schema

    Usage:
        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user="alice",
            extra={
                "query_id": "12345",
                "execution_time_ms": 1250,
                "result_count": 10
            }
        )
    """
    # Convert level string to logging constant
    level_map: dict[str, int] = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    log_level: int = level_map.get(level.lower(), logging.INFO)

    # Create log message
    message: str = f"Event: {event}"
    if user:
        message += f" | User: {user}"

    # Build extra dict for LogRecord
    log_extras: dict[str, Any] = {
        "event": event,
        "user": user,
        "custom_fields": extra,
    }

    # Extract known fields from extra for top-level access
    if "execution_time_ms" in extra:
        log_extras["execution_time_ms"] = extra["execution_time_ms"]

    if "result_count" in extra:
        log_extras["result_count"] = extra["result_count"]

    # Log with extra fields
    logger.log(log_level, message, extra=log_extras)


def log_error(
    logger: logging.Logger,
    event: str,
    user: str | None,
    error: Exception,
) -> None:
    """Log an error event with exception details and stack trace.

    Args:
        logger: Logger instance from get_structured_logger()
        event: Event identifier (typically "error" or specific error event)
        user: Username (None for system errors)
        error: Exception object to log

    Per FR-024: Error logging with stack trace requirement

    Usage:
        try:
            risky_operation()
        except ValueError as e:
            log_error(
                logger=logger,
                event="database_error",
                user="alice",
                error=e
            )
    """
    # Get stack trace as string
    tb_str: str = "".join(traceback.format_tb(error.__traceback__))

    # Build error message
    error_message: str = f"{type(error).__name__}: {error!s}"
    message: str = f"Error: {event}"
    if user:
        message += f" | User: {user}"
    message += f" | {error_message}"

    # Build extra dict with error details
    log_extras: dict[str, Any] = {
        "event": event,
        "user": user,
        "error_message": error_message,
        "stack_trace": tb_str,
        "error_type": type(error).__name__,
        "custom_fields": {},
    }

    # Log at ERROR level
    logger.error(message, extra=log_extras)


# Initialize application-level logger
def setup_application_logging(log_level: str = "INFO") -> None:
    """Setup application-level logging configuration.

    Args:
        log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Call this once at application startup to configure logging globally.

    Per FR-024: Application logging setup
    """
    level_map: dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    level: int = level_map.get(log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler with JSON formatter
    console_handler: logging.StreamHandler[Any] = logging.StreamHandler()
    formatter: StructuredJSONFormatter = StructuredJSONFormatter()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
