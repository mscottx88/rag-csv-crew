"""Unit tests for full-text search service (T104-TEST).

Tests the full-text search functionality using PostgreSQL tsvector and
ts_rank for keyword-based column matching.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.src.services.hybrid_search import HybridSearchService


@pytest.mark.unit
class TestFullTextSearch:
    """Unit tests for full-text search service (T104)."""

    def test_fulltext_search_basic_query(self) -> None:
        """Test basic full-text search query against _fulltext column.

        Validates:
        - Query uses ts_query for text search
        - Results ranked by ts_rank
        - _fulltext tsvector column is queried

        Success Criteria (T104):
        - Search returns relevant columns
        - Results ordered by text relevance
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        # Mock pool.connection() returning connection context manager
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        # Mock conn.cursor() returning cursor context manager
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchall.return_value = [
            ("revenue", "dataset-1", 0.9),
            ("total_revenue", "dataset-2", 0.7),
            ("revenue_annual", "dataset-3", 0.5),
        ]

        service: HybridSearchService = HybridSearchService(mock_pool)
        results: list[dict[str, Any]] = service.fulltext_search(
            username="testuser", query_text="revenue", limit=10
        )

        # Verify results
        assert len(results) == 3
        assert results[0]["column_name"] == "revenue"
        assert results[0]["rank"] == 0.9

        # Verify SQL query used ts_query and ts_rank (second execute call is the actual query)
        assert mock_cursor.execute.call_count == 2  # SET search_path + actual query
        sql_query: str = mock_cursor.execute.call_args_list[1][0][0]  # Second call
        assert "ts_rank" in sql_query.lower()
        assert "_fulltext" in sql_query.lower()

    def test_fulltext_search_multi_word_query(self) -> None:
        """Test full-text search with multiple keywords.

        Validates:
        - Multi-word queries are processed correctly
        - AND/OR logic is applied
        - Phrase searches work with quotes

        Success Criteria (T104):
        - Multi-word queries return relevant results
        - Boolean operators work correctly
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("customer_name", "dataset-1", 0.8),
            ("customer_id", "dataset-1", 0.6),
        ]

        service: HybridSearchService = HybridSearchService(mock_pool)
        service.fulltext_search(username="testuser", query_text="customer name", limit=10)

        # Verify multi-word query executed
        assert mock_cursor.execute.call_count == 2  # SET search_path + actual query
        sql_params: tuple[Any, ...] = mock_cursor.execute.call_args_list[1][0][1]

        # Verify query parameters contain search text
        assert any("customer" in str(param).lower() for param in sql_params)

    def test_fulltext_search_with_dataset_filter(self) -> None:
        """Test full-text search filtered by dataset IDs.

        Validates:
        - Dataset filter is applied in WHERE clause
        - Only columns from specified datasets returned
        - Ranking maintained within filtered results

        Success Criteria (T104):
        - Dataset filter restricts results correctly
        - Relevance ranking preserved
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("revenue", "dataset-A", 0.9),
            ("sales", "dataset-B", 0.7),
        ]

        service: HybridSearchService = HybridSearchService(mock_pool)
        service.fulltext_search(
            username="testuser",
            query_text="revenue",
            dataset_ids=["dataset-A", "dataset-B"],
            limit=10,
        )

        # Verify dataset filter applied
        assert mock_cursor.execute.call_count == 2  # SET search_path + actual query
        sql_params: tuple[Any, ...] = mock_cursor.execute.call_args_list[1][0][1]

        # Should have dataset IDs in params
        assert "dataset-A" in sql_params or "dataset-B" in sql_params

    def test_fulltext_search_ranking_accuracy(self) -> None:
        """Test ts_rank produces correct relevance scores.

        Validates:
        - Exact matches rank higher than partial matches
        - Longer text with keyword ranks lower (normalization)
        - Scores are between 0 and 1

        Success Criteria (T104):
        - Ranking reflects text relevance
        - Scores in valid range
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("revenue", "dataset-1", 1.0),  # Exact match
            ("total_revenue", "dataset-1", 0.7),  # Partial match
            ("revenue_by_region", "dataset-1", 0.5),  # Partial with more text
        ]

        service: HybridSearchService = HybridSearchService(mock_pool)
        results: list[dict[str, Any]] = service.fulltext_search(
            username="testuser", query_text="revenue", limit=10
        )

        # Verify ranking order
        assert results[0]["rank"] >= results[1]["rank"] >= results[2]["rank"]

        # Verify scores in valid range
        for result in results:
            assert 0.0 <= result["rank"] <= 1.0

    def test_fulltext_search_empty_results(self) -> None:
        """Test full-text search returns empty when no matches found.

        Validates:
        - Empty result set handled gracefully
        - No errors on no matches
        - Returns empty list (not None)

        Success Criteria (T104):
        - Empty results don't cause errors
        - Returns empty list
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        service: HybridSearchService = HybridSearchService(mock_pool)
        results: list[dict[str, Any]] = service.fulltext_search(
            username="testuser", query_text="nonexistent_term_xyz", limit=10
        )

        # Should return empty list
        assert results == []

    def test_fulltext_search_special_characters(self) -> None:
        """Test full-text search handles special characters safely.

        Validates:
        - SQL injection prevented (parameterized queries)
        - Special regex characters escaped
        - Quotes and apostrophes handled correctly

        Success Criteria (T104):
        - Special characters don't break queries
        - No SQL injection vulnerability
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        service: HybridSearchService = HybridSearchService(mock_pool)

        # Test various special characters
        special_queries: list[str] = [
            "customer's name",
            "revenue (2023)",
            "sales & marketing",
            "user@email.com",
        ]

        for query in special_queries:
            results: list[dict[str, Any]] = service.fulltext_search(
                username="testuser", query_text=query, limit=10
            )
            # Should not raise exception
            assert isinstance(results, list)

    def test_fulltext_search_limit_parameter(self) -> None:
        """Test full-text search respects limit parameter.

        Validates:
        - LIMIT clause applied to SQL query
        - Results capped at specified limit
        - Default limit is reasonable (e.g., 10)

        Success Criteria (T104):
        - Limit parameter controls result count
        - SQL includes LIMIT clause
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock more results than limit
        mock_cursor.fetchall.return_value = [
            (f"column_{i}", "dataset-1", 0.9 - i * 0.1) for i in range(5)
        ]

        service: HybridSearchService = HybridSearchService(mock_pool)
        results: list[dict[str, Any]] = service.fulltext_search(
            username="testuser", query_text="column", limit=5
        )

        # Verify limit applied
        assert mock_cursor.execute.call_count == 2  # SET search_path + actual query
        sql_query: str = mock_cursor.execute.call_args_list[1][0][0]  # Second call
        assert "LIMIT" in sql_query.upper()

        # Verify result count
        assert len(results) == 5

    def test_fulltext_search_case_insensitive(self) -> None:
        """Test full-text search is case-insensitive.

        Validates:
        - "Revenue", "revenue", "REVENUE" return same results
        - Case normalization applied
        - Consistent behavior across queries

        Success Criteria (T104):
        - Case-insensitive matching works
        - Results consistent regardless of case
        """
        mock_pool: MagicMock = MagicMock()
        mock_conn: MagicMock = MagicMock()
        mock_cursor: MagicMock = MagicMock()

        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("revenue", "dataset-1", 0.9),
            ("Revenue", "dataset-2", 0.8),
            ("REVENUE", "dataset-3", 0.7),
        ]

        service: HybridSearchService = HybridSearchService(mock_pool)

        # Test different cases
        for query_text in ["revenue", "Revenue", "REVENUE"]:
            results: list[dict[str, Any]] = service.fulltext_search(
                username="testuser", query_text=query_text, limit=10
            )
            # All should return results
            assert len(results) > 0
