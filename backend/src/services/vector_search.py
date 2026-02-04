"""Vector search service for semantic similarity using OpenAI embeddings and pgvector.

This service provides semantic column matching by generating embeddings
using OpenAI's text-embedding-3-small model and querying PostgreSQL
with pgvector extension for cosine similarity search.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import os
from typing import Any

from openai import OpenAI
from psycopg_pool import ConnectionPool


class VectorSearchService:
    """Service for generating embeddings and performing vector similarity search.

    Uses OpenAI text-embedding-3-small (1536 dimensions) for embedding generation
    and pgvector with cosine distance (<=> operator) for similarity search.
    """

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize vector search service with OpenAI client.

        Args:
            pool: Optional database connection pool for similarity searches.
                  If None, only embedding generation methods are available.

        Raises:
            ValueError: If OPENAI_API_KEY environment variable is not set.
        """
        api_key: str | None = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable must be set for vector search"
            )

        self.client: OpenAI = OpenAI(api_key=api_key)
        self.pool: ConnectionPool | None = pool
        self.model: str = "text-embedding-3-small"
        self.embedding_dimension: int = 1536

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text input.

        Args:
            text: Text to generate embedding for (column name, description, etc.)

        Returns:
            1536-dimensional embedding vector as list of floats.

        Raises:
            ValueError: If text is empty or whitespace-only after normalization.
            RuntimeError: If OpenAI API call fails.
        """
        # Normalize text: strip leading/trailing whitespace and collapse internal whitespace
        normalized_text: str = " ".join(text.split())
        if not normalized_text:
            raise ValueError("Text cannot be empty or whitespace-only")

        try:
            response: Any = self.client.embeddings.create(
                model=self.model,
                input=normalized_text
            )
            embedding: list[float] = response.data[0].embedding

            # Verify dimension
            if len(embedding) != self.embedding_dimension:
                raise RuntimeError(
                    f"Expected {self.embedding_dimension}-dimensional embedding, "
                    f"got {len(embedding)}"
                )

            return embedding

        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call.

        More efficient than calling generate_embedding() repeatedly for multiple texts.

        Args:
            texts: List of texts to generate embeddings for.

        Returns:
            List of 1536-dimensional embedding vectors (same order as input texts).

        Raises:
            ValueError: If texts list is empty or contains empty strings.
            RuntimeError: If OpenAI API call fails.
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        # Normalize all texts: strip and collapse internal whitespace
        normalized_texts: list[str] = [" ".join(text.split()) for text in texts]

        # Validate all texts are non-empty
        if any(not text for text in normalized_texts):
            raise ValueError("All texts must be non-empty after normalization")

        try:
            response: Any = self.client.embeddings.create(
                model=self.model,
                input=normalized_texts
            )

            embeddings: list[list[float]] = [
                item.embedding for item in response.data
            ]

            # Verify all dimensions
            for i, embedding in enumerate(embeddings):
                if len(embedding) != self.embedding_dimension:
                    raise RuntimeError(
                        f"Expected {self.embedding_dimension}-dimensional embedding "
                        f"for text {i}, got {len(embedding)}"
                    )

            return embeddings

        except Exception as e:
            raise RuntimeError(f"Failed to generate batch embeddings: {e}") from e

    def find_similar_columns(
        self,
        username: str,
        query_text: str,
        limit: int = 10,
        dataset_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Find columns semantically similar to query text using vector similarity.

        Uses pgvector cosine distance (<=> operator) to find closest embeddings.
        Distance is converted to similarity score: similarity = 1 - (distance / 2).

        Args:
            username: Username for schema isolation.
            query_text: Natural language query to search for.
            limit: Maximum number of results to return (default: 10).
            dataset_ids: Optional list of dataset IDs to filter results.
                        If None, search across all user's datasets.

        Returns:
            List of matching columns sorted by similarity (descending).
            Each dict contains:
                - column_name: str
                - dataset_id: str
                - distance: float (cosine distance, 0 = identical)
                - similarity: float (0-1, higher = more similar)

        Raises:
            ValueError: If pool is None, username is empty, or query_text is empty.
            RuntimeError: If database query fails.
        """
        if self.pool is None:
            raise ValueError(
                "Connection pool is required for similarity search. "
                "Provide pool parameter to __init__()."
            )

        if not username or not username.strip():
            raise ValueError("Username cannot be empty")

        if not query_text or not query_text.strip():
            raise ValueError("Query text cannot be empty")

        # Generate embedding for query text
        query_embedding: list[float] = self.generate_embedding(query_text)

        # Build SQL query
        user_schema: str = f"{username}_schema"

        sql: str = """
            SELECT
                column_name,
                dataset_id,
                embedding <=> %s::vector AS distance
            FROM column_mappings
        """

        params: list[Any] = [query_embedding]

        # Add dataset filter if provided
        if dataset_ids is not None and len(dataset_ids) > 0:
            placeholders: str = ",".join(["%s"] * len(dataset_ids))
            sql += f" WHERE dataset_id IN ({placeholders})"
            params.extend(dataset_ids)

        sql += " ORDER BY distance ASC LIMIT %s"
        params.append(limit)

        try:
            with self.pool.connection() as conn, conn.cursor() as cur:
                # Set search path to user schema
                cur.execute(f"SET search_path TO {user_schema}, public")

                # Execute similarity search
                cur.execute(sql, params)
                rows: list[tuple[Any, ...]] = cur.fetchall()

                # Convert to dict format with similarity score
                results: list[dict[str, Any]] = []
                for row in rows:
                    column_name: str = row[0]
                    dataset_id: str = row[1]
                    distance: float = row[2]

                    # Convert distance to similarity: similarity = 1 - (distance / 2)
                    # Cosine distance range is [0, 2], so we normalize to [0, 1]
                    similarity: float = 1.0 - (distance / 2.0)

                    results.append({
                        "column_name": column_name,
                        "dataset_id": dataset_id,
                        "distance": distance,
                        "similarity": similarity
                    })

                return results

        except Exception as e:
            raise RuntimeError(f"Vector similarity search failed: {e}") from e
