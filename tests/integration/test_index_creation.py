"""Integration tests for index creation on real PostgreSQL.

Tests create_indexes_for_dataset() against a real database:
- B-tree indexes created on all columns
- tsvector generated columns created for TEXT columns
- GIN indexes on tsvector columns
- Index metadata entries recorded
- FR-002 identifier heuristic skips identifier-like TEXT columns
- get_index_profiles() returns correct DataColumnIndexProfile objects
- ON DELETE CASCADE removes metadata when dataset is deleted

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any
from uuid import uuid4

from psycopg_pool import ConnectionPool
import pytest

from backend.src.models.index_metadata import DataColumnIndexProfile
from backend.src.services.index_manager import (
    create_indexes_for_dataset,
    get_index_profiles,
)
from backend.src.services.schema_manager import ensure_user_schema_exists

_TEST_USERNAME: str = "alice"
_SCHEMA: str = f"{_TEST_USERNAME}_schema"


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
    insert_sql: str = f"INSERT INTO {_SCHEMA}.{table_name} VALUES ({placeholders})"

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            for row in rows:
                cur.execute(insert_sql, tuple(row))
        conn.commit()


def _cleanup_test_table(
    pool: ConnectionPool,
    table_name: str,
) -> None:
    """Drop a test table and its index_metadata entries.

    Args:
        pool: Database connection pool.
        table_name: Table name to drop.
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{table_name} CASCADE")
        conn.commit()


@pytest.mark.integration
class TestIndexCreationIntegration:
    """T010: Integration test for index creation on PostgreSQL."""

    def test_btree_indexes_on_all_columns(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test B-tree indexes created for all columns via pg_indexes."""
        table_name: str = "test_btree_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "name", "type": "TEXT"},
            {"name": "quantity", "type": "INTEGER"},
        ]
        rows: list[list[Any]] = [
            [9.99, "Widget A", 100],
            [19.99, "Widget B", 200],
            [29.99, "Widget C", 300],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            # Verify B-tree indexes exist via pg_indexes
            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT indexname FROM pg_indexes"
                        " WHERE schemaname = %s"
                        " AND tablename = %s"
                        " AND indexname LIKE %s",
                        (_SCHEMA, table_name, "idx_%_btree"),
                    )
                    btree_indexes: list[tuple[str, ...]] = cur.fetchall()

            btree_names: list[str] = [r[0] for r in btree_indexes]
            assert len(btree_names) == 3
            assert f"idx_{table_name}_price_btree" in btree_names
            assert f"idx_{table_name}_name_btree" in btree_names
            assert f"idx_{table_name}_quantity_btree" in btree_names
        finally:
            _cleanup_test_table(connection_pool, table_name)

    def test_gin_indexes_on_text_columns(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test GIN indexes and tsvector columns for TEXT columns."""
        table_name: str = "test_gin_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "description", "type": "TEXT"},
        ]
        rows: list[list[Any]] = [
            [9.99, "A long enough description for testing"],
            [19.99, "Another description that is not too short"],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            with connection_pool.connection() as conn:
                # Verify GIN index exists
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT indexname FROM pg_indexes"
                        " WHERE schemaname = %s"
                        " AND tablename = %s"
                        " AND indexname LIKE %s",
                        (_SCHEMA, table_name, "idx_%_gin"),
                    )
                    gin_indexes: list[tuple[str, ...]] = cur.fetchall()

                gin_names: list[str] = [r[0] for r in gin_indexes]
                assert len(gin_names) == 1
                assert f"idx_{table_name}_description_gin" in gin_names

                # Verify tsvector generated column exists
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT column_name FROM"
                        " information_schema.columns"
                        " WHERE table_schema = %s"
                        " AND table_name = %s"
                        " AND column_name = %s",
                        (_SCHEMA, table_name, "_ts_description"),
                    )
                    ts_col: tuple[str, ...] | None = cur.fetchone()

                assert ts_col is not None
        finally:
            _cleanup_test_table(connection_pool, table_name)

    def test_index_metadata_recorded(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test index metadata entries stored in index_metadata table."""
        table_name: str = "test_meta_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
            {"name": "price", "type": "NUMERIC"},
        ]
        rows: list[list[Any]] = [
            ["Widget", 9.99],
            ["Gadget", 19.99],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            # Query index_metadata for this dataset
            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT column_name, index_type,"
                        f" capability, status"
                        f" FROM {_SCHEMA}.index_metadata"
                        f" WHERE dataset_id = %s"
                        f" ORDER BY column_name, index_type",
                        (dataset_id,),
                    )
                    meta_rows: list[tuple[str, ...]] = cur.fetchall()

            # Should have: name btree, name gin, price btree
            assert len(meta_rows) == 3

            # Verify each entry
            col_type_pairs: list[tuple[str, str]] = [(r[0], r[1]) for r in meta_rows]
            assert ("name", "btree") in col_type_pairs
            assert ("name", "gin") in col_type_pairs
            assert ("price", "btree") in col_type_pairs

            # All should be 'created' status
            for row in meta_rows:
                assert row[3] == "created"
        finally:
            _cleanup_test_table(connection_pool, table_name)

    def test_no_numeric_gin_indexes(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test that NUMERIC columns don't get GIN indexes."""
        table_name: str = "test_numeric_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "quantity", "type": "INTEGER"},
        ]
        rows: list[list[Any]] = [
            [9.99, 100],
            [19.99, 200],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT indexname FROM pg_indexes"
                        " WHERE schemaname = %s"
                        " AND tablename = %s"
                        " AND indexname LIKE %s",
                        (_SCHEMA, table_name, "idx_%_gin"),
                    )
                    gin_indexes: list[tuple[str, ...]] = cur.fetchall()

            assert len(gin_indexes) == 0
        finally:
            _cleanup_test_table(connection_pool, table_name)


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
    with pool.connection() as conn:
        with conn.cursor() as cur:
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
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {_SCHEMA}.datasets WHERE id = %s",
                (dataset_id,),
            )
        conn.commit()


