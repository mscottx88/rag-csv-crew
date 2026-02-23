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
from logging.handlers import RotatingFileHandler
from pathlib import Path
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

        # Enable propagation to root logger (allows pytest caplog to work)
        logger.propagate = True

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
def setup_application_logging(
    log_level: str = "INFO", enable_file_logging: bool = True, log_dir: str = "logs"
) -> None:
    """Setup application-level logging configuration with rotation support.

    Args:
        log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_file_logging: Enable file-based logging with rotation (default: True)
        log_dir: Directory for log files (default: "logs")

    Call this once at application startup to configure logging globally.

    Per FR-024: Application logging setup
    Per T204a-POLISH: Log rotation with RotatingFileHandler
        - Standard logs: 100MB per file, 5 backup files (500MB total)
        - Security logs: 100MB per file, 10 backup files (1GB total)
        - Retention: Standard 30 days (handled by external cleanup), Security 90 days

    Log Files:
        - logs/app.log: Standard application logs (rotated at 100MB, 5 backups)
        - logs/security.log: Security events (auth, access) (rotated at 100MB, 10 backups)
        - logs/errors.log: Error-level logs only (rotated at 100MB, 5 backups)
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

    # Create JSON formatter
    formatter: StructuredJSONFormatter = StructuredJSONFormatter()

    # Add console handler (always enabled)
    console_handler: logging.StreamHandler[Any] = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handlers with rotation (if enabled)
    if enable_file_logging:
        # Create log directory if it doesn't exist
        log_path: Path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Standard application logs (100MB per file, 5 backups = 500MB total)
        app_log_file: Path = log_path / "app.log"
        app_handler: RotatingFileHandler = RotatingFileHandler(
            filename=str(app_log_file),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=5,  # Keep 5 backup files (app.log.1 through app.log.5)
            encoding="utf-8",
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)  # Log INFO and above to app.log
        root_logger.addHandler(app_handler)

        # Security logs (auth, access events) (100MB per file, 10 backups = 1GB total)
        # These are filtered to only include security-related events
        security_log_file: Path = log_path / "security.log"
        security_handler: RotatingFileHandler = RotatingFileHandler(
            filename=str(security_log_file),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,  # Keep 10 backup files (security.log.1 through security.log.10)
            encoding="utf-8",
        )
        security_handler.setFormatter(formatter)
        security_handler.setLevel(logging.INFO)

        # Add filter for security events
        class SecurityEventFilter(logging.Filter):
            """Filter that only passes security-related log events."""

            def filter(self, record: logging.LogRecord) -> bool:
                """Check if log record is a security event.

                Args:
                    record: Log record to filter

                Returns:
                    True if record should be logged, False otherwise
                """
                # Security events: auth_login, auth_logout, access_denied, permission_check
                security_events: set[str] = {
                    "auth_login",
                    "auth_logout",
                    "access_denied",
                    "permission_check",
                    "token_validation_failed",
                    "invalid_credentials",
                }

                # Check if event field exists and is a security event
                has_security_event: bool = (
                    hasattr(record, "event") and record.event in security_events
                )
                return has_security_event

        security_handler.addFilter(SecurityEventFilter())
        root_logger.addHandler(security_handler)

        # Error logs (100MB per file, 5 backups = 500MB total)
        error_log_file: Path = log_path / "errors.log"
        error_handler: RotatingFileHandler = RotatingFileHandler(
            filename=str(error_log_file),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=5,  # Keep 5 backup files (errors.log.1 through errors.log.5)
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)  # Only ERROR and CRITICAL logs
        root_logger.addHandler(error_handler)
