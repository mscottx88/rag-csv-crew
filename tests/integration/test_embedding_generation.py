"""Integration tests for embedding generation on real PostgreSQL.

T033: Tests create_embedding_indexes() against a real database:
- Vector column (_emb_) created
- HNSW index created in pg_indexes
- Embeddings populated for qualifying rows
- Index metadata entry with capability=vector_similarity

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from psycopg_pool import ConnectionPool
import pytest

from backend.src.models.index_metadata import DataColumnIndexProfile
from backend.src.services.index_manager import (
    create_embedding_indexes,
    get_index_profiles,
)
from backend.src.services.schema_manager import ensure_user_schema_exists

_TEST_USERNAME: str = "alice"
_SCHEMA: str = f"{_TEST_USERNAME}_schema"


def _create_dataset_row(
    pool: ConnectionPool,
    dataset_id: str,
    filename: str,
) -> None:
    """Insert a dataset row into the datasets table.

    Args:
        pool: Database connection pool.
        dataset_id: UUID for the dataset.
        filename: Dataset filename.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {_SCHEMA}.datasets "
            "(id, filename, original_filename, table_name, "
            "row_count, column_count, file_size_bytes, schema_json) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                dataset_id,
                filename,
                f"{filename}.csv",
                f"{filename}_data",
                0,
                1,
                100,
                '{"columns": []}',
            ),
        )
        conn.commit()


def _delete_dataset_row(
    pool: ConnectionPool,
    dataset_id: str,
) -> None:
    """Delete a dataset row from the datasets table.

    Args:
        pool: Database connection pool.
        dataset_id: UUID of the dataset to delete.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM {_SCHEMA}.datasets WHERE id = %s",
            (dataset_id,),
        )
        conn.commit()


def _create_test_table(
    pool: ConnectionPool,
    table_name: str,
    columns: list[dict[str, str]],
    rows: list[list[Any]],
) -> None:
    """Create a test data table and insert rows.

    Args:
        pool: Database connection pool.
        table_name: Table name within user schema.
        columns: Column definitions (name, type).
        rows: Row data to insert.
    """
    col_defs: str = ", ".join(f"{c['name']} {c['type']}" for c in columns)
    create_sql: str = f"CREATE TABLE IF NOT EXISTS {_SCHEMA}.{table_name}" f" ({col_defs})"

    placeholders: str = ", ".join(["%s"] * len(columns))
    insert_sql: str = f"INSERT INTO {_SCHEMA}.{table_name}" f" VALUES ({placeholders})"

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(create_sql)
        for row in rows:
            cur.execute(insert_sql, tuple(row))
        conn.commit()


def _cleanup_test_table(
    pool: ConnectionPool,
    table_name: str,
) -> None:
    """Drop a test table.

    Args:
        pool: Database connection pool.
        table_name: Table name to drop.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{table_name} CASCADE")
        conn.commit()


@pytest.mark.integration
class TestEmbeddingGenerationIntegration:
    """T033: Integration test for embedding generation end-to-end."""

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_vector_column_created(
        self,
        mock_vs_cls: MagicMock,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test _emb_ vector column created on table."""
        table_name: str = "test_emb_col"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "description", "type": "TEXT"},
        ]
        rows: list[list[Any]] = [
            [
                "A detailed product description that is long enough"
                " for full-text search indexing to be useful",
            ],
            [
                "Another comprehensive description with sufficient"
                " length for embedding generation testing",
            ],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_dataset_row(connection_pool, dataset_id, "test_emb")
        _create_test_table(connection_pool, table_name, columns, rows)

        mock_vs: MagicMock = MagicMock()
        mock_vs.generate_embedding.return_value = [0.1] * 1536
        mock_vs_cls.return_value = mock_vs

        try:
            with connection_pool.connection() as conn:
                create_embedding_indexes(
                    conn=conn,
                    username=_TEST_USERNAME,
                    dataset_id=dataset_id,
                    table_name=table_name,
                    qualifying_columns=["description"],
                )

            # Verify _emb_description column exists
            with connection_pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM"
                    " information_schema.columns"
                    " WHERE table_schema = %s"
                    " AND table_name = %s"
                    " AND column_name = %s",
                    (_SCHEMA, table_name, "_emb_description"),
                )
                emb_col: tuple[str, ...] | None = cur.fetchone()

            assert emb_col is not None
        finally:
            _cleanup_test_table(connection_pool, table_name)
            _delete_dataset_row(connection_pool, dataset_id)

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_hnsw_index_in_pg_indexes(
        self,
        mock_vs_cls: MagicMock,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test HNSW index visible in pg_indexes catalog."""
        table_name: str = "test_hnsw_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "description", "type": "TEXT"},
        ]
        rows: list[list[Any]] = [
            [
                "A detailed product description that is long enough"
                " for full-text search indexing and embedding test",
            ],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_dataset_row(connection_pool, dataset_id, "test_hnsw")
        _create_test_table(connection_pool, table_name, columns, rows)

        mock_vs: MagicMock = MagicMock()
        mock_vs.generate_embedding.return_value = [0.1] * 1536
        mock_vs_cls.return_value = mock_vs

        try:
            with connection_pool.connection() as conn:
                create_embedding_indexes(
                    conn=conn,
                    username=_TEST_USERNAME,
                    dataset_id=dataset_id,
                    table_name=table_name,
                    qualifying_columns=["description"],
                )

            # Verify HNSW index exists
            with connection_pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT indexname FROM pg_indexes"
                    " WHERE schemaname = %s"
                    " AND tablename = %s"
                    " AND indexname LIKE %s",
                    (_SCHEMA, table_name, "idx_%_hnsw"),
                )
                hnsw_indexes: list[tuple[str, ...]] = cur.fetchall()

            hnsw_names: list[str] = [r[0] for r in hnsw_indexes]
            assert len(hnsw_names) == 1
            assert "description" in hnsw_names[0]
        finally:
            _cleanup_test_table(connection_pool, table_name)
            _delete_dataset_row(connection_pool, dataset_id)

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_metadata_entry_vector_similarity(
        self,
        mock_vs_cls: MagicMock,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test index_metadata has capability=vector_similarity."""
        table_name: str = "test_emb_meta"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "description", "type": "TEXT"},
        ]
        rows: list[list[Any]] = [
            [
                "A detailed product description that is long enough"
                " for embedding generation and metadata test",
            ],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_dataset_row(connection_pool, dataset_id, "test_emb_m")
        _create_test_table(connection_pool, table_name, columns, rows)

        mock_vs: MagicMock = MagicMock()
        mock_vs.generate_embedding.return_value = [0.1] * 1536
        mock_vs_cls.return_value = mock_vs

        try:
            with connection_pool.connection() as conn:
                create_embedding_indexes(
                    conn=conn,
                    username=_TEST_USERNAME,
                    dataset_id=dataset_id,
                    table_name=table_name,
                    qualifying_columns=["description"],
                )

            with connection_pool.connection() as conn:
                profiles: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
                    conn,
                    _TEST_USERNAME,
                    [dataset_id],
                )

            assert dataset_id in profiles
            profile_list: list[DataColumnIndexProfile] = profiles[dataset_id]
            desc_profile: DataColumnIndexProfile = next(
                p for p in profile_list if p.column_name == "description"
            )
            assert desc_profile.has_vector is True
            assert desc_profile.embedding_column == "_emb_description"
        finally:
            _cleanup_test_table(connection_pool, table_name)
            _delete_dataset_row(connection_pool, dataset_id)
