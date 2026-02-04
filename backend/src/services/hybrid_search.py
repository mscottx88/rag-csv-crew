"""Hybrid search service combining exact match, full-text, and vector similarity.

This service orchestrates three search strategies in parallel:
1. Exact match (case-insensitive column name matching)
2. Full-text search (PostgreSQL tsvector with ts_rank)
3. Vector similarity search (pgvector with cosine distance)

Results are fused with weighted scoring (default: 40% exact, 30% fulltext, 30% vector)
and deduplicated by (column_name, dataset_id) tuple.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from psycopg_pool import ConnectionPool

from backend.src.services.vector_search import VectorSearchService


class HybridSearchService:
    """Service for hybrid search combining multiple search strategies.

    Executes exact match, full-text, and vector searches in parallel using
    ThreadPoolExecutor, then fuses results with configurable weights.
    """

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize hybrid search service with connection pool.

        Args:
            pool: Database connection pool for search operations.
        """
        self.pool: ConnectionPool = pool
        self.vector_service: VectorSearchService = VectorSearchService(pool=pool)

    def search(
        self,
        username: str,
        query_text: str,
        dataset_ids: list[str] | None = None,
        limit: int = 10
    ) -> dict[str, Any]:
        """Execute hybrid search combining three strategies in parallel.

        Args:
            username: Username for schema isolation.
            query_text: Natural language query to search for.
            dataset_ids: Optional list of dataset IDs to filter results.
            limit: Maximum number of results to return (default: 10).

        Returns:
            Dictionary containing:
                - exact_results: List of exact match results
                - fulltext_results: List of full-text search results
                - vector_results: List of vector similarity results
                - fused_results: Combined and ranked results

        Raises:
            ValueError: If username or query_text is empty.
            RuntimeError: If any search strategy fails critically.
        """
        if not username or not username.strip():
            raise ValueError("Username cannot be empty")

        if not query_text or not query_text.strip():
            raise ValueError("Query text cannot be empty")

        # Execute three search strategies in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            exact_future: Future[list[dict[str, Any]]] = executor.submit(
                self.exact_search,
                username=username,
                query_text=query_text,
                dataset_ids=dataset_ids,
                limit=limit
            )

            fulltext_future: Future[list[dict[str, Any]]] = executor.submit(
                self.fulltext_search,
                username=username,
                query_text=query_text,
                dataset_ids=dataset_ids,
                limit=limit
            )

            vector_future: Future[list[dict[str, Any]]] = executor.submit(
                self.vector_service.find_similar_columns,
                username=username,
                query_text=query_text,
                limit=limit,
                dataset_ids=dataset_ids
            )

            # Collect results (blocking until all complete)
            exact_results: list[dict[str, Any]] = exact_future.result()
            fulltext_results: list[dict[str, Any]] = fulltext_future.result()
            vector_results: list[dict[str, Any]] = vector_future.result()

        # Fuse results with default weights
        default_weights: dict[str, float] = {
            "exact": 0.4,
            "fulltext": 0.3,
            "vector": 0.3
        }

        fused_results: list[dict[str, Any]] = self.fuse_results(
            exact_results=exact_results,
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            weights=default_weights
        )

        # Apply limit to final results
        fused_results = fused_results[:limit]

        return {
            "exact_results": exact_results,
            "fulltext_results": fulltext_results,
            "vector_results": vector_results,
            "fused_results": fused_results
        }

    def exact_search(
        self,
        username: str,
        query_text: str,
        dataset_ids: list[str] | None = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Perform case-insensitive exact match search on column names.

        Args:
            username: Username for schema isolation.
            query_text: Query text to match against column names.
            dataset_ids: Optional list of dataset IDs to filter results.
            limit: Maximum number of results to return.

        Returns:
            List of matching columns with score=1.0 for exact matches.
            Each dict contains:
                - column_name: str
                - dataset_id: str
                - score: float (always 1.0 for exact matches)

        Raises:
            RuntimeError: If database query fails.
        """
        user_schema: str = f"{username}_schema"

        sql: str = """
            SELECT column_name, dataset_id
            FROM column_mappings
            WHERE LOWER(column_name) = LOWER(%s)
        """

        params: list[Any] = [query_text.strip()]

        # Add dataset filter if provided
        if dataset_ids is not None and len(dataset_ids) > 0:
            placeholders: str = ",".join(["%s"] * len(dataset_ids))
            sql += f" AND dataset_id IN ({placeholders})"
            params.extend(dataset_ids)

        sql += " LIMIT %s"
        params.append(limit)

        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {user_schema}, public")
                    cur.execute(sql, params)
                    rows: list[tuple[Any, ...]] = cur.fetchall()

                    results: list[dict[str, Any]] = []
                    for row in rows:
                        column_name: str = row[0]
                        dataset_id: str = row[1]

                        results.append({
                            "column_name": column_name,
                            "dataset_id": dataset_id,
                            "score": 1.0  # Exact match always has score 1.0
                        })

                    return results

        except Exception as e:
            raise RuntimeError(f"Exact search failed: {e}") from e

    def fulltext_search(
        self,
        username: str,
        query_text: str,
        dataset_ids: list[str] | None = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Perform full-text search using PostgreSQL tsvector and ts_rank.

        Args:
            username: Username for schema isolation.
            query_text: Natural language query for full-text search.
            dataset_ids: Optional list of dataset IDs to filter results.
            limit: Maximum number of results to return.

        Returns:
            List of matching columns ranked by text relevance.
            Each dict contains:
                - column_name: str
                - dataset_id: str
                - rank: float (ts_rank score, typically 0-1)

        Raises:
            RuntimeError: If database query fails.
        """
        user_schema: str = f"{username}_schema"

        sql: str = """
            SELECT
                column_name,
                dataset_id,
                ts_rank(_fulltext, plainto_tsquery('english', %s)) AS rank
            FROM column_mappings
            WHERE _fulltext @@ plainto_tsquery('english', %s)
        """

        params: list[Any] = [query_text.strip(), query_text.strip()]

        # Add dataset filter if provided
        if dataset_ids is not None and len(dataset_ids) > 0:
            placeholders: str = ",".join(["%s"] * len(dataset_ids))
            sql += f" AND dataset_id IN ({placeholders})"
            params.extend(dataset_ids)

        sql += " ORDER BY rank DESC LIMIT %s"
        params.append(limit)

        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {user_schema}, public")
                    cur.execute(sql, params)
                    rows: list[tuple[Any, ...]] = cur.fetchall()

                    results: list[dict[str, Any]] = []
                    for row in rows:
                        column_name: str = row[0]
                        dataset_id: str = row[1]
                        rank: float = float(row[2])

                        results.append({
                            "column_name": column_name,
                            "dataset_id": dataset_id,
                            "rank": rank
                        })

                    return results

        except Exception as e:
            raise RuntimeError(f"Full-text search failed: {e}") from e

    def fuse_results(
        self,
        exact_results: list[dict[str, Any]],
        fulltext_results: list[dict[str, Any]],
        vector_results: list[dict[str, Any]],
        weights: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Fuse results from multiple search strategies with weighted scoring.

        Deduplicates results by (column_name, dataset_id) tuple and combines
        scores from all strategies that found the same column.

        Args:
            exact_results: Results from exact match search (score field).
            fulltext_results: Results from full-text search (rank field).
            vector_results: Results from vector search (similarity field).
            weights: Weights for each strategy (keys: exact, fulltext, vector).

        Returns:
            List of deduplicated results sorted by combined_score (descending).
            Each dict contains:
                - column_name: str
                - dataset_id: str
                - combined_score: float (weighted sum)
                - strategy_scores: dict (optional, original scores per strategy)

        Raises:
            ValueError: If weights dict is missing required keys.
        """
        required_keys: set[str] = {"exact", "fulltext", "vector"}
        if not required_keys.issubset(weights.keys()):
            raise ValueError(f"Weights must contain keys: {required_keys}")

        # Deduplication map: (column_name, dataset_id) -> result dict
        fused_map: dict[tuple[str, str], dict[str, Any]] = {}

        # Process exact match results
        for result in exact_results:
            column_name: str = result["column_name"]
            dataset_id: str = result["dataset_id"]
            score: float = result["score"]

            key: tuple[str, str] = (column_name, dataset_id)

            if key not in fused_map:
                fused_map[key] = {
                    "column_name": column_name,
                    "dataset_id": dataset_id,
                    "combined_score": 0.0,
                    "strategy_scores": {}
                }

            # Add weighted exact score
            weighted_score: float = score * weights["exact"]
            fused_map[key]["combined_score"] += weighted_score
            fused_map[key]["strategy_scores"]["exact"] = score

        # Process full-text results
        for result in fulltext_results:
            column_name = result["column_name"]
            dataset_id = result["dataset_id"]
            rank: float = result["rank"]

            key = (column_name, dataset_id)

            if key not in fused_map:
                fused_map[key] = {
                    "column_name": column_name,
                    "dataset_id": dataset_id,
                    "combined_score": 0.0,
                    "strategy_scores": {}
                }

            # Add weighted fulltext score
            weighted_score = rank * weights["fulltext"]
            fused_map[key]["combined_score"] += weighted_score
            fused_map[key]["strategy_scores"]["fulltext"] = rank

        # Process vector similarity results
        for result in vector_results:
            column_name = result["column_name"]
            dataset_id = result["dataset_id"]
            similarity: float = result["similarity"]

            key = (column_name, dataset_id)

            if key not in fused_map:
                fused_map[key] = {
                    "column_name": column_name,
                    "dataset_id": dataset_id,
                    "combined_score": 0.0,
                    "strategy_scores": {}
                }

            # Add weighted vector score
            weighted_score = similarity * weights["vector"]
            fused_map[key]["combined_score"] += weighted_score
            fused_map[key]["strategy_scores"]["vector"] = similarity

        # Convert to list and sort by combined_score (descending)
        fused_list: list[dict[str, Any]] = list(fused_map.values())
        fused_list.sort(key=lambda x: x["combined_score"], reverse=True)

        return fused_list
