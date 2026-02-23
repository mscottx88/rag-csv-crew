"""Column Metadata Service for computing and storing column-level statistics.

Computes min/max values, distinct counts, null counts, and sample values
for dataset columns to enrich embeddings and improve query understanding.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from concurrent.futures import Future, ThreadPoolExecutor
import json
import logging
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

logger: logging.Logger = logging.getLogger(__name__)


class ColumnMetadataService:
    """Service for computing and storing column-level statistics.

    Provides methods to:
    - Compute numeric statistics (min/max, distinct count)
    - Compute text statistics (distinct count, top values)
    - Store metadata in column_metadata table
    - Retrieve metadata for enriching embeddings
    """

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize ColumnMetadataService.

        Args:
            pool: Database connection pool for metadata operations
        """
        self.pool: ConnectionPool = pool

    def _compute_numeric_stats(
        self,
        username: str,
        dataset_id: UUID,
        table_name: str,
        column_name: str,
    ) -> dict[str, Any]:
        """Compute statistics for numeric columns.

        Computes min, max, distinct count, and null count for numeric columns.

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            table_name: Name of the table containing the column
            column_name: Name of the column to analyze

        Returns:
            Dictionary with keys:
            - dataset_id: UUID of the dataset
            - column_name: Name of the column
            - min_value: Minimum value (as string)
            - max_value: Maximum value (as string)
            - distinct_count: Number of distinct values
            - null_count: Number of NULL values
            - top_values: None (not applicable for numeric columns)

        Raises:
            Exception: On database operation failure
        """
        schema_name: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            # Compute min, max, distinct count, and null count in single query
            query: str = f"""
                    SELECT
                        MIN({column_name})::TEXT AS min_value,
                        MAX({column_name})::TEXT AS max_value,
                        COUNT(DISTINCT {column_name}) AS distinct_count,
                        COUNT(*) - COUNT({column_name}) AS null_count
                    FROM {table_name}
                """
            cur.execute(query)
            row: tuple[Any, ...] | None = cur.fetchone()

            if row is None:
                # Empty table case
                return {
                    "dataset_id": dataset_id,
                    "column_name": column_name,
                    "min_value": None,
                    "max_value": None,
                    "distinct_count": 0,
                    "null_count": 0,
                    "top_values": None,
                }

            min_value: str | None = row[0]
            max_value: str | None = row[1]
            distinct_count: int = row[2]
            null_count: int = row[3]

            return {
                "dataset_id": dataset_id,
                "column_name": column_name,
                "min_value": min_value,
                "max_value": max_value,
                "distinct_count": distinct_count,
                "null_count": null_count,
                "top_values": None,
            }

    def _compute_text_stats(
        self,
        username: str,
        dataset_id: UUID,
        table_name: str,
        column_name: str,
    ) -> dict[str, Any]:
        """Compute statistics for text columns.

        Computes distinct count, null count, and top 10 most frequent values
        for text columns.

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            table_name: Name of the table containing the column
            column_name: Name of the column to analyze

        Returns:
            Dictionary with keys:
            - dataset_id: UUID of the dataset
            - column_name: Name of the column
            - min_value: None (not applicable for text columns)
            - max_value: None (not applicable for text columns)
            - distinct_count: Number of distinct values
            - null_count: Number of NULL values
            - top_values: JSON array of {value, count} for top 10 values

        Raises:
            Exception: On database operation failure
        """
        schema_name: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            # Compute distinct count and null count
            count_query: str = f"""
                    SELECT
                        COUNT(DISTINCT {column_name}) AS distinct_count,
                        COUNT(*) - COUNT({column_name}) AS null_count
                    FROM {table_name}
                """
            cur.execute(count_query)
            count_row: tuple[Any, ...] | None = cur.fetchone()

            if count_row is None:
                # Empty table case
                return {
                    "dataset_id": dataset_id,
                    "column_name": column_name,
                    "min_value": None,
                    "max_value": None,
                    "distinct_count": 0,
                    "null_count": 0,
                    "top_values": None,
                }

            distinct_count: int = count_row[0]
            null_count: int = count_row[1]

            # Compute top 10 most frequent values
            top_values_query: str = f"""
                    SELECT
                        {column_name} AS value,
                        COUNT(*) AS count
                    FROM {table_name}
                    WHERE {column_name} IS NOT NULL
                    GROUP BY {column_name}
                    ORDER BY count DESC, {column_name} ASC
                    LIMIT 10
                """
            cur.execute(top_values_query)
            top_rows: list[tuple[Any, ...]] = cur.fetchall()

            # Convert to JSON-serializable format
            top_values: list[dict[str, Any]] | None = None
            if top_rows:
                top_values = [{"value": str(row[0]), "count": int(row[1])} for row in top_rows]

            return {
                "dataset_id": dataset_id,
                "column_name": column_name,
                "min_value": None,
                "max_value": None,
                "distinct_count": distinct_count,
                "null_count": null_count,
                "top_values": top_values,
            }

    def _compute_general_stats(
        self,
        username: str,
        dataset_id: UUID,
        table_name: str,
        column_name: str,
    ) -> dict[str, Any]:
        """Compute general statistics for non-numeric, non-text columns.

        Computes distinct count and null count for columns that don't fit
        numeric or text categories (e.g., BOOLEAN, DATE, TIMESTAMP).

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            table_name: Name of the table containing the column
            column_name: Name of the column to analyze

        Returns:
            Dictionary with keys:
            - dataset_id: UUID of the dataset
            - column_name: Name of the column
            - min_value: None
            - max_value: None
            - distinct_count: Number of distinct values
            - null_count: Number of NULL values
            - top_values: None

        Raises:
            Exception: On database operation failure
        """
        schema_name: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            # Compute distinct count and null count
            query: str = f"""
                    SELECT
                        COUNT(DISTINCT {column_name}) AS distinct_count,
                        COUNT(*) - COUNT({column_name}) AS null_count
                    FROM {table_name}
                """
            cur.execute(query)
            row: tuple[Any, ...] | None = cur.fetchone()

            if row is None:
                # Empty table case
                return {
                    "dataset_id": dataset_id,
                    "column_name": column_name,
                    "min_value": None,
                    "max_value": None,
                    "distinct_count": 0,
                    "null_count": 0,
                    "top_values": None,
                }

            distinct_count: int = row[0]
            null_count: int = row[1]

            return {
                "dataset_id": dataset_id,
                "column_name": column_name,
                "min_value": None,
                "max_value": None,
                "distinct_count": distinct_count,
                "null_count": null_count,
                "top_values": None,
            }

    def _compute_column_metadata(
        self,
        username: str,
        dataset_id: UUID,
        table_name: str,
        column_name: str,
    ) -> dict[str, Any]:
        """Compute metadata for a column by dispatching to appropriate stat method.

        Queries the column's PostgreSQL data type and dispatches to the
        appropriate statistics computation method based on type category.

        Type Dispatch Rules:
        - Numeric types (BIGINT, DOUBLE PRECISION, INTEGER, etc.) → _compute_numeric_stats()
        - Text types (TEXT, VARCHAR, CHAR) → _compute_text_stats()
        - Other types (BOOLEAN, DATE, TIMESTAMP) → _compute_general_stats()

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            table_name: Name of the table containing the column
            column_name: Name of the column to analyze

        Returns:
            Dictionary with computed metadata (structure depends on column type)

        Raises:
            ValueError: If column does not exist in table
            Exception: On database operation failure
        """
        schema_name: str = f"{username}_schema"

        # Query PostgreSQL information_schema to get column data type
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            # Get column data type from information_schema
            type_query: str = """
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                      AND column_name = %s
                """
            cur.execute(type_query, (schema_name, table_name, column_name))
            type_row: tuple[Any, ...] | None = cur.fetchone()

            if type_row is None:
                raise ValueError(f"Column '{column_name}' not found in table '{table_name}'")

            data_type: str = type_row[0].upper()
            udt_name: str = type_row[1].upper()

        # Dispatch to appropriate stat method based on data type
        # Numeric types: INTEGER, BIGINT, SMALLINT, REAL, DOUBLE PRECISION, NUMERIC
        numeric_types: set[str] = {
            "INTEGER",
            "BIGINT",
            "SMALLINT",
            "INT2",
            "INT4",
            "INT8",
            "REAL",
            "DOUBLE PRECISION",
            "FLOAT4",
            "FLOAT8",
            "NUMERIC",
            "DECIMAL",
        }

        # Text types: TEXT, VARCHAR, CHAR, CHARACTER VARYING, CHARACTER
        text_types: set[str] = {
            "TEXT",
            "VARCHAR",
            "CHAR",
            "CHARACTER VARYING",
            "CHARACTER",
            "BPCHAR",
        }

        # Check data_type first, then fall back to udt_name
        if data_type in numeric_types or udt_name in numeric_types:
            return self._compute_numeric_stats(username, dataset_id, table_name, column_name)
        if data_type in text_types or udt_name in text_types:
            return self._compute_text_stats(username, dataset_id, table_name, column_name)

        # All other types (BOOLEAN, DATE, TIMESTAMP, etc.)
        return self._compute_general_stats(username, dataset_id, table_name, column_name)

    def _get_column_names(self, username: str, table_name: str) -> list[str]:
        """Get list of data column names from table (excluding metadata columns).

        Args:
            username: Username for schema context
            table_name: Name of the table

        Returns:
            List of column names (excludes _source_file, _row_number, _ingested_at)

        Raises:
            Exception: On database operation failure
        """
        schema_name: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            # Get all column names except metadata columns
            columns_query: str = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                  AND column_name NOT IN ('_source_file', '_row_number', '_ingested_at')
                ORDER BY ordinal_position
            """
            cur.execute(columns_query, (schema_name, table_name))
            column_rows: list[tuple[Any, ...]] = cur.fetchall()

            return [row[0] for row in column_rows]

    def _compute_all_columns_parallel(
        self,
        username: str,
        dataset_id: UUID,
        table_name: str,
        *,
        column_names: list[str],
        max_workers: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Compute metadata for all columns in parallel using ThreadPoolExecutor.

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            table_name: Name of the table
            column_names: List of column names to process
            max_workers: Maximum number of parallel worker threads

        Returns:
            Tuple of (metadata_results, errors):
            - metadata_results: List of computed metadata dictionaries
            - errors: List of error messages

        Raises:
            Exception: On critical failure
        """
        metadata_results: list[dict[str, Any]] = []
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all column computation tasks
            futures: dict[Future[dict[str, Any]], str] = {}
            for column_name in column_names:
                future: Future[dict[str, Any]] = executor.submit(
                    self._compute_column_metadata,
                    username,
                    dataset_id,
                    table_name,
                    column_name,
                )
                futures[future] = column_name

            # Collect results as they complete
            for future, column_name in futures.items():
                try:
                    result: dict[str, Any] = future.result()
                    metadata_results.append(result)
                    logger.debug("Computed metadata for column: %s", column_name)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    error_msg: str = f"Failed to compute metadata for column '{column_name}': {exc}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        return metadata_results, errors

    def compute_and_store_metadata(
        self,
        username: str,
        dataset_id: UUID,
        table_name: str,
        max_workers: int = 10,
    ) -> dict[str, Any]:
        """Compute and store metadata for all columns in a table.

        Uses ThreadPoolExecutor to compute column statistics in parallel,
        then stores results in the column_metadata table.

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            table_name: Name of the table to analyze
            max_workers: Maximum number of parallel worker threads (default: 10)

        Returns:
            Dictionary with keys:
            - columns_processed: Number of columns processed
            - success: Boolean indicating overall success
            - errors: List of error messages (empty if all succeeded)

        Raises:
            Exception: On critical failure (e.g., table not found)

        Performance:
        - Target: <5s for 50-column datasets per feature spec
        - Uses thread-based parallelism for I/O-bound database queries
        """
        schema_name: str = f"{username}_schema"
        logger.info(
            "Computing metadata for table %s.%s (dataset %s)",
            schema_name,
            table_name,
            dataset_id,
        )

        # Get column names from table
        column_names: list[str] = self._get_column_names(username, table_name)

        if not column_names:
            logger.warning("No columns found in table %s.%s", schema_name, table_name)
            return {
                "columns_processed": 0,
                "success": True,
                "errors": [],
            }

        logger.info("Found %d columns to process", len(column_names))

        # Compute metadata for all columns in parallel
        metadata_results: list[dict[str, Any]]
        errors: list[str]
        metadata_results, errors = self._compute_all_columns_parallel(
            username,
            dataset_id,
            table_name,
            column_names=column_names,
            max_workers=max_workers,
        )

        # Store all metadata results in database
        if metadata_results:
            try:
                self._store_metadata_batch(username, metadata_results)
                logger.info("Successfully stored metadata for %d columns", len(metadata_results))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                error_msg = f"Failed to store metadata batch: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)

        success: bool = len(errors) == 0
        return {
            "columns_processed": len(metadata_results),
            "success": success,
            "errors": errors,
        }

    def _store_metadata_batch(
        self,
        username: str,
        metadata_list: list[dict[str, Any]],
    ) -> None:
        """Store column metadata in batch using UPSERT logic.

        Inserts or updates column_metadata records using PostgreSQL
        INSERT ... ON CONFLICT ... DO UPDATE (UPSERT).

        Args:
            username: Username for schema context
            metadata_list: List of metadata dictionaries with keys:
                - dataset_id: UUID
                - column_name: str
                - min_value: str | None
                - max_value: str | None
                - distinct_count: int
                - null_count: int
                - top_values: list[dict] | None (converted to JSONB)

        Raises:
            Exception: On database operation failure
        """
        if not metadata_list:
            return

        schema_name: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            # UPSERT query: INSERT with ON CONFLICT DO UPDATE
            upsert_query: str = """
                INSERT INTO column_metadata (
                    dataset_id,
                    column_name,
                    min_value,
                    max_value,
                    distinct_count,
                    null_count,
                    top_values,
                    computed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (dataset_id, column_name)
                DO UPDATE SET
                    min_value = EXCLUDED.min_value,
                    max_value = EXCLUDED.max_value,
                    distinct_count = EXCLUDED.distinct_count,
                    null_count = EXCLUDED.null_count,
                    top_values = EXCLUDED.top_values,
                    computed_at = EXCLUDED.computed_at
            """

            # Execute batch insert/update
            for metadata in metadata_list:
                # Convert top_values to Jsonb if present
                top_values: Jsonb | None = None
                if metadata.get("top_values") is not None:
                    top_values = Jsonb(metadata["top_values"])

                cur.execute(
                    upsert_query,
                    (
                        metadata["dataset_id"],
                        metadata["column_name"],
                        metadata.get("min_value"),
                        metadata.get("max_value"),
                        metadata.get("distinct_count"),
                        metadata.get("null_count"),
                        top_values,
                    ),
                )

            conn.commit()
            logger.debug("Stored metadata batch of %d columns", len(metadata_list))

    def get_column_metadata(
        self,
        username: str,
        dataset_id: UUID,
        column_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve column metadata from database.

        Fetches column metadata for a specific column or all columns in a dataset.

        Args:
            username: Username for schema context
            dataset_id: UUID of the dataset
            column_name: Optional specific column name (if None, returns all columns)

        Returns:
            List of metadata dictionaries with keys:
            - id: UUID
            - dataset_id: UUID
            - column_name: str
            - min_value: str | None
            - max_value: str | None
            - distinct_count: int
            - null_count: int
            - top_values: list[dict] | None (parsed from JSONB)
            - computed_at: datetime

        Raises:
            Exception: On database operation failure
        """
        schema_name: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_name}, public")

            if column_name is not None:
                # Query specific column
                query: str = """
                        SELECT
                            id,
                            dataset_id,
                            column_name,
                            min_value,
                            max_value,
                            distinct_count,
                            null_count,
                            top_values,
                            computed_at
                        FROM column_metadata
                        WHERE dataset_id = %s AND column_name = %s
                    """
                cur.execute(query, (dataset_id, column_name))
            else:
                # Query all columns for dataset
                query = """
                        SELECT
                            id,
                            dataset_id,
                            column_name,
                            min_value,
                            max_value,
                            distinct_count,
                            null_count,
                            top_values,
                            computed_at
                        FROM column_metadata
                        WHERE dataset_id = %s
                        ORDER BY column_name
                    """
                cur.execute(query, (dataset_id,))

            rows: list[tuple[Any, ...]] = cur.fetchall()

            # Convert rows to dictionaries
            results: list[dict[str, Any]] = []
            for row in rows:
                # Parse top_values from JSONB (row[7])
                top_values: list[dict[str, Any]] | None = None
                if row[7] is not None:
                    # row[7] is already parsed by psycopg (dict or list)
                    if isinstance(row[7], list):
                        top_values = row[7]
                    elif isinstance(row[7], str):
                        # Fallback: parse JSON string if needed
                        top_values = json.loads(row[7])

                metadata_dict: dict[str, Any] = {
                    "id": row[0],
                    "dataset_id": row[1],
                    "column_name": row[2],
                    "min_value": row[3],
                    "max_value": row[4],
                    "distinct_count": row[5],
                    "null_count": row[6],
                    "top_values": top_values,
                    "computed_at": row[8],
                }
                results.append(metadata_dict)

            return results
