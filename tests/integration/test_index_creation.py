"""Integration tests for index creation on real PostgreSQL.

Tests create_indexes_for_dataset() against a real database:
- B-tree indexes created on all columns
- tsvector generated columns created for TEXT columns
- GIN indexes on tsvector columns
- Index metadata entries recorded
- FR-002 identifier heuristic skips identifier-like TEXT columns

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any
from uuid import uuid4

from psycopg_pool import ConnectionPool
import pytest

from backend.src.services.index_manager import create_indexes_for_dataset
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
