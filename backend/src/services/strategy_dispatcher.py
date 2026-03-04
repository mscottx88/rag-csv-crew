"""Strategy dispatcher service for parallel query fusion.

Determines which query strategies (structured, fulltext, vector) are
applicable based on index metadata, and detects aggregation intent to
skip non-structured strategies for aggregate queries.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import re
from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg_pool import ConnectionPool

from backend.src.models.fusion import StrategyDispatchPlan, StrategyType
from backend.src.utils.logging import get_structured_logger

logger = get_structured_logger(__name__)

# Aggregation keywords for detect_aggregation_intent (FR-019)
_AGGREGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bhow\s+many\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+the\s+total\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+the\s+average\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+the\s+sum\b", re.IGNORECASE),
]

_AGGREGATION_KEYWORDS: set[str] = {
    "count",
    "sum",
    "total",
    "average",
    "avg",
    "minimum",
    "min",
    "maximum",
    "max",
}


class StrategyDispatcherService:
    """Determines which query strategies are applicable based on index metadata.

    Queries the index_metadata table to check for available index
    capabilities (filtering, full_text_search, vector_similarity)
    and builds a StrategyDispatchPlan accordingly.
    """

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize with connection pool for index metadata queries.

        Args:
            pool: Database connection pool for metadata queries.
        """
        self._pool: ConnectionPool = pool

    def plan_strategies(
        self,
        username: str,
        dataset_ids: list[UUID] | None,
        is_aggregation: bool = False,
    ) -> StrategyDispatchPlan:
        """Determine which strategies to dispatch based on index availability.

        Args:
            username: For schema-isolated index metadata queries.
            dataset_ids: Target datasets. None = all user datasets.
            is_aggregation: Whether the query has aggregation intent.

        Returns:
            StrategyDispatchPlan with applicable strategies.

        Strategy selection rules:
            - structured: ALWAYS included (B-tree indexes always exist)
            - fulltext: Included when any target dataset has
              full_text_search capability
            - vector: Included when any target dataset has
              vector_similarity capability
            - If is_aggregation=True: Only structured (FR-019)
        """
        # If aggregation, skip all non-structured strategies (FR-019)
        if is_aggregation:
            available_indexes: dict[str, list[str]] = self._query_available_indexes(
                username, dataset_ids
            )
            return StrategyDispatchPlan(
                strategies=[StrategyType.STRUCTURED],
                is_aggregation=True,
                available_indexes=available_indexes,
            )

        # Query index metadata for capabilities
        capabilities: set[str] = self._query_capabilities(username, dataset_ids)
        available_indexes = self._query_available_indexes(username, dataset_ids)

        # Build strategy list (STRUCTURED always first per FR-002)
        strategies: list[StrategyType] = [StrategyType.STRUCTURED]

        if "full_text_search" in capabilities:
            strategies.append(StrategyType.FULLTEXT)

        if "vector_similarity" in capabilities:
            strategies.append(StrategyType.VECTOR)

        return StrategyDispatchPlan(
            strategies=strategies,
            is_aggregation=False,
            available_indexes=available_indexes,
        )

    @staticmethod
    def detect_aggregation_intent(query_text: str) -> bool:
        """Detect whether the user's query implies aggregation.

        Looks for keywords: count, sum, average, avg, total, minimum,
        min, maximum, max, how many, what is the total/average/sum.

        Args:
            query_text: The user's natural language query.

        Returns:
            True if aggregation intent is detected.
        """
        query_lower: str = query_text.lower()

        # Check multi-word patterns first
        for pattern in _AGGREGATION_PATTERNS:
            if pattern.search(query_lower):
                return True

        # Check single-word keywords with word boundaries
        words: list[str] = re.findall(r"\b\w+\b", query_lower)
        return any(word in _AGGREGATION_KEYWORDS for word in words)

    def _query_capabilities(
        self,
        username: str,
        dataset_ids: list[UUID] | None,
    ) -> set[str]:
        """Query index_metadata for distinct capabilities.

        Args:
            username: For schema isolation.
            dataset_ids: Target datasets, or None for all.

        Returns:
            Set of capability strings found in index_metadata.
        """
        user_schema: str = f"{username}_schema"

        with self._pool.connection() as conn, conn.cursor() as cur:
            if dataset_ids is not None:
                dataset_id_strs: list[str] = [str(d) for d in dataset_ids]
                cur.execute(
                    sql.SQL(
                        "SELECT DISTINCT capability "
                        "FROM {schema}.index_metadata "
                        "WHERE dataset_id::text = ANY(%s) "
                        "AND status = 'created'"
                    ).format(schema=sql.Identifier(user_schema)),
                    (dataset_id_strs,),
                )
            else:
                cur.execute(
                    sql.SQL(
                        "SELECT DISTINCT capability "
                        "FROM {schema}.index_metadata "
                        "WHERE status = 'created'"
                    ).format(schema=sql.Identifier(user_schema)),
                )

            rows: list[tuple[Any, ...]] = cur.fetchall()
            capabilities: set[str] = {str(row[0]) for row in rows}
            return capabilities

    def _query_available_indexes(
        self,
        username: str,
        dataset_ids: list[UUID] | None,
    ) -> dict[str, list[str]]:
        """Query per-table index capabilities.

        Args:
            username: For schema isolation.
            dataset_ids: Target datasets, or None for all.

        Returns:
            Dict mapping table_name to list of capability strings.
        """
        user_schema: str = f"{username}_schema"

        with self._pool.connection() as conn, conn.cursor() as cur:
            if dataset_ids is not None:
                dataset_id_strs: list[str] = [str(d) for d in dataset_ids]
                cur.execute(
                    sql.SQL(
                        "SELECT d.table_name, "
                        "array_agg(DISTINCT im.capability) "
                        "FROM {schema}.index_metadata im "
                        "JOIN {schema}.datasets d "
                        "ON im.dataset_id::text = d.id::text "
                        "WHERE im.dataset_id::text = ANY(%s) "
                        "AND im.status = 'created' "
                        "GROUP BY d.table_name"
                    ).format(schema=sql.Identifier(user_schema)),
                    (dataset_id_strs,),
                )
            else:
                cur.execute(
                    sql.SQL(
                        "SELECT d.table_name, "
                        "array_agg(DISTINCT im.capability) "
                        "FROM {schema}.index_metadata im "
                        "JOIN {schema}.datasets d "
                        "ON im.dataset_id::text = d.id::text "
                        "WHERE im.status = 'created' "
                        "GROUP BY d.table_name"
                    ).format(schema=sql.Identifier(user_schema)),
                )

            rows: list[tuple[Any, ...]] = cur.fetchall()
            indexes: dict[str, list[str]] = {}
            for row in rows:
                table_name: str = str(row[0])
                caps: list[str] = list(row[1]) if row[1] else []
                indexes[table_name] = caps
            return indexes
