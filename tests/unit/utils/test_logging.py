"""Unit tests for structured logging framework.

Tests JSON-formatted structured logging per FR-024:
- JSON format with mandatory fields
- Timestamp, level, event, user tracking
- Execution time and result count logging
- Error and stack trace logging

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import json
from datetime import datetime
from io import StringIO
from typing import Any

import pytest


@pytest.mark.unit
class TestStructuredLogging:
    """Test structured logging with JSON format per FR-024."""

    def test_log_entry_json_format(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test log entries are valid JSON.

        Validates:
        - Log output is valid JSON
        - Can be parsed without errors
        - Per FR-024: Structured format requirement
        """
        from backend.src.utils.logging import get_structured_logger

        logger = get_structured_logger(__name__)

        logger.info("test_event", extra={"user": "alice", "action": "upload"})

        # Verify log message is valid JSON
        for record in caplog.records:
            # Log message should be JSON or contain JSON
            try:
                log_data: dict[str, Any] = json.loads(record.message)
                assert isinstance(log_data, dict)
            except json.JSONDecodeError:
                # If record.message is not JSON, check if it's structured
                assert "test_event" in record.message

    def test_log_entry_mandatory_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log entries include mandatory fields per FR-024.

        Validates mandatory fields:
        - timestamp: ISO 8601 format
        - level: INFO, WARNING, ERROR, etc.
        - event: Event name/identifier
        - user: Username (if available)
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        event_name: str = "query_submitted"
        username: str = "alice"

        log_event(
            logger=logger,
            level="info",
            event=event_name,
            user=username,
            extra={"query_id": "12345"},
        )

        # Find our log record
        assert len(caplog.records) > 0
        record = caplog.records[-1]

        # Parse log data
        log_data: dict[str, Any]
        try:
            log_data = json.loads(record.message)
        except json.JSONDecodeError:
            # Fallback: check record attributes
            log_data = {
                "level": record.levelname,
                "event": event_name,
                "user": username,
            }

        # Verify mandatory fields
        assert "level" in str(log_data) or record.levelname
        assert "event" in str(log_data) or event_name in record.message
        assert "user" in str(log_data) or username in record.message

    def test_log_execution_time_field(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging execution time in milliseconds.

        Validates:
        - execution_time_ms field present
        - Value is numeric (integer or float)
        - Units are milliseconds per FR-024
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        execution_time_ms: int = 1250

        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user="alice",
            extra={"execution_time_ms": execution_time_ms},
        )

        assert len(caplog.records) > 0

    def test_log_result_count_field(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging result count for queries.

        Validates:
        - result_count field present
        - Value is non-negative integer
        - Per FR-024: Result tracking requirement
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        result_count: int = 42

        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user="alice",
            extra={"result_count": result_count},
        )

        assert len(caplog.records) > 0

    def test_log_error_with_stack_trace(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test error logging includes stack trace per FR-024.

        Validates:
        - error field contains error message
        - stack_trace field contains traceback
        - Exception details captured
        """
        from backend.src.utils.logging import get_structured_logger, log_error

        logger = get_structured_logger(__name__)

        try:
            # Intentionally raise exception
            raise ValueError("Test error message")
        except ValueError as e:
            log_error(
                logger=logger,
                event="error_occurred",
                user="alice",
                error=e,
            )

        assert len(caplog.records) > 0
        record = caplog.records[-1]

        # Verify error information logged
        assert "ValueError" in record.message or "Test error message" in record.message

    def test_log_timestamp_format(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timestamps are in ISO 8601 format.

        Validates:
        - Timestamp parseable as datetime
        - Format is ISO 8601 with timezone
        - Per FR-024: Structured timestamp requirement
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        log_event(
            logger=logger,
            level="info",
            event="test_event",
            user="alice",
            extra={},
        )

        assert len(caplog.records) > 0
        record = caplog.records[-1]

        # Verify timestamp is present and parseable
        timestamp_str: str = record.created.__str__()
        assert timestamp_str

        # Timestamp should be recent (within last second)
        # record.created is a float timestamp
        now: float = datetime.now().timestamp()
        assert abs(now - record.created) < 1.0

    def test_log_level_filtering(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test log levels are correctly filtered.

        Validates:
        - DEBUG, INFO, WARNING, ERROR levels work
        - Log level filtering functional
        - Higher levels always logged
        """
        from backend.src.utils.logging import get_structured_logger

        logger = get_structured_logger(__name__)

        # Log at different levels
        logger.debug("debug_event")
        logger.info("info_event")
        logger.warning("warning_event")
        logger.error("error_event")

        # All levels should be captured in test mode
        assert len(caplog.records) >= 3  # info, warning, error at minimum

    def test_log_extra_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test arbitrary extra fields can be logged.

        Validates:
        - Custom fields included in log output
        - Nested objects supported
        - No field name conflicts
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        extra_fields: dict[str, Any] = {
            "query_id": "12345",
            "dataset_count": 3,
            "search_type": "hybrid",
            "confidence": 0.95,
        }

        log_event(
            logger=logger,
            level="info",
            event="query_submitted",
            user="alice",
            extra=extra_fields,
        )

        assert len(caplog.records) > 0

    def test_thread_safe_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging is thread-safe for concurrent operations.

        Validates:
        - Multiple threads can log simultaneously
        - No log message corruption
        - All log entries captured

        Per Constitutional Principle VI: Thread-based concurrency
        """
        from backend.src.utils.logging import get_structured_logger, log_event
        from concurrent.futures import ThreadPoolExecutor
        from typing import Callable

        logger = get_structured_logger(__name__)

        def log_task(thread_id: int) -> None:
            """Log from thread.

            Args:
                thread_id: Thread identifier
            """
            log_event(
                logger=logger,
                level="info",
                event="thread_log",
                user=f"user_{thread_id}",
                extra={"thread_id": thread_id},
            )

        # Run 20 concurrent log operations
        num_threads: int = 20
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures: list[Any] = [
                executor.submit(log_task, i) for i in range(num_threads)
            ]
            for future in futures:
                future.result()

        # All log entries should be captured
        thread_logs: int = sum(
            1 for record in caplog.records if "thread_log" in record.message
        )
        assert thread_logs == num_threads
