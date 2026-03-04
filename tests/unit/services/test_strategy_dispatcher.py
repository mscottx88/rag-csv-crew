"""Unit tests for StrategyDispatcherService.

Tests plan_strategies() strategy selection based on index metadata (T005),
detect_aggregation_intent() keyword matching (T020), and aggregation-aware
plan_strategies behavior (T021).

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from backend.src.models.fusion import StrategyDispatchPlan, StrategyType
from backend.src.services.strategy_dispatcher import StrategyDispatcherService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_pool(
    fetchall_return: list[tuple[Any, ...]],
) -> MagicMock:
    """Build a MagicMock that mimics ConnectionPool context managers.

    Creates a mock pool where pool.connection().__enter__() returns
    a mock connection whose cursor().__enter__() returns a mock
    cursor with the given fetchall return value.

    Args:
        fetchall_return: Rows returned by cursor.fetchall().

    Returns:
        MagicMock configured as a ConnectionPool.

    Note:
        plan_strategies() calls _query_capabilities then _query_available_indexes.
        fetchall.side_effect provides sequential return values for both calls.
        Default second return is empty (no index metadata), override via
        _get_mock_cursor(pool).fetchall.side_effect = [...] for specific tests.
    """
    mock_pool: MagicMock = MagicMock()
    mock_conn: MagicMock = MagicMock()
    mock_cursor: MagicMock = MagicMock()

    # Default: first call returns capability rows, second call returns empty
    mock_cursor.fetchall.side_effect = [fetchall_return, []]

    # Wire up context managers:
    # pool.connection().__enter__() -> conn
    mock_pool.connection.return_value.__enter__ = MagicMock(
        return_value=mock_conn,
    )
    mock_pool.connection.return_value.__exit__ = MagicMock(
        return_value=False,
    )
    # conn.cursor().__enter__() -> cursor
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor,
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(
        return_value=False,
    )

    return mock_pool


def _get_mock_cursor(mock_pool: MagicMock) -> MagicMock:
    """Extract the mock cursor from a mock pool built by _build_mock_pool.

    Args:
        mock_pool: Pool mock created by _build_mock_pool.

    Returns:
        The mock cursor that execute() and fetchall() are called on.
    """
    mock_conn: MagicMock = mock_pool.connection.return_value.__enter__.return_value
    mock_cursor: MagicMock = mock_conn.cursor.return_value.__enter__.return_value
    return mock_cursor


# ---------------------------------------------------------------------------
# T005: plan_strategies tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlanStrategies:
    """T005: Test plan_strategies() strategy dispatch logic."""

    def test_all_three_indexes_returns_all_strategies(self) -> None:
        """All 3 capabilities present returns STRUCTURED, FULLTEXT, VECTOR.

        When index_metadata contains filtering, full_text_search, and
        vector_similarity capabilities, the plan should include all
        three strategy types.
        """
        cap_rows: list[tuple[str]] = [
            ("filtering",),
            ("full_text_search",),
            ("vector_similarity",),
        ]
        idx_rows: list[tuple[str, list[str]]] = [
            ("my_table", ["filtering", "full_text_search", "vector_similarity"]),
        ]
        mock_pool: MagicMock = _build_mock_pool(cap_rows)
        cursor: MagicMock = _get_mock_cursor(mock_pool)
        cursor.fetchall.side_effect = [cap_rows, idx_rows]
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert len(plan.strategies) == 3
        assert StrategyType.STRUCTURED in plan.strategies
        assert StrategyType.FULLTEXT in plan.strategies
        assert StrategyType.VECTOR in plan.strategies

    def test_only_btree_returns_structured_only(self) -> None:
        """Only filtering capability returns [STRUCTURED] only.

        When index_metadata only contains 'filtering' capability
        (B-tree indexes), the plan should include only STRUCTURED.
        """
        rows: list[tuple[str]] = [("filtering",)]
        mock_pool: MagicMock = _build_mock_pool(rows)
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert plan.strategies == [StrategyType.STRUCTURED]

    def test_fts_and_btree_no_vector(self) -> None:
        """FTS + B-tree but no vector returns [STRUCTURED, FULLTEXT].

        When capabilities include filtering and full_text_search but
        not vector_similarity, VECTOR should be excluded.
        """
        rows: list[tuple[str]] = [
            ("filtering",),
            ("full_text_search",),
        ]
        mock_pool: MagicMock = _build_mock_pool(rows)
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert StrategyType.STRUCTURED in plan.strategies
        assert StrategyType.FULLTEXT in plan.strategies
        assert StrategyType.VECTOR not in plan.strategies
        assert len(plan.strategies) == 2

    def test_vector_and_btree_no_fts(self) -> None:
        """Vector + B-tree but no FTS returns [STRUCTURED, VECTOR].

        When capabilities include filtering and vector_similarity but
        not full_text_search, FULLTEXT should be excluded.
        """
        rows: list[tuple[str]] = [
            ("filtering",),
            ("vector_similarity",),
        ]
        mock_pool: MagicMock = _build_mock_pool(rows)
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert StrategyType.STRUCTURED in plan.strategies
        assert StrategyType.VECTOR in plan.strategies
        assert StrategyType.FULLTEXT not in plan.strategies
        assert len(plan.strategies) == 2

    def test_dataset_ids_none_queries_all_datasets(self) -> None:
        """dataset_ids=None queries all user datasets (FR-017).

        When dataset_ids is None the service should query index_metadata
        without a WHERE dataset_id filter, returning capabilities across
        all datasets in the user's schema.
        """
        rows: list[tuple[str]] = [("filtering",)]
        mock_pool: MagicMock = _build_mock_pool(rows)
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=None,
        )

        # Verify queries were executed (capabilities + available_indexes)
        mock_cursor: MagicMock = _get_mock_cursor(mock_pool)
        assert mock_cursor.execute.call_count >= 1

        # The first SQL should NOT contain dataset_id filter
        first_call_args: tuple[Any, ...] = mock_cursor.execute.call_args_list[0][0]
        query_str: str = str(first_call_args[0])
        assert "dataset_id" not in query_str.lower() or ("ANY" not in query_str)

        assert plan.strategies == [StrategyType.STRUCTURED]

    def test_structured_always_first(self) -> None:
        """STRUCTURED is always the first strategy in the list (FR-002).

        Regardless of which capabilities are present, STRUCTURED must
        appear at index 0 of the strategies list.
        """
        rows: list[tuple[str]] = [
            ("full_text_search",),
            ("vector_similarity",),
            ("filtering",),
        ]
        mock_pool: MagicMock = _build_mock_pool(rows)
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert plan.strategies[0] == StrategyType.STRUCTURED

    def test_available_indexes_populated(self) -> None:
        """available_indexes dict is populated with capability strings.

        The plan's available_indexes should contain capability strings
        from the index_metadata query results, mapped by dataset/table.
        """
        cap_rows: list[tuple[str]] = [
            ("filtering",),
            ("full_text_search",),
            ("vector_similarity",),
        ]
        idx_rows: list[tuple[str, list[str]]] = [
            ("my_table", ["filtering", "full_text_search", "vector_similarity"]),
        ]
        mock_pool: MagicMock = _build_mock_pool(cap_rows)
        cursor: MagicMock = _get_mock_cursor(mock_pool)
        cursor.fetchall.side_effect = [cap_rows, idx_rows]
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        # available_indexes should not be empty when capabilities exist
        assert len(plan.available_indexes) > 0

        # Verify capability strings appear in the index values
        all_caps: list[str] = []
        avail_idx: dict[str, list[str]] = plan.available_indexes
        for caps_list in avail_idx.values():
            all_caps.extend(caps_list)
        assert "filtering" in all_caps
        assert "full_text_search" in all_caps
        assert "vector_similarity" in all_caps


# ---------------------------------------------------------------------------
# T020: detect_aggregation_intent tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectAggregationIntent:
    """T020: Test detect_aggregation_intent() keyword matching."""

    def test_count_detected(self) -> None:
        """'count' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "count",
        )
        assert result is True

    def test_sum_detected(self) -> None:
        """'sum' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "sum",
        )
        assert result is True

    def test_average_detected(self) -> None:
        """'average' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "average",
        )
        assert result is True

    def test_avg_detected(self) -> None:
        """'avg' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "avg",
        )
        assert result is True

    def test_total_detected(self) -> None:
        """'total' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "total",
        )
        assert result is True

    def test_minimum_detected(self) -> None:
        """'minimum' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "minimum",
        )
        assert result is True

    def test_min_detected(self) -> None:
        """'min' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "min",
        )
        assert result is True

    def test_maximum_detected(self) -> None:
        """'maximum' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "maximum",
        )
        assert result is True

    def test_max_detected(self) -> None:
        """'max' keyword triggers aggregation detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "max",
        )
        assert result is True

    def test_how_many_phrase(self) -> None:
        """'how many products are there?' triggers detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "how many products are there?",
        )
        assert result is True

    def test_what_is_the_total_phrase(self) -> None:
        """'what is the total revenue?' triggers detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "what is the total revenue?",
        )
        assert result is True

    def test_what_is_the_average_phrase(self) -> None:
        """'what is the average price?' triggers detection."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "what is the average price?",
        )
        assert result is True

    def test_no_aggregation_show_all(self) -> None:
        """'Show me all products' returns False (no aggregation)."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "Show me all products",
        )
        assert result is False

    def test_no_aggregation_find_chargers(self) -> None:
        """'Find wireless chargers' returns False."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "Find wireless chargers",
        )
        assert result is False

    def test_case_insensitivity(self) -> None:
        """'COUNT of items' is detected (case-insensitive matching)."""
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "COUNT of items",
        )
        assert result is True

    def test_how_many_categories_acceptable_false_positive(
        self,
    ) -> None:
        """'how many categories of wireless chargers' is True.

        This is an acceptable false positive per FR-019: the phrase
        'how many' triggers aggregation detection even when the user
        might want a list.
        """
        result: bool = StrategyDispatcherService.detect_aggregation_intent(
            "how many categories of wireless chargers",
        )
        assert result is True


# ---------------------------------------------------------------------------
# T021: aggregation-aware plan_strategies tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAggregationAwarePlanStrategies:
    """T021: Test aggregation-aware strategy dispatch behavior."""

    def test_aggregation_true_returns_structured_only(self) -> None:
        """is_aggregation=True with all indexes returns only [STRUCTURED].

        When aggregation intent is detected (is_aggregation=True), the
        plan must include only STRUCTURED regardless of available
        index capabilities (FR-019).
        """
        idx_rows: list[tuple[str, list[str]]] = [
            ("my_table", ["filtering", "full_text_search", "vector_similarity"]),
        ]
        mock_pool: MagicMock = _build_mock_pool(idx_rows)
        # is_aggregation=True only calls _query_available_indexes (1 call)
        cursor: MagicMock = _get_mock_cursor(mock_pool)
        cursor.fetchall.side_effect = [idx_rows]
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
            is_aggregation=True,
        )

        assert plan.strategies == [StrategyType.STRUCTURED]
        assert plan.is_aggregation is True

    def test_cross_dataset_union_of_capabilities(self) -> None:
        """Cross-dataset queries produce union of capabilities.

        When querying multiple datasets with different index profiles,
        the plan should include strategies based on the union of all
        capabilities across datasets.
        """
        # Simulate union: one dataset has FTS, another has vector
        cap_rows: list[tuple[str]] = [
            ("filtering",),
            ("full_text_search",),
            ("vector_similarity",),
        ]
        idx_rows: list[tuple[str, list[str]]] = [
            ("table_a", ["filtering", "full_text_search"]),
            ("table_b", ["filtering", "vector_similarity"]),
        ]
        mock_pool: MagicMock = _build_mock_pool(cap_rows)
        cursor: MagicMock = _get_mock_cursor(mock_pool)
        cursor.fetchall.side_effect = [cap_rows, idx_rows]
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4(), uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert StrategyType.STRUCTURED in plan.strategies
        assert StrategyType.FULLTEXT in plan.strategies
        assert StrategyType.VECTOR in plan.strategies

    def test_single_strategy_bypass_signals_len_one(self) -> None:
        """Only STRUCTURED available signals single-strategy path.

        When only B-tree indexes are available, the plan has exactly
        one strategy (len==1), signaling the single-strategy bypass
        path downstream.
        """
        rows: list[tuple[str]] = [("filtering",)]
        mock_pool: MagicMock = _build_mock_pool(rows)
        service: StrategyDispatcherService = StrategyDispatcherService(
            mock_pool,
        )
        dataset_ids: list[UUID] = [uuid4()]

        plan: StrategyDispatchPlan = service.plan_strategies(
            username="alice",
            dataset_ids=dataset_ids,
        )

        assert len(plan.strategies) == 1
        assert plan.strategies[0] == StrategyType.STRUCTURED
