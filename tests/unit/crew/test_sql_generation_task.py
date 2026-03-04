"""Unit tests for SQL generation task with index context injection.

T025 [US1]: Tests create_sql_generation_task() with index_context parameter.
Verifies context injection into task description and graceful None handling.
Also tests value_context + index_context interaction (FTS over ILIKE).

T006 [US1]: Tests multi-strategy SQL generation via strategy_dispatch parameter.
Verifies MULTI-STRATEGY section, per-strategy delimiters, ctid requirement,
LIMIT 50 per strategy, and backwards compatibility.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.src.crew.tasks import create_sql_generation_task
from backend.src.models.fusion import StrategyDispatchPlan, StrategyType


@pytest.mark.unit
class TestSqlGenerationTaskIndexContext:
    """T025: Test index_context parameter in create_sql_generation_task()."""

    @patch("backend.src.crew.tasks.Task")
    def test_index_context_injected_into_description(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test index_context appears in task description."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        context: str = (
            "INDEX CAPABILITIES (use these for optimal query"
            " performance):\n"
            "Table: products_data\n"
            "  Column: name (TEXT)\n"
            "    - B-tree: supports =, <, >, BETWEEN, ORDER BY\n"
        )

        create_sql_generation_task(
            agent=agent,
            query_text="Find products named Widget",
            dataset_ids=[uuid4()],
            index_context=context,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "INDEX CAPABILITIES" in description
        assert "products_data" in description

    @patch("backend.src.crew.tasks.Task")
    def test_index_context_none_handled_gracefully(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test None index_context skips INDEX CAPABILITIES section."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()

        create_sql_generation_task(
            agent=agent,
            query_text="Find products named Widget",
            dataset_ids=[uuid4()],
            index_context=None,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "INDEX CAPABILITIES" not in description

    @patch("backend.src.crew.tasks.Task")
    def test_index_context_empty_string_handled(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test empty string index_context skips section."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()

        create_sql_generation_task(
            agent=agent,
            query_text="Find products named Widget",
            dataset_ids=[uuid4()],
            index_context="",
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "INDEX CAPABILITIES" not in description

    @patch("backend.src.crew.tasks.Task")
    def test_index_context_after_schema_context(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test index_context appears after schema context."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        schema_ctx: str = "\n\nAVAILABLE SCHEMA:\nTable: products_data\n"
        index_ctx: str = (
            "INDEX CAPABILITIES (use these for optimal query"
            " performance):\nTable: products_data\n"
        )

        create_sql_generation_task(
            agent=agent,
            query_text="Find Widget",
            dataset_ids=[uuid4()],
            schema_context=schema_ctx,
            index_context=index_ctx,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        schema_pos: int = description.find("AVAILABLE SCHEMA")
        index_pos: int = description.find("INDEX CAPABILITIES")
        assert schema_pos < index_pos

    @patch("backend.src.crew.tasks.Task")
    def test_fts_requirement_added(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test FTS preference requirement added to task description."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        context: str = "INDEX CAPABILITIES\nTable: test\n"

        create_sql_generation_task(
            agent=agent,
            query_text="Find Widget",
            dataset_ids=[uuid4()],
            index_context=context,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "full-text search" in description.lower()

    @patch("backend.src.crew.tasks.Task")
    def test_vector_requirement_added(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test vector similarity requirement added to task."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        context: str = "INDEX CAPABILITIES\nTable: test\n"

        create_sql_generation_task(
            agent=agent,
            query_text="Find similar products",
            dataset_ids=[uuid4()],
            index_context=context,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "vector" in description.lower() or "<=>" in description

    @patch("backend.src.crew.tasks.Task")
    def test_no_index_context_preserves_original_requirements(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test original requirements intact when no index context."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()

        create_sql_generation_task(
            agent=agent,
            query_text="Show products",
            dataset_ids=[uuid4()],
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "parameterized" in description.lower()
        assert "SQL" in description

    @patch("backend.src.crew.tasks.Task")
    def test_value_context_uses_fts_when_index_context_present(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test value match instructions reference FTS when index context available."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        index_ctx: str = "INDEX CAPABILITIES\nTable: products_data\n"
        search_results: dict[str, Any] = {
            "fused_results": [
                {
                    "source": "data_values",
                    "column_name": "name",
                    "match_count": 5,
                    "sample_values": ["Widget A"],
                },
            ],
        }

        create_sql_generation_task(
            agent=agent,
            query_text="Find Widget",
            dataset_ids=[uuid4()],
            search_results=search_results,
            index_context=index_ctx,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        # FTS instructions present in value-based query section
        assert "full-text search" in description.lower()
        assert "plainto_tsquery" in description
        # No standalone ILIKE example directive (ILIKE only as fallback mention)
        assert "Generate a WHERE clause using ILIKE" not in description

    @patch("backend.src.crew.tasks.Task")
    def test_value_context_uses_ilike_without_index_context(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test value match instructions use ILIKE when no index context."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        search_results: dict[str, Any] = {
            "fused_results": [
                {
                    "source": "data_values",
                    "column_name": "name",
                    "match_count": 5,
                    "sample_values": ["Widget A"],
                },
            ],
        }

        create_sql_generation_task(
            agent=agent,
            query_text="Find Widget",
            dataset_ids=[uuid4()],
            search_results=search_results,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "ILIKE" in description


# ---------------------------------------------------------------------------
# Helpers for multi-strategy tests
# ---------------------------------------------------------------------------


def _make_three_strategy_plan() -> StrategyDispatchPlan:
    """Create a StrategyDispatchPlan with all three strategies."""
    return StrategyDispatchPlan(
        strategies=[
            StrategyType.STRUCTURED,
            StrategyType.FULLTEXT,
            StrategyType.VECTOR,
        ],
        available_indexes={
            "products_data": [
                "filtering",
                "full_text_search",
                "vector_similarity",
            ],
        },
    )


def _make_single_strategy_plan() -> StrategyDispatchPlan:
    """Create a StrategyDispatchPlan with only STRUCTURED."""
    return StrategyDispatchPlan(
        strategies=[StrategyType.STRUCTURED],
    )


# ---------------------------------------------------------------------------
# T006: Multi-strategy SQL generation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMultiStrategySqlGenerationTask:
    """T006: Test strategy_dispatch parameter in create_sql_generation_task.

    Verifies that when strategy_dispatch is provided with multiple
    strategies, the task description includes MULTI-STRATEGY section,
    per-strategy delimiters, ctid requirement, and LIMIT 50.
    Also verifies backwards compatibility when strategy_dispatch is None.
    """

    @patch("backend.src.crew.tasks.Task")
    def test_three_strategies_contains_multi_strategy_section(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test strategy_dispatch with 3 strategies includes MULTI-STRATEGY."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        plan: StrategyDispatchPlan = _make_three_strategy_plan()

        create_sql_generation_task(
            agent=agent,
            query_text="Find expensive products",
            dataset_ids=[uuid4()],
            strategy_dispatch=plan,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "MULTI-STRATEGY" in description

    @patch("backend.src.crew.tasks.Task")
    def test_three_strategies_contains_all_delimiter_markers(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test strategy_dispatch with 3 strategies has all delimiters."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        plan: StrategyDispatchPlan = _make_three_strategy_plan()

        create_sql_generation_task(
            agent=agent,
            query_text="Find expensive products",
            dataset_ids=[uuid4()],
            strategy_dispatch=plan,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "---STRATEGY: structured---" in description
        assert "---STRATEGY: fulltext---" in description
        assert "---STRATEGY: vector---" in description
        assert "---END STRATEGY---" in description

    @patch("backend.src.crew.tasks.Task")
    def test_three_strategies_mentions_ctid(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test strategy_dispatch with 3 strategies mentions ctid."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        plan: StrategyDispatchPlan = _make_three_strategy_plan()

        create_sql_generation_task(
            agent=agent,
            query_text="Find expensive products",
            dataset_ids=[uuid4()],
            strategy_dispatch=plan,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "ctid" in description

    @patch("backend.src.crew.tasks.Task")
    def test_three_strategies_mentions_limit_50(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test strategy_dispatch with 3 strategies mentions LIMIT 50."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        plan: StrategyDispatchPlan = _make_three_strategy_plan()

        create_sql_generation_task(
            agent=agent,
            query_text="Find expensive products",
            dataset_ids=[uuid4()],
            strategy_dispatch=plan,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "LIMIT 50" in description

    @patch("backend.src.crew.tasks.Task")
    def test_strategy_dispatch_none_no_multi_strategy(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test strategy_dispatch=None has no MULTI-STRATEGY section."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()

        create_sql_generation_task(
            agent=agent,
            query_text="Find expensive products",
            dataset_ids=[uuid4()],
            strategy_dispatch=None,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "MULTI-STRATEGY" not in description

    @patch("backend.src.crew.tasks.Task")
    def test_single_strategy_no_multi_strategy_section(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test strategy_dispatch with 1 strategy has no MULTI-STRATEGY."""
        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        plan: StrategyDispatchPlan = _make_single_strategy_plan()

        create_sql_generation_task(
            agent=agent,
            query_text="Find expensive products",
            dataset_ids=[uuid4()],
            strategy_dispatch=plan,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "MULTI-STRATEGY" not in description
