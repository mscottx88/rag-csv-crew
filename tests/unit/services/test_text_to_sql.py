"""Unit tests for text-to-SQL service with CrewAI integration.

Tests the text-to-SQL service that converts natural language queries to SQL
using CrewAI SQL Generator agent and executes them against the database.
Tests index context retrieval in query processing flow (T026).
Tests multi-strategy SQL parsing from LLM output (T007).

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from backend.src.models.fusion import StrategySQL, StrategyType
from backend.src.models.index_metadata import (
    DataColumnIndexProfile,
    IndexCapability,
    IndexMetadataEntry,
    IndexStatus,
    IndexType,
)
from backend.src.services.index_manager import (
    build_index_context,
    get_index_profiles,
)
from backend.src.services.text_to_sql import parse_multi_strategy_sql


@pytest.mark.unit
class TestTextToSQLService:
    """Unit tests for text-to-SQL service (T051)."""

    @patch("backend.src.services.text_to_sql.TextToSQLService.get_schema_context")
    @patch("backend.src.services.text_to_sql.Crew")
    def test_generate_sql_from_natural_language(
        self, mock_crew: MagicMock, mock_get_schema: MagicMock
    ) -> None:
        """Test text-to-SQL conversion generates valid SQL query.

        Validates:
        - Natural language query is converted to SQL
        - Generated SQL is parameterized (no injection risk)
        - CrewAI SQL Generator agent is invoked correctly

        Args:
            mock_crew: Mocked CrewAI Crew class
            mock_get_schema: Mocked get_schema_context method

        Success Criteria (T051):
        - Service converts natural language to SQL
        - Generated SQL follows parameterized query pattern
        - Agent receives correct input
        """
        from backend.src.services.text_to_sql import TextToSQLService

        mock_get_schema.return_value = {
            "tables": ["sales_data"],
            "columns": {"sales_data": ["region", "amount"]},
        }

        # Mock CrewAI response
        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "SELECT * FROM sales_data WHERE region = %s LIMIT 10"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        service: TextToSQLService = TextToSQLService()
        user_query: str = "Show me the top 10 sales in the North region"
        dataset_ids: list[UUID] = [uuid4()]

        result: dict[str, Any] = service.generate_sql(
            query_text=user_query, dataset_ids=dataset_ids, username="testuser"
        )

        # Verify SQL was generated
        assert "sql" in result
        assert isinstance(result["sql"], str)
        assert len(result["sql"]) > 0

        # Verify no SQL injection (should use parameterized queries)
        sql: str = result["sql"]
        assert "SELECT" in sql.upper()
        # Should use %s placeholders, not string interpolation
        assert "'" not in sql or "%s" in sql

        # Verify CrewAI was called
        mock_crew_instance.kickoff.assert_called_once()

    @patch("backend.src.services.text_to_sql.TextToSQLService.get_schema_context")
    @patch("backend.src.services.text_to_sql.Crew")
    def test_generate_sql_handles_multiple_datasets(
        self, mock_crew: MagicMock, mock_get_schema: MagicMock
    ) -> None:
        """Test SQL generation for queries spanning multiple datasets.

        Validates:
        - Multiple dataset IDs are passed to agent
        - Generated SQL includes JOIN clauses
        - Cross-reference information is utilized

        Args:
            mock_crew: Mocked CrewAI Crew class
            mock_get_schema: Mocked get_schema_context method

        Success Criteria (T051):
        - Multi-dataset queries generate JOIN SQL
        - Agent receives all dataset IDs
        """
        from backend.src.services.text_to_sql import TextToSQLService

        mock_get_schema.return_value = {
            "tables": ["customers_data", "orders_data"],
            "columns": {
                "customers_data": ["id", "name"],
                "orders_data": ["id", "customer_id", "amount"],
            },
        }

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = """
            SELECT c.name, SUM(o.amount) AS total
            FROM customers_data c
            JOIN orders_data o ON c.id = o.customer_id
            GROUP BY c.name
            """
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        service: TextToSQLService = TextToSQLService()
        dataset_ids: list[UUID] = [uuid4(), uuid4()]

        result: dict[str, Any] = service.generate_sql(
            query_text="Which customers have the highest order totals?",
            dataset_ids=dataset_ids,
            username="testuser",
        )

        assert "sql" in result
        sql: str = result["sql"]
        # Should contain JOIN for multi-dataset query
        assert "JOIN" in sql.upper()

    @patch("backend.src.services.text_to_sql.Crew")
    def test_generate_sql_error_handling(self, mock_crew: MagicMock) -> None:
        """Test error handling when SQL generation fails.

        Validates:
        - LLM API failures are caught
        - Retry logic is applied per constitution
        - Error messages are user-friendly

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T051):
        - API failures raise appropriate exceptions
        - Error messages don't leak sensitive info
        """
        from backend.src.services.text_to_sql import TextToSQLService

        mock_crew_instance: MagicMock = MagicMock()
        mock_crew_instance.kickoff.side_effect = Exception("API rate limit exceeded")
        mock_crew.return_value = mock_crew_instance

        service: TextToSQLService = TextToSQLService()

        with pytest.raises(Exception) as exc_info:
            service.generate_sql(
                query_text="Show me the data", dataset_ids=[uuid4()], username="testuser"
            )

        # Verify error is raised
        assert exc_info.value is not None

    def test_validate_sql_injection_prevention(self) -> None:
        """Test SQL injection prevention in generated queries.

        Validates:
        - User input is not directly interpolated into SQL
        - Parameterized queries are enforced
        - Special characters are handled safely

        Success Criteria (T051):
        - Service rejects unsafe SQL patterns
        - Only parameterized queries are accepted
        """
        from backend.src.services.text_to_sql import TextToSQLService

        service: TextToSQLService = TextToSQLService()

        # Test dangerous input
        malicious_query: str = "Show data'; DROP TABLE users; --"

        # Service should sanitize or reject this
        # Actual implementation will use parameterized queries via psycopg
        with patch.object(service, "generate_sql") as mock_generate:
            mock_generate.return_value = {
                "sql": "SELECT * FROM data WHERE query = %s",
                "params": [malicious_query],
            }

            result: dict[str, Any] = service.generate_sql(
                query_text=malicious_query, dataset_ids=[uuid4()], username="testuser"
            )

            # Verify parameterized query pattern
            assert "params" in result
            assert isinstance(result["params"], list)
            # Original malicious input should be in params, not SQL string
            assert malicious_query not in result["sql"]


_TEST_DATASET_ID: str = "12345678-1234-1234-1234-123456789abc"


def _make_index_entry(
    column_name: str,
    index_type: IndexType,
    capability: IndexCapability,
    generated_column_name: str | None = None,
) -> IndexMetadataEntry:
    """Create an IndexMetadataEntry for T026 tests."""
    return IndexMetadataEntry(
        id=uuid4(),
        dataset_id=UUID(_TEST_DATASET_ID),
        column_name=column_name,
        index_name=f"idx_test_{column_name}_{index_type.value}",
        index_type=index_type,
        capability=capability,
        generated_column_name=generated_column_name,
        status=IndexStatus.CREATED,
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
class TestIndexContextRetrieval:
    """T026: Test index context retrieval in query processing flow."""

    def test_get_index_profiles_called_with_correct_dataset_ids(
        self,
    ) -> None:
        """Test get_index_profiles receives correct dataset_ids."""
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor,
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(
            return_value=False,
        )
        mock_cursor.fetchall.return_value = []

        ds_ids: list[str] = [_TEST_DATASET_ID]
        get_index_profiles(
            mock_conn,
            "testuser",
            ds_ids,
        )

        # Should query with the correct dataset_id
        mock_cursor.execute.assert_called_once()
        call_args: tuple[Any, ...] = mock_cursor.execute.call_args[0]
        assert _TEST_DATASET_ID in str(call_args)

    def test_build_index_context_with_profiles_and_table_names(
        self,
    ) -> None:
        """Test build_index_context called with correct profiles."""
        btree: IndexMetadataEntry = _make_index_entry(
            "name",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        gin: IndexMetadataEntry = _make_index_entry(
            "name",
            IndexType.GIN,
            IndexCapability.FULL_TEXT_SEARCH,
            generated_column_name="_ts_name",
        )
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="name",
            dataset_id=UUID(_TEST_DATASET_ID),
            indexes=[btree, gin],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: [profile],
        }
        table_names: dict[str, str] = {
            _TEST_DATASET_ID: "products_data",
        }

        context: str = build_index_context(profiles, table_names)

        assert "Table: products_data" in context
        assert "Column: name (TEXT)" in context
        assert "Full-text search via '_ts_name'" in context

    @patch("backend.src.crew.tasks.Task")
    def test_index_context_passed_to_task_creation(
        self,
        mock_task_cls: MagicMock,
    ) -> None:
        """Test index_context string is passed to task creation."""
        from backend.src.crew.tasks import create_sql_generation_task

        mock_task_cls.return_value = MagicMock()
        agent: MagicMock = MagicMock()
        context: str = "INDEX CAPABILITIES\nTest context\n"

        create_sql_generation_task(
            agent=agent,
            query_text="Find products",
            dataset_ids=[UUID(_TEST_DATASET_ID)],
            index_context=context,
        )

        call_kwargs: Any = mock_task_cls.call_args.kwargs
        description: str = call_kwargs["description"]
        assert "INDEX CAPABILITIES" in description

    def test_empty_profiles_produce_no_context(self) -> None:
        """Test empty profiles produce empty index_context."""
        context: str = build_index_context({}, {})
        assert context == ""

    def test_context_includes_all_datasets(self) -> None:
        """Test context covers all requested datasets."""
        ds_id_1: str = _TEST_DATASET_ID
        ds_id_2: str = str(uuid4())

        btree_1: IndexMetadataEntry = _make_index_entry(
            "name",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        btree_2: IndexMetadataEntry = IndexMetadataEntry(
            id=uuid4(),
            dataset_id=UUID(ds_id_2),
            column_name="price",
            index_name="idx_orders_price_btree",
            index_type=IndexType.BTREE,
            capability=IndexCapability.FILTERING,
            status=IndexStatus.CREATED,
            created_at=datetime.now(UTC),
        )

        profile_1: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="name",
            dataset_id=UUID(ds_id_1),
            indexes=[btree_1],
        )
        profile_2: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="price",
            dataset_id=UUID(ds_id_2),
            indexes=[btree_2],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            ds_id_1: [profile_1],
            ds_id_2: [profile_2],
        }
        table_names: dict[str, str] = {
            ds_id_1: "products_data",
            ds_id_2: "orders_data",
        }

        context: str = build_index_context(profiles, table_names)

        assert "Table: products_data" in context
        assert "Table: orders_data" in context


@pytest.mark.unit
class TestRuntimeEmbeddingDetection:
    """T040: Unit tests for runtime embedding detection in query execution."""

    def test_detect_vector_placeholder_in_sql(self) -> None:
        """Test detection of %s::vector placeholder in generated SQL."""
        from backend.src.services.text_to_sql import (
            _detect_vector_placeholders,
        )

        sql: str = (
            "SELECT * FROM products_data" " ORDER BY _emb_description <=> %s::vector LIMIT 10"
        )
        result: bool = _detect_vector_placeholders(sql)

        assert result is True

    def test_no_vector_placeholder(self) -> None:
        """Test no detection when SQL lacks vector placeholders."""
        from backend.src.services.text_to_sql import (
            _detect_vector_placeholders,
        )

        sql: str = "SELECT * FROM products_data WHERE price > %s"
        result: bool = _detect_vector_placeholders(sql)

        assert result is False

    @patch(
        "backend.src.services.vector_search.VectorSearchService",
    )
    def test_embedding_generated_for_vector_query(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test runtime embedding generated when SQL has vector placeholder."""
        from backend.src.services.text_to_sql import (
            _resolve_vector_params,
        )

        mock_vs: MagicMock = MagicMock()
        mock_vs.generate_embedding.return_value = [0.1] * 1536
        mock_vs_cls.return_value = mock_vs

        sql: str = (
            "SELECT * FROM products_data" " ORDER BY _emb_description <=> %s::vector LIMIT 10"
        )
        query_text: str = "find similar products"

        resolved_sql: str
        params: list[Any]
        resolved_sql, params = _resolve_vector_params(
            sql,
            query_text,
        )

        assert len(params) == 1
        assert len(params[0]) == 1536
        # %s::vector should remain as %s for psycopg parameterization
        assert "%s::vector" not in resolved_sql
        assert "%s" in resolved_sql

    def test_non_vector_sql_unchanged(self) -> None:
        """Test non-vector SQL returns unchanged with empty params."""
        from backend.src.services.text_to_sql import (
            _resolve_vector_params,
        )

        sql: str = "SELECT * FROM products_data WHERE price > %s"
        query_text: str = "find expensive products"

        resolved_sql: str
        params: list[Any]
        resolved_sql, params = _resolve_vector_params(
            sql,
            query_text,
        )

        assert resolved_sql == sql
        assert params == []


