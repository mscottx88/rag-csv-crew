"""Vector search service for semantic column matching using embeddings.

Implements:
- Embedding generation via OpenAI text-embedding-3-small or Google Gemini (1536 dimensions)
- Vector similarity search using pgvector cosine distance
- Batch embedding generation for efficiency
- Provider auto-detection (Google Gemini if GOOGLE_API_KEY set, else OpenAI)

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import os
import re
from typing import Any, Literal

from openai import OpenAI
from psycopg_pool import ConnectionPool
from google import genai


class VectorSearchService:
    """Service for generating embeddings and performing vector similarity search.

    Uses OpenAI text-embedding-3-small (1536 dimensions) for semantic understanding
    and pgvector cosine distance for similarity matching.
    """

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize vector search service.

        Auto-detects embedding provider:
        - Google Gemini if GOOGLE_API_KEY is set (gemini-embedding-001)
        - OpenAI if OPENAI_API_KEY is set (text-embedding-3-small)

        Args:
            pool: Optional database connection pool (for similarity search)

        Raises:
            ValueError: If neither GOOGLE_API_KEY nor OPENAI_API_KEY is set
        """
        self.pool: ConnectionPool | None = pool

        # Auto-detect provider (prefer Google if both are set)
        google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
        openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

        if google_api_key:
            # Initialize Google Gemini client (new google.genai package)
            self.client: Any = genai.Client(api_key=google_api_key)
            self.provider: Literal["google", "openai"] = "google"
            # Use embedding-001 (768d native, available in v1beta)
            self.model: str = "models/embedding-001"
            self.native_dim: int = 768  # Google embedding-001 native dimensions
            self.embedding_dim: int = 1536  # Padded to match database schema
        elif openai_api_key:
            # Initialize OpenAI client (synchronous)
            self.client = OpenAI(api_key=openai_api_key)
            self.provider = "openai"
            self.model = "text-embedding-3-small"
            self.native_dim = 1536  # OpenAI native dimensions
            self.embedding_dim = 1536  # Matches database schema
        else:
            raise ValueError(
                "Neither GOOGLE_API_KEY nor OPENAI_API_KEY environment variable is set"
            )

    def _normalize_text(self, text: str) -> str:
        """Normalize text by stripping and collapsing whitespace.

        Args:
            text: Input text to normalize

        Returns:
            Normalized text with single spaces
        """
        # Strip leading/trailing whitespace and collapse multiple spaces to single space
        return re.sub(r"\s+", " ", text.strip())

    def _pad_embedding(self, embedding: list[float]) -> list[float]:
        """Pad embedding to target dimension with zeros if needed.

        Args:
            embedding: Input embedding vector

        Returns:
            Padded embedding vector of target dimension
        """
        if len(embedding) < self.embedding_dim:
            # Pad with zeros to reach target dimension
            padding: list[float] = [0.0] * (self.embedding_dim - len(embedding))
            return embedding + padding
        return embedding

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text string.

        Args:
            text: Input text to embed

        Returns:
            List of 1536 floating-point values representing the embedding

        Raises:
            ValueError: If text is empty or whitespace-only
            Exception: If API call fails
        """
        # Normalize and validate input
        normalized_text: str = self._normalize_text(text)
        if not normalized_text:
            raise ValueError("Cannot generate embedding for empty text")

        # Call appropriate provider API
        if self.provider == "google":
            # Call Google Gemini API (synchronous, new google.genai package)
            response: Any = self.client.models.embed_content(
                model=self.model, contents=normalized_text
            )
            embedding: list[float] = response.embeddings[0].values
            # Pad Google embeddings (768d) to target dimension (1536d)
            embedding = self._pad_embedding(embedding)
        else:
            # Call OpenAI API (synchronous) - pass string directly for single input
            response = self.client.embeddings.create(
                model=self.model, input=normalized_text
            )
            embedding = response.data[0].embedding

        # Validate dimensionality
        if len(embedding) != self.embedding_dim:
            raise ValueError(
                f"Expected {self.embedding_dim}-dimensional embedding, got {len(embedding)}"
            )

        return embedding

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call.

        More efficient than calling generate_embedding() repeatedly.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors, one per input text

        Raises:
            ValueError: If texts list is empty or contains only whitespace
            Exception: If API call fails
        """
        if not texts:
            raise ValueError("Cannot generate embeddings for empty text list")

        # Normalize all texts
        normalized_texts: list[str] = [self._normalize_text(text) for text in texts]

        # Validate no empty strings
        if any(not text for text in normalized_texts):
            raise ValueError("Cannot generate embeddings for empty text strings")

        # Call appropriate provider API with batch
        embeddings: list[list[float]]
        if self.provider == "google":
            # Google Gemini batch embeddings (synchronous, new google.genai package)
            # Process batch as individual calls (API limitation)
            embeddings = []
            for normalized_text in normalized_texts:
                gemini_response: Any = self.client.models.embed_content(
                    model=self.model, contents=normalized_text
                )
                # Pad Google embeddings (768d) to target dimension (1536d)
                padded_embedding: list[float] = self._pad_embedding(
                    gemini_response.embeddings[0].values
                )
                embeddings.append(padded_embedding)
        else:
            # Call OpenAI API with batch (synchronous) - pass list for batch
            openai_response: Any = self.client.embeddings.create(
                model=self.model, input=normalized_texts
            )
            # Extract embeddings (preserve order)
            embeddings = [item.embedding for item in openai_response.data]

        # Validate count and dimensionality
        if len(embeddings) != len(texts):
            raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")

        for idx, embedding in enumerate(embeddings):
            if len(embedding) != self.embedding_dim:
                raise ValueError(
                    f"Embedding {idx}: expected {self.embedding_dim} dimensions, "
                    f"got {len(embedding)}"
                )

        return embeddings

    # pylint: disable=too-many-locals
    # JUSTIFICATION: Function requires many local variables for SQL query construction
    # (embedding, schema, sql_parts, params, placeholders) and result processing
    # (row unpacking: column_name, dataset_id, description, distance, similarity).
    # Reducing would require over-engineering (builder pattern) or reduce clarity.
    def find_similar_columns(
        self,
        username: str,
        query_text: str,
        limit: int = 10,
        dataset_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find columns semantically similar to query using pgvector cosine distance.

        Args:
            username: Username for schema isolation
            query_text: Natural language query text
            limit: Maximum number of results to return
            dataset_ids: Optional list of dataset UUIDs to filter by

        Returns:
            List of dictionaries with keys:
                - column_name: str
                - dataset_id: str
                - description: str | None
                - distance: float (cosine distance, lower = more similar)
                - similarity: float (0-1, higher = more similar)

        Raises:
            ValueError: If pool not initialized or query_text empty
            Exception: If database query fails
        """
        if not self.pool:
            raise ValueError("Connection pool not initialized for vector search")

        # Generate embedding for query
        query_embedding: list[float] = self.generate_embedding(query_text)

        # Build SQL query with optional dataset filtering
        user_schema: str = f"{username}_schema"

        # Base query using pgvector cosine distance operator (<=>)
        sql_parts: list[str] = [
            "SELECT column_name, dataset_id, description, ",
            "embedding <=> %s::vector AS distance ",
            "FROM column_mappings ",
            "WHERE embedding IS NOT NULL ",
        ]

        # Add dataset filtering if specified
        params: list[Any] = [query_embedding]
        if dataset_ids:
            placeholders: str = ", ".join(["%s"] * len(dataset_ids))
            sql_parts.append(f"AND dataset_id IN ({placeholders}) ")
            params.extend(dataset_ids)

        # Order by distance (ascending = most similar first)
        sql_parts.append("ORDER BY distance ASC ")
        sql_parts.append("LIMIT %s")
        params.append(limit)

        sql: str = "".join(sql_parts)

        # Execute query with connection pool
        with self.pool.connection() as conn, conn.cursor() as cur:
            # Set search path for schema isolation
            cur.execute(f"SET search_path TO {user_schema}, public")

            # Execute similarity search
            cur.execute(sql, params)
            rows: list[tuple[Any, ...]] = cur.fetchall()

        # Convert rows to dictionaries with similarity scores
        results: list[dict[str, Any]] = []
        for row in rows:
            column_name: str = row[0]
            dataset_id: str = row[1]
            description: str | None = row[2]
            distance: float = row[3]

            # Convert cosine distance to similarity score (0-1, higher is better)
            # Cosine distance range: [0, 2], where 0 = identical, 2 = opposite
            # Similarity formula: 1 - (distance / 2)
            similarity: float = 1.0 - (distance / 2.0)

            results.append(
                {
                    "column_name": column_name,
                    "dataset_id": dataset_id,
                    "description": description,
                    "distance": distance,
                    "similarity": similarity,
                }
            )

        return results
