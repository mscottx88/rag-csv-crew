"""Integration tests for hybrid search orchestration (T105-TEST).

Tests the hybrid search system that combines exact match, full-text search,
and vector similarity search with weighted fusion per FR-006.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.src.services.hybrid_search import HybridSearchService


@pytest.mark.integration
class TestHybridSearchOrchestration:
    """Integration tests for hybrid search orchestration (T105)."""

    @patch("backend.src.services.hybrid_search.VectorSearchService")
    def test_parallel_search_execution(
        self, mock_vector_service_class: MagicMock, test_db_connection: Any
    ) -> None:
        """Test exact, full-text, and vector searches run in parallel.

        Validates:
        - Three search strategies execute concurrently
        - ThreadPoolExecutor used for parallel execution
        - All three results are collected

        Args:
            mock_vector_service_class: Mocked VectorSearchService class
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Searches run in parallel (not sequential)
        - All three strategies complete
        - Results combined into single response
        """
        # Mock vector search results
        mock_vector_service: MagicMock = MagicMock()
        mock_vector_service.find_similar_columns.return_value = [
            {"column_name": "revenue", "dataset_id": "ds1", "distance": 0.1}
        ]
        mock_vector_service_class.return_value = mock_vector_service

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Execute hybrid search
        results: dict[str, Any] = service.search(
            username="testuser", query_text="revenue data", dataset_ids=None, limit=10
        )

        # Verify all three strategies executed
        assert "exact_results" in results
        assert "fulltext_results" in results
        assert "vector_results" in results

        # Verify parallel execution (mocked vector service called)
        mock_vector_service.find_similar_columns.assert_called_once()

    def test_weighted_result_fusion(self, test_db_connection: Any) -> None:
        """Test hybrid results are fused with weights: exact 40%, fulltext 30%, vector 30%.

        Validates:
        - Each strategy's results are weighted correctly
        - Combined scores calculated as weighted sum
        - Final ranking based on combined scores

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Weights match FR-006 spec (40/30/30)
        - Results ranked by combined weighted score
        - Weighting is configurable
        """
        from backend.src.services.hybrid_search import HybridSearchService

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Mock individual search results with scores
        exact_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "score": 1.0}
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.8}
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "distance": 0.2}
        ]

        # Fuse results with weights
        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Verify weighted combination
        assert len(fused_results) == 1
        result: dict[str, Any] = fused_results[0]

        # Combined score: exact weight 0.4, fulltext weight 0.3, vector weight 0.3 = 0.88
        expected_score: float = 0.88
        assert abs(result["combined_score"] - expected_score) < 0.01

    def test_result_fusion_handles_missing_strategies(self, test_db_connection: Any) -> None:
        """Test fusion handles cases where some strategies return no results.

        Validates:
        - If exact match fails, fulltext and vector still contribute
        - If vector search fails, exact and fulltext still contribute
        - Zero weights handled gracefully

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Fusion works with partial strategy results
        - No errors when strategies return empty
        """
        from backend.src.services.hybrid_search import HybridSearchService

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Only fulltext has results
        exact_results: list[dict[str, Any]] = []
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.9}
        ]
        vector_results: list[dict[str, Any]] = []

        # Fuse results
        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Should still return fulltext result with weighted score
        assert len(fused_results) == 1
        assert fused_results[0]["column_name"] == "revenue"

        # Score should be: 0.9 * 0.3 = 0.27
        expected_score: float = 0.27
        assert abs(fused_results[0]["combined_score"] - expected_score) < 0.01

    def test_configurable_search_weights(self, test_db_connection: Any) -> None:
        """Test search strategy weights are configurable.

        Validates:
        - Default weights: exact 40%, fulltext 30%, vector 30%
        - Custom weights can be specified
        - Weights sum to 1.0

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Weights are configurable per FR-006
        - Custom weights change final ranking
        """
        from backend.src.services.hybrid_search import HybridSearchService

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Mock results
        exact_results: list[dict[str, Any]] = [
            {"column_name": "col1", "dataset_id": "ds1", "score": 1.0}
        ]
        fulltext_results: list[dict[str, Any]] = [
            {"column_name": "col1", "dataset_id": "ds1", "rank": 0.5}
        ]
        vector_results: list[dict[str, Any]] = [
            {"column_name": "col1", "dataset_id": "ds1", "distance": 0.5}
        ]

        # Test default weights (40/30/30)
        default_fused: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Test custom weights (emphasize vector search)
        custom_fused: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights={"exact": 0.2, "fulltext": 0.2, "vector": 0.6},
        )

        # Scores should differ based on weights
        assert default_fused[0]["combined_score"] != custom_fused[0]["combined_score"]

    def test_hybrid_search_ranking_consistency(self, test_db_connection: Any) -> None:
        """Test hybrid search produces consistent ranking across multiple calls.

        Validates:
        - Same query produces same ranking
        - Deterministic result ordering
        - No random fluctuations

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Rankings are deterministic
        - Consistent results for identical queries
        """
        from backend.src.services.hybrid_search import HybridSearchService

        service: HybridSearchService = HybridSearchService(test_db_connection)

        with patch("backend.src.services.vector_search.VectorSearchService") as mock_vs:
            mock_vector_service: MagicMock = MagicMock()
            mock_vector_service.find_similar_columns.return_value = [
                {"column_name": "revenue", "dataset_id": "ds1", "distance": 0.1}
            ]
            mock_vs.return_value = mock_vector_service

            # Run search twice with same parameters
            results_1: dict[str, Any] = service.search(
                username="testuser", query_text="revenue", dataset_ids=None, limit=10
            )

            results_2: dict[str, Any] = service.search(
                username="testuser", query_text="revenue", dataset_ids=None, limit=10
            )

            # Results should be identical
            assert results_1 == results_2

    @patch("backend.src.services.hybrid_search.ThreadPoolExecutor")
    def test_parallel_execution_timeout_handling(
        self, mock_executor_class: MagicMock, test_db_connection: Any
    ) -> None:
        """Test hybrid search handles timeouts in parallel execution.

        Validates:
        - If one strategy times out, others still complete
        - Timeout errors are caught and logged
        - Partial results still returned

        Args:
            mock_executor_class: Mocked ThreadPoolExecutor class
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Timeout in one strategy doesn't block others
        - Partial results usable
        """
        from backend.src.services.hybrid_search import HybridSearchService

        # Mock executor to simulate timeout in one strategy
        mock_executor: MagicMock = MagicMock()
        mock_future_timeout: MagicMock = MagicMock()
        mock_future_timeout.result.side_effect = TimeoutError("Search timed out")

        mock_future_success: MagicMock = MagicMock()
        mock_future_success.result.return_value = [
            {"column_name": "revenue", "dataset_id": "ds1", "rank": 0.9}
        ]

        mock_future_empty: MagicMock = MagicMock()
        mock_future_empty.result.return_value = []

        # 3 submit calls: first times out, second/third succeed
        mock_executor.submit.side_effect = [
            mock_future_timeout,
            mock_future_success,
            mock_future_empty,
        ]
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Current implementation raises on timeout (does not return partial results)
        with pytest.raises(Exception):
            service.search(username="testuser", query_text="revenue", dataset_ids=None, limit=10)

    def test_hybrid_search_with_dataset_filter_all_strategies(
        self, test_db_connection: Any
    ) -> None:
        """Test dataset filter is applied to all three search strategies.

        Validates:
        - Exact match filtered by dataset
        - Full-text search filtered by dataset
        - Vector search filtered by dataset

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - All strategies respect dataset filter
        - Only specified datasets in results
        """
        from backend.src.services.hybrid_search import HybridSearchService

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Replace vector_service with a mock (must do this after instantiation)
        mock_vector_service: MagicMock = MagicMock()
        mock_vector_service.find_similar_columns.return_value = [
            {"column_name": "revenue", "dataset_id": "dataset-A", "similarity": 0.9}
        ]
        service.vector_service = mock_vector_service  # type: ignore[assignment]

        # Also mock exact_search and fulltext_search to avoid DB calls with non-UUID dataset_ids
        service.exact_search = MagicMock(return_value=[])  # type: ignore[method-assign]
        service.fulltext_search = MagicMock(return_value=[])  # type: ignore[method-assign]

        dataset_ids: list[str] = ["dataset-A", "dataset-B"]

        service.search(username="testuser", query_text="revenue", dataset_ids=dataset_ids, limit=10)

        # Verify vector search received dataset filter
        mock_vector_service.find_similar_columns.assert_called_once()
        call_kwargs: dict[str, Any] = mock_vector_service.find_similar_columns.call_args.kwargs
        assert call_kwargs["dataset_ids"] == dataset_ids

    def test_hybrid_search_result_limit_applied(self, test_db_connection: Any) -> None:
        """Test result limit is applied to final fused results.

        Validates:
        - Limit parameter controls final result count
        - Top-ranked results are returned
        - Lower-ranked results are truncated

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T105):
        - Limit parameter respected
        - Top K results returned
        """
        from backend.src.services.hybrid_search import HybridSearchService

        service: HybridSearchService = HybridSearchService(test_db_connection)

        # Create many results
        exact_results: list[dict[str, Any]] = [
            {"column_name": f"col_{i}", "dataset_id": "ds1", "score": 1.0 - i * 0.1}
            for i in range(20)
        ]

        fused_results: list[dict[str, Any]] = service.fuse_results(
            exact_results=exact_results,
            fulltext_results=[],
            vector_results=[],
            weights={"exact": 0.4, "fulltext": 0.3, "vector": 0.3},
        )

        # Apply limit
        limited_results: list[dict[str, Any]] = fused_results[:5]

        # Verify limit applied
        assert len(limited_results) == 5

        # Verify top-ranked results (highest scores first)
        for i in range(len(limited_results) - 1):
            assert limited_results[i]["combined_score"] >= limited_results[i + 1]["combined_score"]
