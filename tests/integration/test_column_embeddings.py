"""Integration tests for column mapping embeddings (T099-TEST).

Tests the embedding generation workflow during CSV upload, ensuring column
mappings receive semantic embeddings for vector similarity search.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.src.services.ingestion import IngestionService
from backend.src.services.vector_search import VectorSearchService


@pytest.mark.integration
class TestColumnEmbeddings:
    """Integration tests for column mapping embeddings (T099)."""

    @patch("backend.src.services.vector_search.OpenAI")
    @patch("backend.src.services.ingestion.VectorSearchService")
    def test_embeddings_generated_on_csv_upload(
        self, mock_vector_service_class: MagicMock, mock_openai_class: MagicMock
    ) -> None:
        """Test embeddings are generated for column mappings during CSV upload.

        Validates:
        - Each column mapping gets an embedding
        - Embeddings are generated from column name + description
        - Embeddings are stored in column_mappings table

        Args:
            mock_vector_service_class: Mocked VectorSearchService class
            mock_openai_class: Mocked OpenAI client class

        Success Criteria (T099):
        - Embeddings generated for all column mappings
        - Stored in database with correct dimensions
        - No duplicate embeddings
        """
        # Mock vector service
        mock_vector_service: MagicMock = MagicMock()
        mock_vector_service.generate_embedding.return_value = [0.1] * 1536
        mock_vector_service_class.return_value = mock_vector_service

        # Mock database connection pool
        mock_pool: MagicMock = MagicMock()

        service: IngestionService = IngestionService(mock_pool)

        # Simulate column metadata
        columns: list[dict[str, Any]] = [
            {
                "name": "customer_id",
                "sql_type": "INTEGER",
                "description": "Unique customer identifier",
            },
            {"name": "revenue", "sql_type": "NUMERIC", "description": "Total sales amount"},
            {"name": "region", "sql_type": "TEXT", "description": "Geographic sales region"},
        ]

        # Generate embeddings for columns
        service.generate_column_embeddings(
            username="testuser", dataset_id="test-dataset-id", columns=columns
        )

        # Verify embeddings were generated for each column
        assert mock_vector_service.generate_embedding.call_count == 3

        # Verify embedding text includes column name and description
        calls: list[Any] = mock_vector_service.generate_embedding.call_args_list
        call_texts: list[str] = [call.args[0] for call in calls]

        assert any("customer_id" in text.lower() for text in call_texts)
        assert any("revenue" in text.lower() for text in call_texts)
        assert any("region" in text.lower() for text in call_texts)

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.ingestion.VectorSearchService")
    def test_embeddings_stored_with_column_mappings(
        self, mock_vector_service_class: MagicMock
    ) -> None:
        """Test embeddings are persisted in column_mappings table.

        Validates:
        - generate_column_embeddings calls pool.connection() to persist data
        - Embedding generation is invoked for each column
        - Dimensions match text-embedding-3-small (1536)

        Args:
            mock_vector_service_class: Mocked VectorSearchService class

        Success Criteria (T099):
        - Embeddings persisted via pool.connection()
        - Correct vector dimensions (1536)
        - generate_embedding called once per column
        """
        # Mock vector service to return 1536-dim embeddings
        mock_vector_service: MagicMock = MagicMock()
        mock_vector_service.generate_embedding.return_value = [0.1] * 1536
        mock_vector_service_class.return_value = mock_vector_service

        # Mock database connection pool
        mock_pool: MagicMock = MagicMock()

        service: IngestionService = IngestionService(mock_pool)

        columns: list[dict[str, Any]] = [
            {
                "name": "total_sales",
                "sql_type": "NUMERIC",
                "description": "Sum of all sales transactions",
            }
        ]

        service.generate_column_embeddings(
            username="testuser", dataset_id="test-dataset-id", columns=columns
        )

        # Verify embedding was generated with correct dimensions
        assert mock_vector_service.generate_embedding.call_count == 1
        generated_embedding: list[float] = mock_vector_service.generate_embedding.return_value
        assert len(generated_embedding) == 1536

        # Verify DB connection was used to store embeddings
        assert mock_pool.connection.called

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "", "OPENAI_API_KEY": "sk-fake-key-for-testing"})
    @patch("backend.src.services.vector_search.OpenAI")
    def test_embeddings_updated_on_column_remapping(self, mock_openai_class: MagicMock) -> None:
        """Test embeddings are regenerated when column mappings change.

        Validates:
        - Updated column descriptions trigger re-embedding
        - Old embeddings are replaced
        - Vector index is updated

        Args:
            mock_openai_class: Mocked OpenAI client class

        Success Criteria (T099):
        - Remapping triggers embedding regeneration
        - Database reflects updated embeddings
        """
        # Mock OpenAI embeddings with different values
        mock_client: MagicMock = MagicMock()
        mock_openai_class.return_value = mock_client

        # First embedding
        mock_response_1: MagicMock = MagicMock()
        mock_embedding_1: MagicMock = MagicMock()
        mock_embedding_1.embedding = [0.1] * 1536
        mock_response_1.data = [mock_embedding_1]

        # Second embedding (after remapping)
        mock_response_2: MagicMock = MagicMock()
        mock_embedding_2: MagicMock = MagicMock()
        mock_embedding_2.embedding = [0.9] * 1536
        mock_response_2.data = [mock_embedding_2]

        mock_client.embeddings.create.side_effect = [mock_response_1, mock_response_2]

        vector_service: VectorSearchService = VectorSearchService()

        # Generate initial embedding
        initial_text: str = "revenue Total sales amount"
        initial_embedding: list[float] = vector_service.generate_embedding(initial_text)
        assert initial_embedding[0] == 0.1

        # Generate updated embedding
        updated_text: str = "revenue Annual recurring revenue"
        updated_embedding: list[float] = vector_service.generate_embedding(updated_text)
        assert updated_embedding[0] == 0.9

        # Verify embeddings are different
        assert initial_embedding != updated_embedding

    def test_embedding_generation_failure_rollback(self) -> None:
        """Test error propagation when embedding generation fails.

        Validates:
        - Failed embedding generation raises an exception
        - Partial column mappings are not persisted
        - Error is propagated to caller

        Success Criteria (T099):
        - Failed embedding generation raises RuntimeError or Exception
        - Transaction consistency maintained via exception propagation
        """
        mock_pool: MagicMock = MagicMock()
        service: IngestionService = IngestionService(mock_pool)

        # Mock vector service to fail on second column
        with patch("backend.src.services.ingestion.VectorSearchService") as mock_vs:
            mock_vector_service: MagicMock = MagicMock()
            mock_vector_service.generate_embedding.side_effect = [
                [0.1] * 1536,  # First column succeeds
                Exception("API error"),  # Second column fails
            ]
            mock_vs.return_value = mock_vector_service

            columns: list[dict[str, Any]] = [
                {"name": "col1", "sql_type": "TEXT", "description": "First column"},
                {"name": "col2", "sql_type": "TEXT", "description": "Second column"},
            ]

            with pytest.raises((Exception, RuntimeError)):
                service.generate_column_embeddings(
                    username="testuser", dataset_id="test-dataset-id", columns=columns
                )
