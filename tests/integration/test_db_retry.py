"""Integration tests for database retry logic.

Tests exponential backoff retry mechanism per FR-023:
- 3 retry attempts
- Exponential backoff timing (1s, 2s, 4s delays)
- "Reconnecting..." notification to user

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import time

from psycopg import OperationalError
import pytest


@pytest.mark.integration
class TestDatabaseRetry:
    """Test database retry logic with exponential backoff."""

    def test_retry_on_connection_failure(self) -> None:
        """Test retry mechanism attempts 3 times with exponential backoff.

        Validates:
        - Retry attempts exactly 3 times on connection failure
        - Exponential backoff delays: 1s, 2s, 4s
        - Total execution time approximately 7 seconds (1+2+4)
        """
        attempt_count: int = 0
        attempt_times: list[float] = []

        def failing_operation() -> None:
            """Mock operation that always fails.

            Raises:
                OperationalError: Simulated connection failure
            """
            nonlocal attempt_count
            attempt_count += 1
            attempt_times.append(time.time())
            raise OperationalError("Connection failed")

        start_time: float = time.time()

        with pytest.raises(OperationalError):
            # Should retry 3 times then raise
            from backend.src.db.retry import retry_with_backoff

            retry_with_backoff(failing_operation, max_retries=3)

        end_time: float = time.time()
        elapsed: float = end_time - start_time

        # Verify 3 attempts made (initial + 2 retries)
        assert attempt_count == 3

        # Verify exponential backoff timing (approximately 1s + 2s + 4s = 7s)
        assert 6.5 < elapsed < 8.0, f"Expected ~7s, got {elapsed:.2f}s"

    def test_retry_succeeds_on_second_attempt(self) -> None:
        """Test successful retry after initial failure.

        Validates:
        - Operation succeeds if retry succeeds
        - No additional retries after success
        - Returns expected result
        """
        attempt_count: int = 0

        def eventually_succeeds() -> str:
            """Mock operation that succeeds on second attempt.

            Returns:
                Success message on second attempt

            Raises:
                OperationalError: On first attempt only
            """
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise OperationalError("Connection failed")
            return "success"

        from backend.src.db.retry import retry_with_backoff

        result: str = retry_with_backoff(eventually_succeeds, max_retries=3)

        assert result == "success"
        assert attempt_count == 2  # Initial + 1 retry

    def test_retry_with_reconnecting_notification(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test 'Reconnecting...' notification printed on retry.

        Validates:
        - User notification printed before each retry
        - Notification includes attempt number
        - Per FR-023 user feedback requirement

        Args:
            capsys: pytest fixture to capture stdout/stderr
        """
        attempt_count: int = 0

        def failing_operation() -> None:
            """Mock operation that always fails."""
            nonlocal attempt_count
            attempt_count += 1
            raise OperationalError("Connection failed")

        from backend.src.db.retry import retry_with_backoff

        with pytest.raises(OperationalError):
            retry_with_backoff(failing_operation, max_retries=3)

        captured: pytest.CaptureResult[str] = capsys.readouterr()
        # Should see 2 "Reconnecting..." messages (not on first attempt)
        assert captured.out.count("Reconnecting") == 2

    def test_no_retry_on_non_operational_error(self) -> None:
        """Test no retry for non-connection errors.

        Validates:
        - Only OperationalError triggers retry
        - Other exceptions propagate immediately
        - No retry delay for non-retryable errors
        """
        attempt_count: int = 0

        def raises_value_error() -> None:
            """Mock operation that raises non-retryable error."""
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Invalid input")

        from backend.src.db.retry import retry_with_backoff

        start_time: float = time.time()

        with pytest.raises(ValueError):
            retry_with_backoff(raises_value_error, max_retries=3)

        elapsed: float = time.time() - start_time

        # Should fail immediately without retry
        assert attempt_count == 1
        assert elapsed < 0.5  # No backoff delay

    def test_configurable_max_retries(self) -> None:
        """Test retry logic respects max_retries parameter.

        Validates:
        - max_retries=0 means no retries (fail immediately)
        - max_retries=5 attempts exactly 5 times
        """
        # Test with max_retries=0
        attempt_count_0: int = 0

        def always_fails_0() -> None:
            """Mock operation for zero retries test."""
            nonlocal attempt_count_0
            attempt_count_0 += 1
            raise OperationalError("Connection failed")

        from backend.src.db.retry import retry_with_backoff

        with pytest.raises(OperationalError):
            retry_with_backoff(always_fails_0, max_retries=0)

        assert attempt_count_0 == 1  # Initial attempt only

        # Test with max_retries=5
        attempt_count_5: int = 0

        def always_fails_5() -> None:
            """Mock operation for five retries test."""
            nonlocal attempt_count_5
            attempt_count_5 += 1
            raise OperationalError("Connection failed")

        with pytest.raises(OperationalError):
            retry_with_backoff(always_fails_5, max_retries=5)

        assert attempt_count_5 == 5  # Initial + 4 retries