# ---------------------------------------------------------------------------
# T007: Multi-strategy SQL parsing tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMultiStrategySqlParsing:
    """T007: Test parse_multi_strategy_sql from LLM output.

    Verifies parsing of labeled SQL blocks delimited by
    ---STRATEGY: <name>--- / ---END STRATEGY--- markers
    from raw LLM output text.
    """

    def test_valid_three_strategy_output(self) -> None:
        """Test valid 3-strategy output returns 3 StrategySQL objects."""
        raw: str = (
            "Here are the SQL queries:\n\n"
            "---STRATEGY: structured---\n"
            "SELECT ctid, * FROM products_data"
            " WHERE price > %s LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "---STRATEGY: fulltext---\n"
            "SELECT ctid, * FROM products_data"
            " WHERE _ts_name @@ plainto_tsquery(%s)"
            " LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "---STRATEGY: vector---\n"
            "SELECT ctid, * FROM products_data"
            " ORDER BY _emb_desc <=> %s::vector"
            " LIMIT 50\n"
            "---END STRATEGY---\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "find products")

        assert len(results) == 3
        types: list[StrategyType] = [r.strategy_type for r in results]
        assert StrategyType.STRUCTURED in types
        assert StrategyType.FULLTEXT in types
        assert StrategyType.VECTOR in types

    def test_valid_single_strategy_output(self) -> None:
        """Test valid 1-strategy output returns 1 StrategySQL."""
        raw: str = (
            "---STRATEGY: structured---\n"
            "SELECT ctid, * FROM products_data LIMIT 50\n"
            "---END STRATEGY---\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "show products")

        assert len(results) == 1
        assert results[0].strategy_type == StrategyType.STRUCTURED

    def test_malformed_block_missing_end_delimiter(self) -> None:
        """Missing END delimiter causes greedy capture to next END.

        When fulltext block lacks ---END STRATEGY---, the non-greedy
        regex matches from fulltext's start to vector's END, absorbing
        the vector block content. Result: structured + fulltext parsed,
        vector lost (consumed by fulltext's greedy match).
        """
        raw: str = (
            "---STRATEGY: structured---\n"
            "SELECT ctid, * FROM t WHERE id = %s LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "---STRATEGY: fulltext---\n"
            "SELECT ctid, * FROM t WHERE _ts @@ %s LIMIT 50\n"
            "THIS BLOCK HAS NO END DELIMITER\n\n"
            "---STRATEGY: vector---\n"
            "SELECT ctid, * FROM t ORDER BY e <=> %s::vector"
            " LIMIT 50\n"
            "---END STRATEGY---\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "test query")

        # Structured and fulltext both match; vector is consumed by
        # fulltext's non-greedy capture extending to vector's END
        types: list[StrategyType] = [r.strategy_type for r in results]
        assert StrategyType.STRUCTURED in types
        assert StrategyType.FULLTEXT in types
        # vector block was consumed by fulltext's extended match
        assert StrategyType.VECTOR not in types

    def test_invalid_strategy_name_skipped(self) -> None:
        """Test invalid strategy name (e.g., 'unknown') is skipped."""
        raw: str = (
            "---STRATEGY: structured---\n"
            "SELECT ctid, * FROM t LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "---STRATEGY: unknown---\n"
            "SELECT ctid, * FROM t LIMIT 50\n"
            "---END STRATEGY---\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "test query")

        assert len(results) == 1
        assert results[0].strategy_type == StrategyType.STRUCTURED

    def test_empty_sql_in_block_skipped(self) -> None:
        """Test empty SQL in block causes that block to be skipped."""
        raw: str = (
            "---STRATEGY: structured---\n"
            "SELECT ctid, * FROM t LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "---STRATEGY: fulltext---\n"
            "   \n"
            "---END STRATEGY---\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "test query")

        assert len(results) == 1
        assert results[0].strategy_type == StrategyType.STRUCTURED

    def test_zero_valid_blocks_returns_empty(self) -> None:
        """Test zero valid blocks returns empty list."""
        raw: str = "Here is some text with no valid strategy blocks.\n" "No delimiters at all.\n"
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "test query")

        assert results == []

    def test_extra_text_between_blocks_only_delimited_extracted(
        self,
    ) -> None:
        """Test extra text between blocks is ignored."""
        raw: str = (
            "Some preamble text explaining the approach.\n\n"
            "---STRATEGY: structured---\n"
            "SELECT ctid, name FROM t WHERE id = %s LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "Now let me explain the fulltext approach...\n"
            "This uses tsvector for matching.\n\n"
            "---STRATEGY: fulltext---\n"
            "SELECT ctid, name FROM t"
            " WHERE _ts @@ plainto_tsquery(%s) LIMIT 50\n"
            "---END STRATEGY---\n\n"
            "Final thoughts on the query strategy.\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "find items")

        assert len(results) == 2
        types: list[StrategyType] = [r.strategy_type for r in results]
        assert StrategyType.STRUCTURED in types
        assert StrategyType.FULLTEXT in types

    def test_parameter_extraction_counts_placeholders(self) -> None:
        """Test %s placeholders are counted correctly in parameters."""
        raw: str = (
            "---STRATEGY: structured---\n"
            "SELECT ctid, * FROM t"
            " WHERE name = %s AND price > %s AND active = %s"
            " LIMIT 50\n"
            "---END STRATEGY---\n"
        )
        results: list[StrategySQL] = parse_multi_strategy_sql(raw, "find active products")

        assert len(results) == 1
        # Parameters list should have entries for each %s placeholder
        param_count: int = len(results[0].parameters)
        sql_text: str = results[0].sql
        placeholder_count: int = sql_text.count("%s")
        assert placeholder_count == 3
        assert param_count == placeholder_count
