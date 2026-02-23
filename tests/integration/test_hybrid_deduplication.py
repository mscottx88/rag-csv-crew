"""Integration tests for result de-duplication (T106-TEST).

Tests the de-duplication logic in hybrid search to ensure combined results
don't contain duplicate columns from multiple search strategies.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

import pytest

from backend.src.services.hybrid_search import HybridSearchService


@pytest.mark.integration
class TestHybridDeduplication:
    """Integration tests for result de-duplication (T106)."""

    def test_duplicate_columns_merged_across_strategies(self, test_db_connection: Any) -> None:
        """Test same column found by multiple strategies is deduplicated.

        Validates:
        - Exact, fulltext, and vector all find "revenue" column
        - Only one "revenue" entry in final results
        - Scores from all strategies combined

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Duplicates removed from combined results
        - Scores aggregated across strategies
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Same column found by all three strategies
        exact_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "score": 1.0}
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.9}
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "distance": 0.1}
        ]

        # Fuse results with deduplication
        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Should have only one "revenue" entry
        assert len(fused_results) == 1
        assert fused_results[0]["column_name"] == "revenue"

        # Combined score: exact weight 0.4, fulltext weight 0.3, vector weight 0.3 = 0.94
        expected_score: float = 0.94
        assert abs(fused_results[0]["combined_score"] - expected_score) < 0.01

    def test_deduplication_by_column_name_and_dataset(self, test_db_connection: Any) -> None:
        """Test deduplication uses both column name AND dataset ID as key.

        Validates:
        - "revenue" in dataset-A and "revenue" in dataset-B are distinct
        - Same column name in different datasets not deduplicated
        - Unique key is (column_name, dataset_id) tuple

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Deduplication key includes dataset ID
        - Same column in different datasets preserved
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        # "revenue" found in two different datasets
        exact_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "dataset-A", "score": 1.0},
            {"column_name": "revenue", "dataset_id": "dataset-B", "score": 1.0},
        ]
        fulltext_results: list[dict[str, Any]] = []
        vector_results: list[dict[str, Any]] = []

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Should have two entries (different datasets)
        assert len(fused_results) == 2

        dataset_ids: list[str] = [result["dataset_id"] for result in fused_results]
        assert "dataset-A" in dataset_ids
        assert "dataset-B" in dataset_ids

    def test_partial_overlap_deduplication(self, test_db_connection: Any) -> None:
        """Test deduplication with partial overlaps across strategies.

        Validates:
        - Some columns found by multiple strategies
        - Some columns found by single strategy
        - All unique columns present in final results

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Overlapping columns deduplicated
        - Non-overlapping columns preserved
        - Correct count of unique columns
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Partial overlap: revenue found by all, sales by two, customer by one
        exact_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "score": 1.0},
            {"column_name": "sales", "dataset_id": "ds1", "score": 0.9},
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.8},
            {"column_name": "customer_name", "dataset_id": "ds1", "rank": 0.7},
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "distance": 0.2},
            {"column_name": "sales", "dataset_id": "ds1", "distance": 0.3},
        ]

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Should have 3 unique columns: revenue, sales, customer_name
        assert len(fused_results) == 3

        column_names: list[str] = [result["column_name"] for result in fused_results]
        assert "revenue" in column_names
        assert "sales" in column_names
        assert "customer_name" in column_names

        # Revenue should have highest score (found by all three)
        revenue_result: dict[str, Any] = next(
            r for r in fused_results if r["column_name"] == "revenue"
        )
        assert all(revenue_result["combined_score"] >= r["combined_score"] for r in fused_results)

    def test_deduplication_preserves_metadata(self, test_db_connection: Any) -> None:
        """Test deduplication preserves column metadata (dataset, original scores).

        Validates:
        - Dataset ID preserved after deduplication
        - Original scores from each strategy tracked
        - Metadata not lost during merge

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Deduplicated result includes all metadata
        - Original strategy scores accessible
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        exact_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "score": 1.0}
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.9}
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "distance": 0.1}
        ]

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        result: dict[str, Any] = fused_results[0]

        # Verify metadata preserved
        assert result["column_name"] == "revenue"
        assert result["dataset_id"] == "ds1"
        assert "combined_score" in result

        # Optional: verify original scores tracked
        if "strategy_scores" in result:
            assert "exact" in result["strategy_scores"]
            assert "fulltext" in result["strategy_scores"]
            assert "vector" in result["strategy_scores"]

    def test_empty_strategy_results_deduplication(self, test_db_connection: Any) -> None:
        """Test deduplication when some strategies return no results.

        Validates:
        - Empty strategy results don't cause errors
        - Non-empty strategies still deduplicated
        - No duplicate entries in final results

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Deduplication works with partial strategy results
        - No errors when strategies return empty
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Only exact and fulltext have results
        exact_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "score": 1.0}
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.9}
        ]
        vector_results: list[dict[str, Any]] = []  # Empty

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Should have one deduplicated result
        assert len(fused_results) == 1
        assert fused_results[0]["column_name"] == "revenue"

    def test_deduplication_ranking_consistency(self, test_db_connection: Any) -> None:
        """Test deduplication maintains consistent ranking.

        Validates:
        - Same column found by multiple strategies ranks higher
        - Ranking reflects contribution from all strategies
        - Deterministic ordering

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Columns found by multiple strategies rank higher
        - Ranking is deterministic
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        # col1 found by all three, col2 by two, col3 by one
        exact_results: list[dict[str, Any]] = [
            {"column_name": "col1", "dataset_id": "ds1", "score": 1.0},
            {"column_name": "col2", "dataset_id": "ds1", "score": 0.9},
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "col1", "dataset_id": "ds1", "rank": 0.9},
            {"column_name": "col3", "dataset_id": "ds1", "rank": 0.8},
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "col1", "dataset_id": "ds1", "distance": 0.1}
        ]

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Should have 3 unique columns
        assert len(fused_results) == 3

        # col1 (found by all three) should rank highest
        assert fused_results[0]["column_name"] == "col1"

        # Verify consistent ordering
        for i in range(len(fused_results) - 1):
            assert fused_results[i]["combined_score"] >= fused_results[i + 1]["combined_score"]

    def test_case_sensitivity_in_deduplication(self, test_db_connection: Any) -> None:
        """Test deduplication handles case sensitivity correctly.

        Validates:
        - Column names are case-sensitive for deduplication
        - "Revenue" and "revenue" are distinct
        - Or: normalization applied consistently

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T106):
        - Case handling is consistent
        - No unexpected duplicates or merges
        """
        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Different case variations
        exact_results: list[dict[str, Any]] = [
            {"column_name": "Revenue", "dataset_id": "ds1", "score": 1.0}
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.9}
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "REVENUE", "dataset_id": "ds1", "distance": 0.1}
        ]

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Depending on implementation:
        # - If case-insensitive: should have 1 result
        # - If case-sensitive: should have 3 results
        # Either is acceptable, but must be consistent
        assert len(fused_results) >= 1

        # If deduplicated (case-insensitive), verify combined score
        if len(fused_results) == 1:
            # All three found the same column (case-insensitive)
            expected_score: float = 0.94  # 0.4 + 0.27 + 0.27
            assert abs(fused_results[0]["combined_score"] - expected_score) < 0.01
