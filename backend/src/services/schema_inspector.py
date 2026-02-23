"""Schema Inspector Service for database introspection.

Provides methods to query database schemas, retrieve column details,
and discover relationships between datasets. Used by Schema Inspector Agent
to provide context for SQL query generation.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg_pool import ConnectionPool

from src.services.column_metadata import ColumnMetadataService


class SchemaInspectorService:
    """Service for inspecting database schemas and providing context to agents.

    Provides structured access to:
    - Available datasets and their tables
    - Column names, types, and descriptions
    - Cross-references and relationships
    - Sample data for context
    """

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize SchemaInspectorService.

        Args:
            pool: Database connection pool for schema queries
        """
        self.pool: ConnectionPool = pool

    def get_available_datasets(
        self, username: str, dataset_ids: list[UUID] | None = None
    ) -> list[dict[str, Any]]:
        """Get list of available datasets with metadata.

        Args:
            username: Username for schema isolation
            dataset_ids: Optional filter for specific datasets

        Returns:
            List of datasets with id, filename, table_name, row_count, column_count

        Example:
            [
                {
                    "id": "uuid-string",
                    "filename": "customers.csv",
                    "table_name": "customers_data",
                    "row_count": 1000,
                    "column_count": 8,
                    "uploaded_at": "2024-01-15T10:30:00Z"
                }
            ]
        """
        user_schema: str = f"{username}_schema"
        datasets: list[dict[str, Any]] = []

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            # Build dataset filter
            filter_clause: str = ""
            filter_params: tuple[Any, ...] = ()
            if dataset_ids:
                dataset_id_strs: list[str] = [str(dataset_id) for dataset_id in dataset_ids]
                filter_clause = " WHERE id = ANY(%s)"
                filter_params = (dataset_id_strs,)

            cur.execute(
                f"""
                SELECT id, filename, row_count, column_count, uploaded_at
                FROM datasets
                {filter_clause}
                ORDER BY uploaded_at DESC
                """,
                filter_params,
            )

            rows: list[tuple[Any, ...]] = cur.fetchall()

            for row in rows:
                dataset_id: str = str(row[0])
                filename: str = row[1]

                # Construct table name (same logic as ingestion)
                table_name: str = (
                    filename.replace(".csv", "_data")
                    if filename.endswith(".csv")
                    else f"{filename}_data"
                )

                datasets.append(
                    {
                        "id": dataset_id,
                        "filename": filename,
                        "table_name": table_name,
                        "row_count": row[2],
                        "column_count": row[3],
                        "uploaded_at": str(row[4]),
                    }
                )

        return datasets

    def get_dataset_schema(self, username: str, dataset_id: UUID) -> dict[str, Any]:
        """Get complete schema for a specific dataset.

        Args:
            username: Username for schema isolation
            dataset_id: UUID of the dataset

        Returns:
            Dictionary with dataset metadata and column details

        Raises:
            ValueError: If dataset not found

        Example:
            {
                "dataset_id": "uuid-string",
                "filename": "customers.csv",
                "table_name": "customers_data",
                "columns": [
                    {
                        "name": "customer_id",
                        "type": "INTEGER",
                        "description": "Unique customer identifier"
                    }
                ]
            }
        """
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            # Get dataset info
            cur.execute(
                """
                SELECT filename, row_count, column_count
                FROM datasets
                WHERE id = %s
                """,
                (str(dataset_id),),
            )

            dataset_row: tuple[Any, ...] | None = cur.fetchone()
            if dataset_row is None:
                raise ValueError(f"Dataset {dataset_id} not found")

            filename: str = dataset_row[0]
            table_name: str = (
                filename.replace(".csv", "_data")
                if filename.endswith(".csv")
                else f"{filename}_data"
            )

            # Get column details
            cur.execute(
                """
                SELECT column_name, inferred_type, description
                FROM column_mappings
                WHERE dataset_id = %s
                ORDER BY column_name
                """,
                (str(dataset_id),),
            )

            column_rows: list[tuple[Any, ...]] = cur.fetchall()
            columns: list[dict[str, Any]] = []

            for column_row in column_rows:
                columns.append(
                    {
                        "name": column_row[0],
                        "type": column_row[1],
                        "description": column_row[2] if column_row[2] else "",
                    }
                )

            return {
                "dataset_id": str(dataset_id),
                "filename": filename,
                "table_name": table_name,
                "row_count": dataset_row[1],
                "column_count": dataset_row[2],
                "columns": columns,
            }

    def get_column_details(
        self, username: str, dataset_id: UUID, column_name: str
    ) -> dict[str, Any]:
        """Get detailed information about a specific column.

        Args:
            username: Username for schema isolation
            dataset_id: UUID of the dataset
            column_name: Name of the column

        Returns:
            Dictionary with column metadata including statistics (min/max, distinct count, etc.)

        Raises:
            ValueError: If column not found

        Example:
            {
                "column_name": "customer_id",
                "inferred_type": "INTEGER",
                "description": "Unique customer identifier",
                "semantic_type": "identifier",
                "min_value": "1",
                "max_value": "1000",
                "distinct_count": 1000,
                "null_count": 0,
                "top_values": [{"value": "1", "count": 5}]
            }
        """
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            cur.execute(
                """
                SELECT column_name, inferred_type, semantic_type, description
                FROM column_mappings
                WHERE dataset_id = %s AND column_name = %s
                """,
                (str(dataset_id), column_name),
            )

            row: tuple[Any, ...] | None = cur.fetchone()
            if row is None:
                raise ValueError(f"Column '{column_name}' not found in dataset {dataset_id}")

            column_details: dict[str, Any] = {
                "column_name": row[0],
                "inferred_type": row[1],
                "semantic_type": row[2] if row[2] else "",
                "description": row[3] if row[3] else "",
            }

            # Enrich with column metadata (min/max, distinct count, top values)
            try:
                metadata_service: ColumnMetadataService = ColumnMetadataService(self.pool)
                metadata_list: list[dict[str, Any]] = metadata_service.get_column_metadata(
                    username=username,
                    dataset_id=dataset_id,
                    column_name=column_name,
                )

                if metadata_list:
                    metadata: dict[str, Any] = metadata_list[0]
                    column_details["min_value"] = metadata.get("min_value")
                    column_details["max_value"] = metadata.get("max_value")
                    column_details["distinct_count"] = metadata.get("distinct_count")
                    column_details["null_count"] = metadata.get("null_count")
                    column_details["top_values"] = metadata.get("top_values")
            except Exception:  # pylint: disable=broad-exception-caught
                # JUSTIFICATION: Metadata enrichment is optional - if unavailable,
                # return basic column details without statistics
                pass

            return column_details

    def get_relationships(self, username: str, dataset_ids: list[UUID]) -> list[dict[str, Any]]:
        """Get cross-references between specified datasets.

        Args:
            username: Username for schema isolation
            dataset_ids: List of dataset UUIDs to find relationships between

        Returns:
            List of relationships with source/target info

        Example:
            [
                {
                    "source_dataset_id": "uuid1",
                    "source_column": "customer_id",
                    "target_dataset_id": "uuid2",
                    "target_column": "customer_id",
                    "relationship_type": "foreign_key",
                    "confidence_score": 0.95
                }
            ]
        """
        user_schema: str = f"{username}_schema"
        relationships: list[dict[str, Any]] = []

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            dataset_id_strs: list[str] = [str(dataset_id) for dataset_id in dataset_ids]

            cur.execute(
                """
                SELECT
                    source_dataset_id,
                    source_column,
                    target_dataset_id,
                    target_column,
                    relationship_type,
                    confidence_score
                FROM cross_references
                WHERE source_dataset_id = ANY(%s)
                  AND target_dataset_id = ANY(%s)
                ORDER BY confidence_score DESC
                """,
                (dataset_id_strs, dataset_id_strs),
            )

            rows: list[tuple[Any, ...]] = cur.fetchall()
            for row in rows:
                relationships.append(
                    {
                        "source_dataset_id": row[0],
                        "source_column": row[1],
                        "target_dataset_id": row[2],
                        "target_column": row[3],
                        "relationship_type": row[4],
                        "confidence_score": row[5],
                    }
                )

        return relationships

    def get_sample_data(self, username: str, dataset_id: UUID, limit: int = 5) -> dict[str, Any]:
        """Get sample rows from a dataset table.

        Args:
            username: Username for schema isolation
            dataset_id: UUID of the dataset
            limit: Number of sample rows to retrieve (default: 5)

        Returns:
            Dictionary with columns and sample rows

        Raises:
            ValueError: If dataset not found

        Example:
            {
                "table_name": "customers_data",
                "columns": ["customer_id", "name", "email"],
                "rows": [
                    [1, "John Doe", "john@example.com"],
                    [2, "Jane Smith", "jane@example.com"]
                ]
            }
        """
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            # Get dataset filename
            cur.execute(
                """
                SELECT filename
                FROM datasets
                WHERE id = %s
                """,
                (str(dataset_id),),
            )

            row: tuple[Any, ...] | None = cur.fetchone()
            if row is None:
                raise ValueError(f"Dataset {dataset_id} not found")

            filename: str = row[0]
            table_name: str = (
                filename.replace(".csv", "_data")
                if filename.endswith(".csv")
                else f"{filename}_data"
            )

            # Get column names
            cur.execute(
                """
                SELECT column_name
                FROM column_mappings
                WHERE dataset_id = %s
                ORDER BY column_name
                """,
                (str(dataset_id),),
            )

            column_rows: list[tuple[Any, ...]] = cur.fetchall()
            columns: list[str] = [str(col_row[0]) for col_row in column_rows]

            # Get sample data
            cur.execute(
                sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(table_name)),
                (limit,),
            )

            data_rows: list[tuple[Any, ...]] = cur.fetchall()
            rows: list[list[Any]] = [list(data_row) for data_row in data_rows]

            return {"table_name": table_name, "columns": columns, "rows": rows}