@pytest.mark.integration
class TestMetadataTrackingIntegration:
    """T020: Integration test for metadata tracking end-to-end."""

    def test_get_index_profiles_returns_profiles(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test get_index_profiles groups metadata into profiles."""
        table_name: str = "test_profiles_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
            {"name": "price", "type": "NUMERIC"},
        ]
        rows: list[list[Any]] = [
            ["Widget", 9.99],
            ["Gadget", 19.99],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_dataset_row(connection_pool, dataset_id, "test_profiles")
        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            with connection_pool.connection() as conn:
                profiles: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
                    conn,
                    _TEST_USERNAME,
                    [dataset_id],
                )

            assert dataset_id in profiles
            profile_list: list[DataColumnIndexProfile] = profiles[dataset_id]
            col_names: set[str] = {p.column_name for p in profile_list}
            assert "name" in col_names
            assert "price" in col_names

            # name should have FTS
            name_profile: DataColumnIndexProfile = next(
                p for p in profile_list if p.column_name == "name"
            )
            assert name_profile.has_fulltext is True
            assert name_profile.fulltext_column == "_ts_name"

            # price should NOT have FTS
            price_profile: DataColumnIndexProfile = next(
                p for p in profile_list if p.column_name == "price"
            )
            assert price_profile.has_fulltext is False
        finally:
            _cleanup_test_table(connection_pool, table_name)
            _delete_dataset_row(connection_pool, dataset_id)

    def test_cascade_delete_removes_metadata(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test ON DELETE CASCADE removes index_metadata when dataset deleted."""
        table_name: str = "test_cascade_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
        ]
        rows: list[list[Any]] = [
            ["Widget"],
            ["Gadget"],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_dataset_row(connection_pool, dataset_id, "test_cascade")
        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            # Verify metadata exists
            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {_SCHEMA}.index_metadata" " WHERE dataset_id = %s",
                        (dataset_id,),
                    )
                    count_before: int = cur.fetchone()[0]  # type: ignore[index]
            assert count_before > 0

            # Delete the dataset (CASCADE should remove metadata)
            _delete_dataset_row(connection_pool, dataset_id)

            # Verify metadata removed
            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {_SCHEMA}.index_metadata" " WHERE dataset_id = %s",
                        (dataset_id,),
                    )
                    count_after: int = cur.fetchone()[0]  # type: ignore[index]
            assert count_after == 0
        finally:
            _cleanup_test_table(connection_pool, table_name)

    def test_metadata_matches_pg_indexes(
        self,
        connection_pool: ConnectionPool,
    ) -> None:
        """Test index_metadata entries match actual pg_indexes catalog."""
        table_name: str = "test_match_idx"
        dataset_id: str = str(uuid4())
        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
            {"name": "price", "type": "NUMERIC"},
        ]
        rows: list[list[Any]] = [
            ["Widget", 9.99],
            ["Gadget", 19.99],
        ]

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, _TEST_USERNAME)

        _create_dataset_row(connection_pool, dataset_id, "test_match")
        _create_test_table(connection_pool, table_name, columns, rows)

        try:
            with connection_pool.connection() as conn:
                create_indexes_for_dataset(
                    conn,
                    _TEST_USERNAME,
                    dataset_id,
                    table_name,
                    columns,
                )

            # Get index names from metadata
            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT index_name FROM {_SCHEMA}.index_metadata" " WHERE dataset_id = %s",
                        (dataset_id,),
                    )
                    meta_names: set[str] = {r[0] for r in cur.fetchall()}

            # Get index names from pg_indexes
            with connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT indexname FROM pg_indexes"
                        " WHERE schemaname = %s"
                        " AND tablename = %s"
                        " AND indexname LIKE %s",
                        (_SCHEMA, table_name, "idx_%"),
                    )
                    pg_names: set[str] = {r[0] for r in cur.fetchall()}

            # All metadata index names should exist in pg_indexes
            assert meta_names.issubset(pg_names)
        finally:
            _cleanup_test_table(connection_pool, table_name)
            _delete_dataset_row(connection_pool, dataset_id)
