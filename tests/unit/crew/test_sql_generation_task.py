"""Unit tests for SQL generation task with index context injection.

T025 [US1]: Tests create_sql_generation_task() with index_context parameter.
Verifies context injection into task description and graceful None handling.
Also tests value_context + index_context interaction (FTS over ILIKE).

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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
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

        call_kwargs: dict[str, Any] = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "ILIKE" in description
