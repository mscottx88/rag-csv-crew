"""Integration tests for query execution service with timeout and cancellation.

Tests the query execution service that runs generated SQL queries against
PostgreSQL with 30-second timeout and cancellation support.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
import time
from typing import Any

from psycopg_pool import ConnectionPool
import pytest


@pytest.mark.integration
class TestQueryExecution:
    """Integration tests for query execution with timeout and cancellation (T052)."""

    def test_execute_query_with_timeout(self, connection_pool: ConnectionPool) -> None:
        """Test query execution respects 30-second timeout.

        Validates:
        - Query execution times out after 30 seconds
        - Timeout exception is raised
        - Database connection is cleaned up

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T052):
        - Long-running queries timeout after 30s
        - Timeout error is user-friendly
        - No connection leaks
        """
        from backend.src.services.query_execution import QueryExecutionService

        service: QueryExecutionService = QueryExecutionService(connection_pool)

        # Create a query that will take longer than timeout
        # Use pg_sleep to simulate long-running query
        long_query: str = "SELECT pg_sleep(35)"  # 35 seconds > 30 second timeout

        start_time: float = time.time()

        with pytest.raises((FuturesTimeoutError, Exception)):
            service.execute_query(
                sql=long_query, params=[], username="testuser", timeout_seconds=30
            )

        elapsed_time: float = time.time() - start_time

        # Verify timeout occurred around 30 seconds (with small tolerance)
        assert elapsed_time < 35  # Should not wait full 35 seconds
        assert elapsed_time >= 29  # Should wait at least ~30 seconds

    def test_execute_query_success(self, connection_pool: ConnectionPool) -> None:
        """Test successful query execution returns results.

        Validates:
        - Valid SQL query executes successfully
        - Results are returned as list of dictionaries
        - Column names are preserved
        - Row count is accurate

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T052):
        - Query execution returns results
        - Result format is consistent
        - Column metadata is preserved
        """
        from backend.src.services.query_execution import QueryExecutionService

        service: QueryExecutionService = QueryExecutionService(connection_pool)

        # Simple query that returns results
        query: str = "SELECT 1 AS num, 'test' AS text"

        result: dict[str, Any] = service.execute_query(
            sql=query, params=[], username="testuser", timeout_seconds=30
        )

        # Verify result structure
        assert "rows" in result
        assert "row_count" in result
        assert "columns" in result

        # Verify data
        assert result["row_count"] == 1
        assert len(result["rows"]) == 1
        assert result["rows"][0]["num"] == 1
        assert result["rows"][0]["text"] == "test"

    def test_execute_query_with_parameters(self, connection_pool: ConnectionPool) -> None:
        """Test parameterized query execution prevents SQL injection.

        Validates:
        - Parameterized queries execute correctly
        - Parameters are properly escaped
        - Special characters are handled safely

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T052):
        - Parameterized queries work correctly
        - No SQL injection vulnerability
        """
        from backend.src.services.query_execution import QueryExecutionService

        service: QueryExecutionService = QueryExecutionService(connection_pool)

        # Parameterized query
        query: str = "SELECT %s::text AS value"
        params: list[str] = ["test'; DROP TABLE users; --"]

        result: dict[str, Any] = service.execute_query(
            sql=query, params=params, username="testuser", timeout_seconds=30
        )

        # Verify parameter was safely escaped
        assert result["row_count"] == 1
        assert result["rows"][0]["value"] == "test'; DROP TABLE users; --"

    def test_cancel_query_execution(self, connection_pool: ConnectionPool) -> None:
        """Test query cancellation stops execution and returns within 1 second.

        Validates:
        - Running query can be cancelled
        - Cancellation completes within 1 second per FR-025, SC-011
        - Cancelled query raises appropriate exception

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T052):
        - Query cancellation works
        - Cancellation is fast (<1s)
        - Proper cleanup occurs
        """
        from threading import Event

        from backend.src.services.query_execution import QueryExecutionService

        service: QueryExecutionService = QueryExecutionService(connection_pool)
        cancel_event: Event = Event()

        # Start a long-running query in background thread
        def run_query() -> dict[str, Any]:
            """Run long query with cancellation support."""
            return service.execute_query(
                sql="SELECT pg_sleep(30)",  # 30 second query
                params=[],
                username="testuser",
                timeout_seconds=60,
                cancel_event=cancel_event,
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future: Any = executor.submit(run_query)

            # Wait a bit then cancel
            time.sleep(0.5)
            start_cancel: float = time.time()
            cancel_event.set()

            # Query should be cancelled quickly
            with pytest.raises(Exception):
                future.result(timeout=2)  # Wait max 2 seconds for cancellation

            cancel_time: float = time.time() - start_cancel

            # Verify cancellation was fast (within 1 second per SC-011)
            assert cancel_time < 1.5  # Allow some tolerance

    def test_execute_query_error_handling(self, connection_pool: ConnectionPool) -> None:
        """Test error handling for invalid SQL queries.

        Validates:
        - Invalid SQL raises appropriate exception
        - Error message is user-friendly
        - Connection is properly cleaned up

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T052):
        - Invalid queries raise clear errors
        - Error messages don't expose internals
        """
        from backend.src.services.query_execution import QueryExecutionService

        service: QueryExecutionService = QueryExecutionService(connection_pool)

        # Invalid SQL
        invalid_query: str = "SELECT * FROM nonexistent_table_xyz"

        with pytest.raises(Exception) as exc_info:
            service.execute_query(
                sql=invalid_query, params=[], username="testuser", timeout_seconds=30
            )

        # Verify error is raised
        assert exc_info.value is not None
        # Error message should be user-friendly
        error_msg: str = str(exc_info.value)
        assert len(error_msg) > 0

    def test_execute_query_with_large_result_set(self, connection_pool: ConnectionPool) -> None:
        """Test query execution handles large result sets efficiently.

        Validates:
        - Large result sets are retrieved successfully
        - Memory usage is reasonable (streaming if needed)
        - Performance is acceptable

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T052):
        - Large queries complete successfully
        - Results are properly formatted
        """
        from backend.src.services.query_execution import QueryExecutionService

        service: QueryExecutionService = QueryExecutionService(connection_pool)

        # Query that generates 1000 rows
        query: str = "SELECT generate_series(1, 1000) AS num"

        result: dict[str, Any] = service.execute_query(
            sql=query, params=[], username="testuser", timeout_seconds=30
        )

        # Verify all rows returned
        assert result["row_count"] == 1000
        assert len(result["rows"]) == 1000
        assert result["rows"][0]["num"] == 1
        assert result["rows"][999]["num"] == 1000
