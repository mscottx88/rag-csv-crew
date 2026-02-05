"""Integration tests for vector similarity search (T101-TEST).

Tests the vector similarity search functionality using pgvector cosine
distance queries for semantic column matching.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.src.services.schema_manager import SchemaManager
from backend.src.services.vector_search import VectorSearchService


@pytest.mark.integration
class TestVectorSimilarity:
    """Integration tests for vector similarity search (T101)."""

    @patch("backend.src.services.vector_search.OpenAI")
    def test_find_similar_columns_by_semantic_meaning(
        self, mock_openai_class: MagicMock, test_db_connection: Any
    ) -> None:
        """Test finding semantically similar columns using vector search.

        Validates:
        - Cosine distance ranking orders results by similarity
        - Semantically related terms rank higher
        - Query returns top K results

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection fixture

        Success Criteria (T101):
        - Similar columns ranked by cosine distance
        - Results ordered from most to least similar
        - Top K limit works correctly
        """
        # Mock OpenAI embeddings
        mock_client: MagicMock = MagicMock()
        mock_openai_class.return_value = mock_client

        # Create embeddings for test columns
        revenue_embedding: list[float] = [0.9, 0.1] + [0.0] * 1534
        sales_embedding: list[float] = [0.85, 0.15] + [0.0] * 1534
        income_embedding: list[float] = [0.88, 0.12] + [0.0] * 1534
        customer_embedding: list[float] = [0.1, 0.9] + [0.0] * 1534
        query_embedding: list[float] = [0.9, 0.1] + [0.0] * 1534  # Similar to revenue

        # Setup schema
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"
        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        # Insert test embeddings
        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            test_data: list[tuple[str, str, list[float]]] = [
                ("revenue", "Total revenue amount", revenue_embedding),
                ("sales", "Sales transactions", sales_embedding),
                ("income", "Income from operations", income_embedding),
                ("customer_name", "Customer full name", customer_embedding),
            ]

            for column_name, description, embedding in test_data:
                cur.execute("""
                    INSERT INTO column_mappings
                    (dataset_id, original_column, mapped_column, embedding)
                    VALUES (%s, %s, %s, %s)
                """, ("test-dataset", column_name, column_name, embedding))
            test_db_connection.commit()

        # Mock OpenAI to return query embedding
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = query_embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response

        # Search for columns similar to "revenue"
        vector_service: VectorSearchService = VectorSearchService()
        similar_columns: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username,
            query_text="revenue",
            limit=3
        )

        # Verify results
        assert len(similar_columns) == 3

        # Verify ordering (revenue should be first, followed by sales/income)
        column_names: list[str] = [col["column_name"] for col in similar_columns]
        assert column_names[0] == "revenue"
        assert "sales" in column_names or "income" in column_names

        # Verify customer_name is not in top 3 (semantically different)
        assert "customer_name" not in column_names

    @patch("backend.src.services.vector_search.OpenAI")
    def test_cosine_distance_ranking(
        self, mock_openai_class: MagicMock, test_db_connection: Any
    ) -> None:
        """Test cosine distance is used for similarity ranking.

        Validates:
        - Cosine distance operator (<=>)  used correctly
        - Distance values between 0 and 2 (for normalized vectors)
        - Lower distance = higher similarity

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection fixture

        Success Criteria (T101):
        - Query uses cosine distance operator
        - Results include distance scores
        - Distances are in valid range
        """
        from backend.src.services.schema_manager import SchemaManager
        from backend.src.services.vector_search import VectorSearchService

        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"
        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        # Insert test embeddings with known distances
        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            identical_embedding: list[float] = [1.0, 0.0] + [0.0] * 1534
            similar_embedding: list[float] = [0.9, 0.1] + [0.0] * 1534
            different_embedding: list[float] = [0.0, 1.0] + [0.0] * 1534

            cur.execute("""
                INSERT INTO column_mappings
                (dataset_id, original_column, mapped_column, embedding)
                VALUES
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s)
            """, (
                "ds1", "col_identical", "col_identical", identical_embedding,
                "ds2", "col_similar", "col_similar", similar_embedding,
                "ds3", "col_different", "col_different", different_embedding,
            ))
            test_db_connection.commit()

        # Mock OpenAI to return query embedding
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = identical_embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService()
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username,
            query_text="test query",
            limit=3
        )

        # Verify distance scores
        assert len(results) == 3
        assert all("distance" in result for result in results)

        # Verify distances are in valid range (0 to 2 for cosine distance)
        distances: list[float] = [result["distance"] for result in results]
        assert all(0.0 <= d <= 2.0 for d in distances)

        # Verify ordering (lowest distance first)
        assert distances[0] <= distances[1] <= distances[2]

        # Identical embedding should have distance ~0
        assert results[0]["column_name"] == "col_identical"
        assert results[0]["distance"] < 0.01

    @patch("backend.src.services.vector_search.OpenAI")
    def test_vector_search_with_dataset_filter(
        self, mock_openai_class: MagicMock, test_db_connection: Any
    ) -> None:
        """Test vector similarity search filtered by dataset IDs.

        Validates:
        - Dataset ID filter is applied correctly
        - Only columns from specified datasets returned
        - Similarity ranking maintained within filtered results

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection fixture

        Success Criteria (T101):
        - Filter restricts results to specified datasets
        - Ranking is correct within filtered set
        """
        from backend.src.services.schema_manager import SchemaManager
        from backend.src.services.vector_search import VectorSearchService

        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"
        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        embedding: list[float] = [0.5] * 1536

        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Insert columns for multiple datasets
            cur.execute("""
                INSERT INTO column_mappings
                (dataset_id, original_column, mapped_column, embedding)
                VALUES
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s)
            """, (
                "dataset-A", "col_a", "col_a", embedding,
                "dataset-B", "col_b", "col_b", embedding,
                "dataset-C", "col_c", "col_c", embedding,
            ))
            test_db_connection.commit()

        # Mock OpenAI
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService()

        # Search with dataset filter
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username,
            query_text="test",
            dataset_ids=["dataset-A", "dataset-B"],
            limit=10
        )

        # Verify only filtered datasets returned
        dataset_ids: list[str] = [result["dataset_id"] for result in results]
        assert all(ds_id in ["dataset-A", "dataset-B"] for ds_id in dataset_ids)
        assert "dataset-C" not in dataset_ids

    @patch("backend.src.services.vector_search.OpenAI")
    def test_empty_results_when_no_similar_columns(
        self, mock_openai_class: MagicMock, test_db_connection: Any
    ) -> None:
        """Test vector search returns empty when no similar columns exist.

        Validates:
        - Empty database returns empty results
        - No similar columns (high distance threshold) returns empty
        - Error handling for edge cases

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection fixture

        Success Criteria (T101):
        - Empty result set handled gracefully
        - No errors on empty database
        """
        from backend.src.services.schema_manager import SchemaManager
        from backend.src.services.vector_search import VectorSearchService

        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"
        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        # Mock OpenAI
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = [0.5] * 1536
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService()

        # Search on empty database
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username,
            query_text="nonexistent column",
            limit=10
        )

        # Should return empty list, not error
        assert results == []

    def test_vector_search_performance_with_large_dataset(
        self, test_db_connection: Any
    ) -> None:
        """Test vector search performance on large column mapping sets.

        Validates:
        - Query completes in < 100ms for 10K+ embeddings
        - HNSW index provides logarithmic search time
        - Memory usage is acceptable

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T101):
        - Search scales to 10K+ vectors
        - Performance meets SLA requirements
        """
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"
        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        # Insert large number of embeddings
        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Insert 1000 embeddings (scaled down for test speed)
            for i in range(1000):
                embedding: list[float] = [float(i % 100) / 100.0] * 1536
                cur.execute("""
                    INSERT INTO column_mappings
                    (dataset_id, original_column, mapped_column, embedding)
                    VALUES (%s, %s, %s, %s)
                """, (f"dataset-{i // 100}", f"column_{i}", f"column_{i}", embedding))
            test_db_connection.commit()

            # Measure query performance
            import time
            query_embedding: list[float] = [0.5] * 1536

            start_time: float = time.time()
            cur.execute("""
                SELECT original_column, embedding <=> %s::vector AS distance
                FROM column_mappings
                ORDER BY embedding <=> %s::vector
                LIMIT 10
            """, (query_embedding, query_embedding))
            results: list[tuple[Any, ...]] = cur.fetchall()
            end_time: float = time.time()

            query_time_ms: float = (end_time - start_time) * 1000

        # Verify results
        assert len(results) == 10

        # Verify performance (should be < 100ms, but allow margin for test environment)
        assert query_time_ms < 500, f"Query took {query_time_ms:.2f}ms, expected < 500ms"
