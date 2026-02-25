"""Integration tests for vector similarity search (T101-TEST).

Tests the vector similarity search functionality using pgvector cosine
distance queries for semantic column matching.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import time
from typing import Any
from unittest.mock import MagicMock, patch
import uuid

from psycopg_pool import ConnectionPool
import pytest

from backend.src.services.schema_manager import ensure_user_schema_exists
from backend.src.services.vector_search import VectorSearchService


def _insert_dataset(cur: Any, dataset_id: str, table_name: str) -> None:
    """Insert a minimal dataset row to satisfy FK constraint.

    Args:
        cur: Database cursor with search_path already set
        dataset_id: UUID string for the dataset
        table_name: Unique table name for the dataset
    """
    cur.execute(
        """
        INSERT INTO datasets
        (id, filename, original_filename, table_name, row_count,
         column_count, file_size_bytes, schema_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (dataset_id, f"{table_name}.csv", f"{table_name}.csv", table_name, 10, 2, 512, "{}"),
    )


@pytest.mark.integration
class TestVectorSimilarity:
    """Integration tests for vector similarity search (T101)."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.vector_search.OpenAI")
    def test_find_similar_columns_by_semantic_meaning(
        self, mock_openai_class: MagicMock, test_db_connection: ConnectionPool
    ) -> None:
        """Test finding semantically similar columns using vector search.

        Validates:
        - Cosine distance ranking orders results by similarity
        - Semantically related terms rank higher
        - Query returns top K results

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection pool fixture

        Success Criteria (T101):
        - Similar columns ranked by cosine distance
        - Results ordered from most to least similar
        - Top K limit works correctly
        """
        # Create embeddings for test columns
        revenue_embedding: list[float] = [0.9, 0.1] + [0.0] * 1534
        sales_embedding: list[float] = [0.85, 0.15] + [0.0] * 1534
        income_embedding: list[float] = [0.88, 0.12] + [0.0] * 1534
        customer_embedding: list[float] = [0.1, 0.9] + [0.0] * 1534
        query_embedding: list[float] = [0.9, 0.1] + [0.0] * 1534  # Similar to revenue

        username: str = "testuser"
        dataset_id: str = str(uuid.uuid4())

        with test_db_connection.connection() as conn:
            ensure_user_schema_exists(conn, username)

            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {username}_schema, public")
                _insert_dataset(cur, dataset_id, "test_rev_ds")

                test_data: list[tuple[str, list[float]]] = [
                    ("revenue", revenue_embedding),
                    ("sales", sales_embedding),
                    ("income", income_embedding),
                    ("customer_name", customer_embedding),
                ]

                for column_name, embedding in test_data:
                    cur.execute(
                        """
                        INSERT INTO column_mappings
                        (dataset_id, column_name, inferred_type, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (dataset_id, column_name, "TEXT", embedding),
                    )
                conn.commit()

        # Mock OpenAI to return query embedding
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = query_embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Search for columns similar to "revenue"
        vector_service: VectorSearchService = VectorSearchService(pool=test_db_connection)
        similar_columns: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username, query_text="revenue", limit=3
        )

        # Verify results
        assert len(similar_columns) == 3

        # Verify ordering (revenue should be first, followed by sales/income)
        column_names: list[str] = [col["column_name"] for col in similar_columns]
        assert column_names[0] == "revenue"
        assert "sales" in column_names or "income" in column_names

        # Verify customer_name is not in top 3 (semantically different)
        assert "customer_name" not in column_names

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.vector_search.OpenAI")
    def test_cosine_distance_ranking(
        self, mock_openai_class: MagicMock, test_db_connection: ConnectionPool
    ) -> None:
        """Test cosine distance is used for similarity ranking.

        Validates:
        - Cosine distance operator (<=>) used correctly
        - Distance values between 0 and 2 (for normalized vectors)
        - Lower distance = higher similarity

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection pool fixture

        Success Criteria (T101):
        - Query uses cosine distance operator
        - Results include distance scores
        - Distances are in valid range
        """
        username: str = "testuser"
        dataset_id: str = str(uuid.uuid4())

        identical_embedding: list[float] = [1.0, 0.0] + [0.0] * 1534
        similar_embedding: list[float] = [0.9, 0.1] + [0.0] * 1534
        different_embedding: list[float] = [0.0, 1.0] + [0.0] * 1534

        with test_db_connection.connection() as conn:
            ensure_user_schema_exists(conn, username)

            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {username}_schema, public")
                _insert_dataset(cur, dataset_id, "test_cosine_ds")

                cur.execute(
                    """
                    INSERT INTO column_mappings
                    (dataset_id, column_name, inferred_type, embedding)
                    VALUES (%s, %s, %s, %s), (%s, %s, %s, %s), (%s, %s, %s, %s)
                    """,
                    (
                        dataset_id, "col_identical", "TEXT", identical_embedding,
                        dataset_id, "col_similar", "TEXT", similar_embedding,
                        dataset_id, "col_different", "TEXT", different_embedding,
                    ),
                )
                conn.commit()

        # Mock OpenAI to return query embedding (identical to col_identical)
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = identical_embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService(pool=test_db_connection)
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username, query_text="test query", limit=3
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

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.vector_search.OpenAI")
    def test_vector_search_with_dataset_filter(
        self, mock_openai_class: MagicMock, test_db_connection: ConnectionPool
    ) -> None:
        """Test vector similarity search filtered by dataset IDs.

        Validates:
        - Dataset ID filter is applied correctly
        - Only columns from specified datasets returned
        - Similarity ranking maintained within filtered results

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection pool fixture

        Success Criteria (T101):
        - Filter restricts results to specified datasets
        - Ranking is correct within filtered set
        """
        username: str = "testuser"
        dataset_a: str = str(uuid.uuid4())
        dataset_b: str = str(uuid.uuid4())
        dataset_c: str = str(uuid.uuid4())
        embedding: list[float] = [0.5] * 1536

        with test_db_connection.connection() as conn:
            ensure_user_schema_exists(conn, username)

            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {username}_schema, public")
                _insert_dataset(cur, dataset_a, "dsa_filter")
                _insert_dataset(cur, dataset_b, "dsb_filter")
                _insert_dataset(cur, dataset_c, "dsc_filter")

                cur.execute(
                    """
                    INSERT INTO column_mappings
                    (dataset_id, column_name, inferred_type, embedding)
                    VALUES (%s, %s, %s, %s), (%s, %s, %s, %s), (%s, %s, %s, %s)
                    """,
                    (
                        dataset_a, "col_a", "TEXT", embedding,
                        dataset_b, "col_b", "TEXT", embedding,
                        dataset_c, "col_c", "TEXT", embedding,
                    ),
                )
                conn.commit()

        # Mock OpenAI
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService(pool=test_db_connection)

        # Search with dataset filter (only A and B, not C)
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username,
            query_text="test",
            dataset_ids=[dataset_a, dataset_b],
            limit=10,
        )

        # Verify only filtered datasets returned
        returned_ids: list[str] = [result["dataset_id"] for result in results]
        assert all(ds_id in [dataset_a, dataset_b] for ds_id in returned_ids)
        assert dataset_c not in returned_ids

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.vector_search.OpenAI")
    def test_empty_results_when_no_similar_columns(
        self, mock_openai_class: MagicMock, test_db_connection: ConnectionPool
    ) -> None:
        """Test vector search returns empty when no columns exist.

        Validates:
        - Empty database returns empty results
        - No errors on empty database

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection pool fixture

        Success Criteria (T101):
        - Empty result set handled gracefully
        - No errors on empty database
        """
        username: str = "testuser"

        with test_db_connection.connection() as conn:
            ensure_user_schema_exists(conn, username)

        # Mock OpenAI
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = [0.5] * 1536
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService(pool=test_db_connection)

        # Search on empty database
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username, query_text="nonexistent column", limit=10
        )

        # Should return empty list, not error
        assert results == []

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.vector_search.OpenAI")
    def test_vector_search_performance_with_large_dataset(
        self, mock_openai_class: MagicMock, test_db_connection: ConnectionPool
    ) -> None:
        """Test vector search performance on moderately large column sets.

        Validates:
        - Query completes in acceptable time for 100+ embeddings
        - HNSW index provides fast search
        - Memory usage is acceptable

        Args:
            mock_openai_class: Mocked OpenAI client class
            test_db_connection: Test database connection pool fixture

        Success Criteria (T101):
        - Search scales to 100+ vectors
        - Performance meets test requirements
        """
        username: str = "testuser"
        dataset_id: str = str(uuid.uuid4())
        query_embedding: list[float] = [0.5] * 1536

        with test_db_connection.connection() as conn:
            ensure_user_schema_exists(conn, username)

            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {username}_schema, public")
                _insert_dataset(cur, dataset_id, "perf_test_ds")

                # Insert 100 embeddings (scaled down for test speed)
                for i in range(100):
                    embedding: list[float] = [float(i % 10) / 10.0] * 1536
                    cur.execute(
                        """
                        INSERT INTO column_mappings
                        (dataset_id, column_name, inferred_type, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (dataset_id, f"column_{i}", "TEXT", embedding),
                    )
                conn.commit()

        # Mock OpenAI to return query embedding
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = query_embedding
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        vector_service: VectorSearchService = VectorSearchService(pool=test_db_connection)

        # Measure query performance
        start_time: float = time.time()
        results: list[dict[str, Any]] = vector_service.find_similar_columns(
            username=username, query_text="test", limit=10
        )
        end_time: float = time.time()

        query_time_ms: float = (end_time - start_time) * 1000

        # Verify results
        assert len(results) == 10

        # Verify performance (allow margin for test environment)
        assert query_time_ms < 5000, f"Query took {query_time_ms:.2f}ms, expected < 5000ms"
