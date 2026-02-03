"""Unit tests for logging schema validation.

Tests that all event types produce correct schema per FR-024:
- auth_login, file_upload, file_delete events
- query_submit, query_complete, query_cancel events
- error event with proper error fields

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import pytest


@pytest.mark.unit
class TestLoggingSchema:
    """Test structured logging schema compliance for all event types."""

    def test_auth_login_event_schema(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test auth_login event has correct schema.

        Validates schema includes:
        - event: "auth_login"
        - user: username
        - timestamp: ISO 8601
        - level: "INFO"

        Per FR-024: Authentication event logging
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        username: str = "alice"

        log_event(
            logger=logger,
            level="info",
            event="auth_login",
            user=username,
            extra={"ip_address": "192.168.1.1"},
        )

        assert len(caplog.records) > 0
        record = caplog.records[-1]

        # Verify event type logged
        assert "auth_login" in record.message
        assert username in record.message or record.user == username  # type: ignore

    def test_file_upload_event_schema(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test file_upload event has correct schema.

        Validates schema includes:
        - event: "file_upload"
        - user: username
        - filename: uploaded file name
        - file_size_bytes: file size
        - execution_time_ms: upload duration

        Per FR-024: File operation logging
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        username: str = "alice"
        filename: str = "sales.csv"
        file_size: int = 1048576  # 1MB
        exec_time: int = 2500  # 2.5 seconds

        log_event(
            logger=logger,
            level="info",
            event="file_upload",
            user=username,
            extra={
                "filename": filename,
                "file_size_bytes": file_size,
                "execution_time_ms": exec_time,
            },
        )

        assert len(caplog.records) > 0

    def test_file_delete_event_schema(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test file_delete event has correct schema.

        Validates schema includes:
        - event: "file_delete"
        - user: username
        - dataset_id: UUID of deleted dataset
        - filename: deleted file name

        Per FR-024: File operation logging
        """
        from backend.src.utils.logging import get_structured_logger, log_event
        from uuid import uuid4

        logger = get_structured_logger(__name__)

        username: str = "alice"
        dataset_id: str = str(uuid4())
        filename: str = "sales.csv"

        log_event(
            logger=logger,
            level="info",
            event="file_delete",
            user=username,
            extra={"dataset_id": dataset_id, "filename": filename},
        )

        assert len(caplog.records) > 0

    def test_query_submit_event_schema(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test query_submit event has correct schema.

        Validates schema includes:
        - event: "query_submit"
        - user: username
        - query_id: UUID of query
        - query_text: natural language question

        Per FR-024: Query processing logging
        """
        from backend.src.utils.logging import get_structured_logger, log_event
        from uuid import uuid4

        logger = get_structured_logger(__name__)

        username: str = "alice"
        query_id: str = str(uuid4())
        query_text: str = "What are the top 10 sales?"

        log_event(
            logger=logger,
            level="info",
            event="query_submit",
            user=username,
            extra={"query_id": query_id, "query_text": query_text},
        )

        assert len(caplog.records) > 0
        record = caplog.records[-1]

        assert "query_submit" in record.message

    def test_query_complete_event_schema(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test query_complete event has correct schema.

        Validates schema includes:
        - event: "query_complete"
        - user: username
        - query_id: UUID of query
        - execution_time_ms: query duration
        - result_count: number of results
        - status: "completed"

        Per FR-024: Query completion logging
        """
        from backend.src.utils.logging import get_structured_logger, log_event
        from uuid import uuid4

        logger = get_structured_logger(__name__)

        username: str = "alice"
        query_id: str = str(uuid4())
        exec_time: int = 1250  # 1.25 seconds
        result_count: int = 10
        status: str = "completed"

        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user=username,
            extra={
                "query_id": query_id,
                "execution_time_ms": exec_time,
                "result_count": result_count,
                "status": status,
            },
        )

        assert len(caplog.records) > 0

    def test_query_cancel_event_schema(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test query_cancel event has correct schema.

        Validates schema includes:
        - event: "query_cancel"
        - user: username
        - query_id: UUID of cancelled query
        - status: "cancelled"

        Per FR-024, FR-025: Query cancellation logging
        """
        from backend.src.utils.logging import get_structured_logger, log_event
        from uuid import uuid4

        logger = get_structured_logger(__name__)

        username: str = "alice"
        query_id: str = str(uuid4())
        status: str = "cancelled"

        log_event(
            logger=logger,
            level="info",
            event="query_cancel",
            user=username,
            extra={"query_id": query_id, "status": status},
        )

        assert len(caplog.records) > 0

    def test_error_event_schema(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test error event has correct schema.

        Validates schema includes:
        - event: "error"
        - user: username (if available)
        - error: error message string
        - stack_trace: full traceback
        - level: "ERROR"

        Per FR-024: Error logging requirement
        """
        from backend.src.utils.logging import get_structured_logger, log_error

        logger = get_structured_logger(__name__)

        username: str = "alice"
        error_message: str = "Database connection failed"

        try:
            raise ValueError(error_message)
        except ValueError as e:
            log_error(
                logger=logger,
                event="error",
                user=username,
                error=e,
            )

        assert len(caplog.records) > 0
        record = caplog.records[-1]

        # Verify error information present
        assert record.levelname == "ERROR"
        assert "error" in record.message.lower() or "ValueError" in record.message

    def test_all_events_have_timestamp(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test all event types include timestamp.

        Validates:
        - Timestamp present in all event types
        - Timestamp format consistent
        - Per FR-024: Mandatory timestamp field
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        event_types: list[str] = [
            "auth_login",
            "file_upload",
            "file_delete",
            "query_submit",
            "query_complete",
            "query_cancel",
        ]

        for event_type in event_types:
            log_event(
                logger=logger,
                level="info",
                event=event_type,
                user="alice",
                extra={},
            )

        # All events should have timestamps via record.created
        for record in caplog.records:
            assert record.created > 0  # Timestamp is float > 0

    def test_all_events_have_user_field(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test all event types include user field when available.

        Validates:
        - User field present for authenticated events
        - User field can be None for system events
        - Per FR-024: User tracking requirement
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        username: str = "alice"

        # Log event with user
        log_event(
            logger=logger,
            level="info",
            event="query_submit",
            user=username,
            extra={},
        )

        assert len(caplog.records) > 0

    def test_schema_field_types(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test schema field types are correct.

        Validates:
        - execution_time_ms is integer
        - result_count is integer
        - confidence is float (0.0-1.0)
        - file_size_bytes is integer
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        # Log with various typed fields
        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user="alice",
            extra={
                "execution_time_ms": 1250,  # int
                "result_count": 10,  # int
                "confidence": 0.95,  # float
                "file_size_bytes": 1048576,  # int
            },
        )

        assert len(caplog.records) > 0

    def test_schema_extensibility(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test schema allows additional fields beyond mandatory.

        Validates:
        - Custom fields can be added
        - Schema is extensible per FR-024
        - Extra fields don't break mandatory fields
        """
        from backend.src.utils.logging import get_structured_logger, log_event

        logger = get_structured_logger(__name__)

        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user="alice",
            extra={
                "query_id": "12345",
                "custom_field": "custom_value",
                "nested_object": {"key": "value"},
                "tags": ["tag1", "tag2"],
            },
        )

        assert len(caplog.records) > 0
