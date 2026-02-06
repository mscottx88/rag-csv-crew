"""Data value search service for finding query terms in actual CSV data.

This service provides fallback search when column name matching fails. It samples
rows from data tables and searches for query terms in the actual values, helping
with queries like "tell me about gold" where "gold" is a data value, not a column name.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import logging
from typing import Any

from psycopg import sql
from psycopg_pool import ConnectionPool

# Configure logger
logger: logging.Logger = logging.getLogger(__name__)


class DataValueSearchService:
    """Service for searching query terms in actual data values."""

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize data value search service with connection pool.

        Args:
            pool: Database connection pool for search operations.
        """
        self.pool: ConnectionPool = pool

    def search_data_values(
        self,
        username: str,
        query_text: str,
        dataset_ids: list[str] | None = None,
        sample_size: int = 100,
        min_match_threshold: int = 1,
    ) -> list[dict[str, Any]]:
        """Search for query terms in actual data values across datasets.

        Samples rows from data tables and searches for case-insensitive matches
        of query_text in string/text columns. Returns columns that contain matches
        along with sample matching values.

        Args:
            username: Username for schema isolation.
            query_text: Query text to search for in data values.
            dataset_ids: Optional list of dataset IDs to filter search.
            sample_size: Number of rows to sample from each table (default: 100).
            min_match_threshold: Minimum number of matches to include column (default: 1).

        Returns:
            List of matching columns with metadata:
                - column_name: str
                - dataset_id: str
                - dataset_table: str
                - match_count: int (number of rows containing the value)
                - sample_values: list[str] (sample matching values, max 3)
                - score: float (match_count / sample_size, capped at 1.0)

        Raises:
            ValueError: If username or query_text is empty.
            RuntimeError: If database query fails.
        """
        if not username or not username.strip():
            raise ValueError("Username cannot be empty")

        if not query_text or not query_text.strip():
            raise ValueError("Query text cannot be empty")

        user_schema: str = f"{username}_schema"
        query_lower: str = query_text.strip().lower()
        results: list[dict[str, Any]] = []

        logger.info(
            f"DataValueSearch: Starting search for '{query_text}' "
            f"(user: {username}, sample_size: {sample_size})"
        )

        try:
            with self.pool.connection() as conn, conn.cursor() as cur:
                # Set search path
                cur.execute(
                    sql.SQL("SET search_path TO {}, public").format(
                        sql.Identifier(user_schema)
                    )
                )

                # Get datasets and their columns
                dataset_filter: str = ""
                params: list[Any] = []

                if dataset_ids is not None and len(dataset_ids) > 0:
                    placeholders: str = ",".join(["%s"] * len(dataset_ids))
                    dataset_filter = f" WHERE d.id IN ({placeholders})"
                    params.extend(dataset_ids)

                cur.execute(
                    f"""
                    SELECT
                        d.id,
                        d.filename,
                        cm.column_name,
                        cm.inferred_type
                    FROM datasets d
                    JOIN column_mappings cm ON d.id = cm.dataset_id
                    {dataset_filter}
                    ORDER BY d.filename, cm.column_name
                    """,
                    params,
                )

                dataset_columns: list[tuple[Any, ...]] = cur.fetchall()

                logger.info(f"DataValueSearch: Found {len(dataset_columns)} total columns to check")

                # Group columns by dataset
                datasets_map: dict[str, dict[str, Any]] = {}
                for row in dataset_columns:
                    dataset_id: str = str(row[0])
                    filename: str = row[1]
                    column_name: str = row[2]
                    inferred_type: str = row[3]

                    if dataset_id not in datasets_map:
                        dataset_table: str = filename.replace(".csv", "_data")
                        datasets_map[dataset_id] = {
                            "table_name": dataset_table,
                            "columns": [],
                        }

                    logger.debug(
                        f"DataValueSearch: Column '{column_name}' has type '{inferred_type}'"
                    )

                    # Only search text-like columns (case-insensitive check)
                    if inferred_type.upper() in ("TEXT", "VARCHAR", "STRING", "CHAR"):
                        datasets_map[dataset_id]["columns"].append(column_name)
                        logger.debug(f"DataValueSearch: Added text column '{column_name}'")
                    else:
                        logger.debug(
                            f"DataValueSearch: Skipped column '{column_name}' "
                            f"(type '{inferred_type}' not in TEXT/VARCHAR/STRING/CHAR)"
                        )

                # Log summary of text columns found
                total_text_columns: int = sum(
                    len(info["columns"]) for info in datasets_map.values()
                )
                logger.info(
                    f"DataValueSearch: Identified {total_text_columns} text columns "
                    f"across {len(datasets_map)} datasets"
                )

                # Search each dataset's data table
                for dataset_id, dataset_info in datasets_map.items():
                    current_table: str = dataset_info["table_name"]
                    columns: list[str] = dataset_info["columns"]

                    logger.info(
                        f"DataValueSearch: Processing dataset {dataset_id}, "
                        f"table={current_table}, text_columns={len(columns)}"
                    )

                    if not columns:
                        logger.info(f"DataValueSearch: Skipping {current_table} - no text columns")
                        continue

                    # For each text column, search for matches
                    for column_name in columns:
                        # Sample rows and count matches
                        cur.execute(
                            sql.SQL(
                                """
                                SELECT {column}
                                FROM {table}
                                WHERE {column} IS NOT NULL
                                LIMIT %s
                                """
                            ).format(
                                column=sql.Identifier(column_name),
                                table=sql.Identifier(current_table),
                            ),
                            [sample_size],
                        )

                        sampled_rows: list[tuple[Any, ...]] = cur.fetchall()

                        # Count matches and collect sample values
                        matching_values: list[str] = []
                        match_count: int = 0

                        for sampled_row in sampled_rows:
                            value: Any = sampled_row[0]
                            if value is not None:
                                value_str: str = str(value).lower()
                                if query_lower in value_str:
                                    match_count += 1
                                    if len(matching_values) < 3:
                                        matching_values.append(str(value))

                        # If matches found above threshold, add to results
                        if match_count >= min_match_threshold:
                            score: float = min(1.0, match_count / sample_size)
                            results.append(
                                {
                                    "column_name": column_name,
                                    "dataset_id": dataset_id,
                                    "table_name": current_table,
                                    "match_count": match_count,
                                    "sample_values": matching_values,
                                    "score": score,
                                }
                            )

                # Sort by score descending
                results.sort(key=lambda x: x["score"], reverse=True)

                return results

        except Exception as e:
            raise RuntimeError(f"Data value search failed: {e}") from e
