"""Vector search service for semantic column matching using OpenAI embeddings.

Implements:
- Embedding generation via OpenAI text-embedding-3-small (1536 dimensions)
- Vector similarity search using pgvector cosine distance
- Batch embedding generation for efficiency

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import os
import re
from typing import Any

from openai import OpenAI
from psycopg_pool import ConnectionPool


class VectorSearchService:
    """Service for generating embeddings and performing vector similarity search.

    Uses OpenAI text-embedding-3-small (1536 dimensions) for semantic understanding
    and pgvector cosine distance for similarity matching.
    """

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize vector search service.

        Args:
            pool: Optional database connection pool (for similarity search)
        """
        self.pool: ConnectionPool | None = pool

        # Initialize OpenAI client (synchronous)
        api_key: str | None = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client: OpenAI = OpenAI(api_key=api_key)
        self.model: str = "text-embedding-3-small"
        self.embedding_dim: int = 1536

    def _normalize_text(self, text: str) -> str:
        """Normalize text by stripping and collapsing whitespace.

        Args:
            text: Input text to normalize

        Returns:
            Normalized text with single spaces
        """
        # Strip leading/trailing whitespace
        normalized: str = text.strip()

        # Collapse multiple spaces to single space
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text string.

        Args:
            text: Input text to embed

        Returns:
            List of 1536 floating-point values representing the embedding

        Raises:
            ValueError: If text is empty or whitespace-only
            Exception: If OpenAI API call fails
        """
        # Normalize and validate input
        normalized_text: str = self._normalize_text(text)
        if not normalized_text:
            raise ValueError("Cannot generate embedding for empty text")

        # Call OpenAI API (synchronous) - pass string directly for single input
        response: Any = self.client.embeddings.create(
            model=self.model, input=normalized_text
        )

        # Extract embedding from response
        embedding: list[float] = response.data[0].embedding

        # Validate dimensionality
        if len(embedding) != self.embedding_dim:
            raise ValueError(
                f"Expected {self.embedding_dim}-dimensional embedding, "
                f"got {len(embedding)}"
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
            Exception: If OpenAI API call fails
        """
        if not texts:
            raise ValueError("Cannot generate embeddings for empty text list")

        # Normalize all texts
        normalized_texts: list[str] = [self._normalize_text(text) for text in texts]

        # Validate no empty strings
        if any(not text for text in normalized_texts):
            raise ValueError("Cannot generate embeddings for empty text strings")

        # Call OpenAI API with batch (synchronous) - pass list for batch
        response: Any = self.client.embeddings.create(
            model=self.model, input=normalized_texts
        )

        # Extract embeddings (preserve order)
        embeddings: list[list[float]] = [item.embedding for item in response.data]

        # Validate count and dimensionality
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(embeddings)}"
            )

        for idx, embedding in enumerate(embeddings):
            if len(embedding) != self.embedding_dim:
                raise ValueError(
                    f"Embedding {idx}: expected {self.embedding_dim} dimensions, "
                    f"got {len(embedding)}"
                )

        return embeddings

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
        with self.pool.connection() as conn:
            # Set search path for schema isolation
            with conn.cursor() as cur:
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
