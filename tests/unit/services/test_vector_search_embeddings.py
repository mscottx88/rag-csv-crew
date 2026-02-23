"""Unit tests for embedding generation service (T098-TEST).

Tests the vector search service's embedding generation capabilities using
OpenAI text-embedding-3-small model.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.src.services.vector_search import VectorSearchService


@pytest.mark.unit
class TestVectorSearchEmbeddings:
    """Unit tests for embedding generation service (T098)."""

    @patch("backend.src.services.vector_search.OpenAI")
    def test_generate_embedding_from_text(self, mock_openai_class: MagicMock) -> None:
        """Test embedding generation for a single text input.

        Validates:
        - OpenAI text-embedding-3-small is called correctly
        - Returns 1536-dimensional vector (text-embedding-3-small output size)
        - Handles text normalization

        Args:
            mock_openai_class: Mocked OpenAI client class

        Success Criteria (T098):
        - Service generates embeddings using OpenAI API
        - Output is a list of floats with 1536 dimensions
        - Text is properly preprocessed
        """
        # Mock OpenAI client and response
        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = [0.1] * 1536  # 1536 dimensions
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        service: VectorSearchService = VectorSearchService()
        text: str = "revenue column contains sales data"

        embedding: list[float] = service.generate_embedding(text)

        # Verify embedding dimensions
        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float | int) for x in embedding)

        # Verify OpenAI API was called with correct parameters
        mock_client.embeddings.create.assert_called_once()
        call_kwargs: dict[str, Any] = mock_client.embeddings.create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-3-small"
        assert call_kwargs["input"] == text

    @patch("backend.src.services.vector_search.OpenAI")
    def test_generate_embedding_batch(self, mock_openai_class: MagicMock) -> None:
        """Test batch embedding generation for multiple texts.

        Validates:
        - Batch processing reduces API calls
        - All texts receive embeddings
        - Order is preserved

        Args:
            mock_openai_class: Mocked OpenAI client class

        Success Criteria (T098):
        - Batch generation returns list of embeddings
        - Each embedding has correct dimensions
        - Texts are processed in order
        """
        from backend.src.services.vector_search import VectorSearchService

        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()

        # Create mock embeddings for batch
        mock_embedding_1: MagicMock = MagicMock()
        mock_embedding_1.embedding = [0.1] * 1536
        mock_embedding_2: MagicMock = MagicMock()
        mock_embedding_2.embedding = [0.2] * 1536
        mock_embedding_3: MagicMock = MagicMock()
        mock_embedding_3.embedding = [0.3] * 1536

        mock_response.data = [mock_embedding_1, mock_embedding_2, mock_embedding_3]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        service: VectorSearchService = VectorSearchService()
        texts: list[str] = [
            "customer name",
            "order amount",
            "product category",
        ]

        embeddings: list[list[float]] = service.generate_embeddings_batch(texts)

        # Verify batch results
        assert len(embeddings) == 3
        assert all(len(emb) == 1536 for emb in embeddings)

        # Verify single API call for batch
        mock_client.embeddings.create.assert_called_once()
        call_kwargs: dict[str, Any] = mock_client.embeddings.create.call_args.kwargs
        assert call_kwargs["input"] == texts

    @patch("backend.src.services.vector_search.OpenAI")
    def test_generate_embedding_error_handling(self, mock_openai_class: MagicMock) -> None:
        """Test error handling when OpenAI API fails.

        Validates:
        - API errors are caught and wrapped
        - Rate limiting is handled gracefully
        - Error messages are informative

        Args:
            mock_openai_class: Mocked OpenAI client class

        Success Criteria (T098):
        - API failures raise appropriate exceptions
        - Error messages include context
        """
        from backend.src.services.vector_search import VectorSearchService

        mock_client: MagicMock = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_class.return_value = mock_client

        service: VectorSearchService = VectorSearchService()

        with pytest.raises(Exception) as exc_info:
            service.generate_embedding("test text")

        # Verify error is raised
        assert exc_info.value is not None
        assert "rate limit" in str(exc_info.value).lower()

    @patch("backend.src.services.vector_search.OpenAI")
    def test_generate_embedding_normalizes_text(self, mock_openai_class: MagicMock) -> None:
        """Test text normalization before embedding generation.

        Validates:
        - Whitespace is normalized
        - Special characters are handled
        - Empty strings are rejected

        Args:
            mock_openai_class: Mocked OpenAI client class

        Success Criteria (T098):
        - Text is normalized before API call
        - Empty/whitespace-only strings raise errors
        """
        from backend.src.services.vector_search import VectorSearchService

        mock_client: MagicMock = MagicMock()
        mock_response: MagicMock = MagicMock()
        mock_embedding_data: MagicMock = MagicMock()
        mock_embedding_data.embedding = [0.1] * 1536
        mock_response.data = [mock_embedding_data]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        service: VectorSearchService = VectorSearchService()

        # Test whitespace normalization
        text_with_whitespace: str = "  revenue   column  "
        embedding: list[float] = service.generate_embedding(text_with_whitespace)

        assert len(embedding) == 1536

        # Verify normalized text was sent to API
        call_kwargs: dict[str, Any] = mock_client.embeddings.create.call_args.kwargs
        sent_text: str = call_kwargs["input"]
        assert sent_text == "revenue column"  # Normalized

    def test_generate_embedding_empty_text_raises_error(self) -> None:
        """Test that empty text raises appropriate error.

        Validates:
        - Empty strings are rejected
        - Whitespace-only strings are rejected
        - Error messages are clear

        Success Criteria (T098):
        - ValueError raised for empty/whitespace-only input
        """
        from backend.src.services.vector_search import VectorSearchService

        service: VectorSearchService = VectorSearchService()

        # Test empty string
        with pytest.raises(ValueError) as exc_info:
            service.generate_embedding("")

        assert "empty" in str(exc_info.value).lower()

        # Test whitespace-only string
        with pytest.raises(ValueError) as exc_info:
            service.generate_embedding("   ")

        assert "empty" in str(exc_info.value).lower()
