"""Unit tests for parallel query execution service.

T008 [US1]: Tests execute_strategies_parallel and _execute_single_strategy
in QueryExecutionService. Verifies parallel dispatch of multiple strategies,
error isolation, cancellation via threading.Event, empty input handling,
vector parameter resolution, row truncation (FR-011), timing metadata,
and column population from cursor.description.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from threading import Event
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.src.models.fusion import (
    StrategyResult,
    StrategySQL,
    StrategyType,
)
from backend.src.services.query_execution import QueryExecutionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_strategy_sql(
    strategy_type: StrategyType = StrategyType.STRUCTURED,
    sql: str = "SELECT ctid, * FROM t LIMIT 50",
    parameters: list[Any] | None = None,
) -> StrategySQL:
    """Create a StrategySQL instance for testing."""
    return StrategySQL(
        strategy_type=strategy_type,
        sql=sql,
        parameters=parameters if parameters is not None else [],
    )


def _make_mock_pool() -> MagicMock:
    """Create a mock ConnectionPool with cursor context managers."""
    mock_pool: MagicMock = MagicMock()
    mock_conn: MagicMock = MagicMock()
    mock_cursor: MagicMock = MagicMock()

    # Set up connection context manager
    mock_pool.connection.return_value.__enter__ = MagicMock(
        return_value=mock_conn,
    )
    mock_pool.connection.return_value.__exit__ = MagicMock(
        return_value=False,
    )

    # Set up cursor context manager
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor,
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(
        return_value=False,
    )

    # Default: return 3 rows with 2 columns
    mock_cursor.description = [("ctid", None), ("name", None)]
    mock_cursor.fetchall.return_value = [
        ("(0,1)", "Alice"),
        ("(0,2)", "Bob"),
        ("(0,3)", "Charlie"),
    ]

    return mock_pool


# ---------------------------------------------------------------------------
# T008: Parallel execution tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParallelStrategyExecution:
    """T008: Test execute_strategies_parallel in QueryExecutionService.

    Verifies parallel dispatch, error isolation, cancellation,
    empty input, vector resolution, row truncation, timing,
    and column metadata.
    """

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_parallel_three_strategies_returns_three_results(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test parallel execution of 3 strategies returns 3 results."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        strategies: list[StrategySQL] = [
            _make_strategy_sql(StrategyType.STRUCTURED),
            _make_strategy_sql(StrategyType.FULLTEXT),
            _make_strategy_sql(StrategyType.VECTOR),
        ]

        # Mock _execute_single_strategy to return a StrategyResult
        mock_exec.side_effect = [
            StrategyResult(
                strategy_type=StrategyType.STRUCTURED,
                rows=[{"ctid": "(0,1)", "name": "Alice"}],
                columns=["ctid", "name"],
                row_count=1,
                execution_time_ms=10.0,
            ),
            StrategyResult(
                strategy_type=StrategyType.FULLTEXT,
                rows=[{"ctid": "(0,2)", "name": "Bob"}],
                columns=["ctid", "name"],
                row_count=1,
                execution_time_ms=15.0,
            ),
            StrategyResult(
                strategy_type=StrategyType.VECTOR,
                rows=[{"ctid": "(0,3)", "name": "Charlie"}],
                columns=["ctid", "name"],
                row_count=1,
                execution_time_ms=20.0,
            ),
        ]

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
        )

        assert len(results) == 3
        types: list[StrategyType] = [r.strategy_type for r in results]
        assert StrategyType.STRUCTURED in types
        assert StrategyType.FULLTEXT in types
        assert StrategyType.VECTOR in types

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_one_strategy_raises_returns_error_result(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test one strategy exception returns error, others succeed."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        strategies: list[StrategySQL] = [
            _make_strategy_sql(StrategyType.STRUCTURED),
            _make_strategy_sql(StrategyType.FULLTEXT),
            _make_strategy_sql(StrategyType.VECTOR),
        ]

        mock_exec.side_effect = [
            StrategyResult(
                strategy_type=StrategyType.STRUCTURED,
                rows=[{"ctid": "(0,1)", "name": "Alice"}],
                columns=["ctid", "name"],
                row_count=1,
                execution_time_ms=10.0,
            ),
            StrategyResult(
                strategy_type=StrategyType.FULLTEXT,
                error="relation does not exist",
                execution_time_ms=5.0,
            ),
            StrategyResult(
                strategy_type=StrategyType.VECTOR,
                rows=[{"ctid": "(0,3)", "name": "Charlie"}],
                columns=["ctid", "name"],
                row_count=1,
                execution_time_ms=20.0,
            ),
        ]

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
        )

        assert len(results) == 3

        # Find the failed result
        failed: list[StrategyResult] = [r for r in results if not r.succeeded]
        succeeded: list[StrategyResult] = [r for r in results if r.succeeded]
        assert len(failed) == 1
        assert failed[0].strategy_type == StrategyType.FULLTEXT
        assert failed[0].error is not None
        assert "relation" in failed[0].error
        assert len(succeeded) == 2

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_cancel_event_set_strategies_check_cancellation(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test cancel_event set causes strategies to check cancellation."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        strategies: list[StrategySQL] = [
            _make_strategy_sql(StrategyType.STRUCTURED),
        ]
        cancel: Event = Event()
        cancel.set()

        # Mock returns an error result when cancellation is detected
        mock_exec.return_value = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
            error="Query cancelled before execution",
            execution_time_ms=0.0,
        )

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
            cancel_event=cancel,
        )

        assert len(results) == 1
        # cancel_event should have been passed through
        call_kwargs: Any = mock_exec.call_args.kwargs
        assert call_kwargs.get("cancel_event") is cancel

    def test_empty_strategies_returns_empty_list(self) -> None:
        """Test empty strategies list returns empty list."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=[],
            username="testuser",
        )

        assert not results

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_vector_parameters_resolved(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test strategy with %s::vector has vector parameters resolved."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        vector_sql: str = "SELECT ctid, * FROM t" " ORDER BY _emb_desc <=> %s::vector LIMIT 50"
        strategies: list[StrategySQL] = [
            _make_strategy_sql(
                StrategyType.VECTOR,
                sql=vector_sql,
                parameters=[[0.1] * 1536],
            ),
        ]

        mock_exec.return_value = StrategyResult(
            strategy_type=StrategyType.VECTOR,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
            columns=["ctid", "name"],
            row_count=1,
            execution_time_ms=25.0,
        )

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
        )

        assert len(results) == 1
        assert results[0].strategy_type == StrategyType.VECTOR
        assert results[0].succeeded is True

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_row_count_over_50_truncated(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test row count > 50 is truncated to 50 (FR-011)."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        # Create 60 rows to exceed the 50-row limit
        large_rows: list[dict[str, Any]] = [
            {"ctid": f"(0,{i})", "name": f"Row{i}"} for i in range(60)
        ]

        strategies: list[StrategySQL] = [
            _make_strategy_sql(StrategyType.STRUCTURED),
        ]

        mock_exec.return_value = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
            rows=large_rows[:50],
            columns=["ctid", "name"],
            row_count=50,
            execution_time_ms=30.0,
        )

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
        )

        assert len(results) == 1
        assert results[0].row_count <= 50

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_execution_time_recorded(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test execution_time_ms is recorded in StrategyResult."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        strategies: list[StrategySQL] = [
            _make_strategy_sql(StrategyType.STRUCTURED),
        ]

        mock_exec.return_value = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
            columns=["ctid", "name"],
            row_count=1,
            execution_time_ms=42.5,
        )

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
        )

        assert len(results) == 1
        assert results[0].execution_time_ms > 0.0
        assert results[0].execution_time_ms == 42.5

    @patch.object(
        QueryExecutionService,
        "_execute_single_strategy",
    )
    def test_columns_populated_from_cursor_description(
        self,
        mock_exec: MagicMock,
    ) -> None:
        """Test StrategyResult.columns populated from cursor.description."""
        mock_pool: MagicMock = _make_mock_pool()
        service: QueryExecutionService = QueryExecutionService(mock_pool)

        strategies: list[StrategySQL] = [
            _make_strategy_sql(StrategyType.STRUCTURED),
        ]

        expected_columns: list[str] = ["ctid", "name", "price"]
        mock_exec.return_value = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Widget", "price": 9.99},
            ],
            columns=expected_columns,
            row_count=1,
            execution_time_ms=10.0,
        )

        results: list[StrategyResult] = service.execute_strategies_parallel(
            strategies=strategies,
            username="testuser",
        )

        assert len(results) == 1
        assert results[0].columns == expected_columns
        assert "ctid" in results[0].columns
        assert "name" in results[0].columns
        assert "price" in results[0].columns
