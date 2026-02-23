"""Integration tests for CSV ingestion (T043-T046).

Tests dynamic table creation, bulk COPY ingestion, metadata storage, and filename conflicts.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from io import BytesIO
from typing import Any
import uuid

from psycopg_pool import ConnectionPool
import pytest


@pytest.mark.integration
class TestCSVIngestion:
    """Integration tests for CSV ingestion pipeline (T043-T046)."""

    def test_dynamic_table_creation(self, connection_pool: ConnectionPool) -> None:
        """Test dynamic {filename}_data table creation (T043).

        Validates per data-model.md:
        - Table name: {filename}_data
        - Columns: _row_id, _dataset_id, _ingested_at, dynamic cols, _fulltext
        - Types match CSV schema

        Success Criteria (T043):
        - Table created with correct structure
        - Metadata columns present
        - Dynamic columns from CSV
        """
        from backend.src.services.ingestion import create_dataset_table

        csv_schema: dict[str, Any] = {
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
                {"name": "price", "type": "FLOAT"},
            ]
        }

        with connection_pool.connection() as conn:
            table_name: str = create_dataset_table(
                conn, username="testuser", filename="products", schema=csv_schema
            )

            # Verify table exists
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = 'testuser_schema' AND table_name = %s "
                    "ORDER BY ordinal_position",
                    (table_name,),
                )
                columns: list[tuple[str, str]] = cur.fetchall()

            # Verify metadata columns exist
            column_names: list[str] = [col[0] for col in columns]
            assert "_row_id" in column_names
            assert "_dataset_id" in column_names
            assert "_ingested_at" in column_names
            assert "_fulltext" in column_names

            # Verify dynamic columns from CSV
            assert "id" in column_names
            assert "name" in column_names
            assert "price" in column_names

    def test_bulk_csv_ingestion_with_copy(self, connection_pool: ConnectionPool) -> None:
        """Test bulk CSV ingestion via PostgreSQL COPY (T044).

        Validates per research.md:
        - PostgreSQL COPY protocol used
        - Streaming ingestion
        - Row count accuracy
        - Performance

        Success Criteria (T044):
        - Data ingested efficiently
        - All rows imported
        - Row count matches CSV
        """
        from backend.src.services.ingestion import create_dataset_table, ingest_csv_data

        csv_data: bytes = (
            b"id,name,price\n1,Product A,19.99\n2,Product B,29.99\n3,Product C,39.99\n"
        )
        csv_file: BytesIO = BytesIO(csv_data)

        # Generate valid UUID for test
        test_dataset_id: str = str(uuid.uuid4())

        # Create schema for CSV structure
        csv_schema: dict[str, Any] = {
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
                {"name": "price", "type": "FLOAT"},
            ]
        }

        with connection_pool.connection() as conn:
            # Create table first (test should be independent)
            table_name: str = create_dataset_table(
                conn, username="testuser", filename="products", schema=csv_schema
            )

            row_count: int = ingest_csv_data(
                conn,
                username="testuser",
                table_name=table_name,
                csv_file=csv_file,
                dataset_id=test_dataset_id,
            )

            # Verify row count
            assert row_count == 3

            # Verify data ingested
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM testuser_schema.{table_name} WHERE _dataset_id = %s",
                    (test_dataset_id,),
                )
                result: tuple[int] = cur.fetchone()  # type: ignore
                assert result[0] == 3

    def test_dataset_metadata_storage(self, connection_pool: ConnectionPool) -> None:
        """Test dataset metadata stored in datasets table (T045).

        Validates per data-model.md:
        - Insert into {username}_schema.datasets
        - All required fields populated
        - Schema JSON stored

        Success Criteria (T045):
        - Metadata record created
        - Schema matches data-model.md
        """
        from backend.src.services.ingestion import store_dataset_metadata

        metadata: dict[str, Any] = {
            "filename": "products.csv",
            "original_filename": "my products.csv",
            "table_name": "products_data",
            "row_count": 100,
            "column_count": 5,
            "file_size_bytes": 5000,
            "schema_json": {"columns": [{"name": "id", "type": "INTEGER"}]},
        }

        with connection_pool.connection() as conn:
            dataset_id: str = store_dataset_metadata(conn, username="testuser", metadata=metadata)

            # Verify dataset record exists
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT filename, table_name, row_count FROM testuser_schema.datasets WHERE id = %s",
                    (dataset_id,),
                )
                result: tuple[str, str, int] | None = cur.fetchone()

            assert result is not None
            assert result[0] == "products.csv"
            assert result[1] == "products_data"
            assert result[2] == 100

    def test_filename_conflict_detection(self, connection_pool: ConnectionPool) -> None:
        """Test filename conflict detection and 409 response (T046).

        Validates per FR-022:
        - Detect existing filename
        - Return 409 status
        - Suggest timestamp suffix

        Success Criteria (T046):
        - Conflict detected
        - Suggestion provided
        """
        from backend.src.services.ingestion import check_filename_conflict

        with connection_pool.connection() as conn:
            # First upload
            conflict_info: dict[str, Any] = check_filename_conflict(
                conn, username="testuser", filename="sales"
            )
            assert conflict_info["conflict"] is False

            # Create a dataset
            from backend.src.services.ingestion import store_dataset_metadata

            metadata: dict[str, Any] = {
                "filename": "sales",
                "original_filename": "sales.csv",
                "table_name": "sales_data",
                "row_count": 10,
                "column_count": 3,
                "file_size_bytes": 500,
                "schema_json": {},
            }
            store_dataset_metadata(conn, username="testuser", metadata=metadata)

            # Second upload with same filename
            conflict_info = check_filename_conflict(conn, username="testuser", filename="sales")

            # Verify conflict detected
            assert conflict_info["conflict"] is True
            assert "suggested_filename" in conflict_info
            # Should suggest timestamp suffix like "sales_20240115120000"
            assert conflict_info["suggested_filename"].startswith("sales_")
