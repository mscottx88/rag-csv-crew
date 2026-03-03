"""Unit tests for IndexManagerService.

Tests index name generation utility with 63-character identifier truncation
and MD5 hash suffix per data-model.md Identifier Length Handling.
Tests create_indexes_for_dataset() B-tree, FTS, and error handling.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from unittest.mock import MagicMock, patch

from psycopg import sql
import pytest

from backend.src.models.index_metadata import (
    IndexCapability,
    IndexMetadataEntry,
    IndexStatus,
    IndexType,
)
from backend.src.services.index_manager import (
    IndexCreationError,
    create_indexes_for_dataset,
    generate_index_name,
)


@pytest.mark.unit
class TestGenerateIndexName:
    """Test index name generation with PostgreSQL 63-char limit."""

    def test_normal_name_no_truncation(self) -> None:
        """Test that short names are returned without truncation."""
        name: str = generate_index_name("products_data", "price", "btree")
        assert name == "idx_products_data_price_btree"
        assert len(name) <= 63

    def test_gin_index_name(self) -> None:
        """Test GIN index name for tsvector columns."""
        name: str = generate_index_name("products_data", "name", "gin")
        assert name == "idx_products_data_name_gin"

    def test_hnsw_index_name(self) -> None:
        """Test HNSW index name for vector columns."""
        name: str = generate_index_name("products_data", "description", "hnsw")
        assert name == "idx_products_data_description_hnsw"

    def test_truncation_at_63_chars(self) -> None:
        """Test that long names are truncated to 63 characters max."""
        long_table: str = "very_long_table_name_that_exceeds_normal"
        long_column: str = "very_long_column_name_also_exceeds"
        name: str = generate_index_name(long_table, long_column, "btree")
        assert len(name) <= 63

    def test_truncation_includes_hash(self) -> None:
        """Test that truncated names include 8-char MD5 hash."""
        long_table: str = "very_long_table_name_that_exceeds_normal"
        long_column: str = "very_long_column_name_also_exceeds"
        name: str = generate_index_name(long_table, long_column, "btree")
        # Name should follow pattern: idx_{truncated}_{hash8}_{type}
        assert name.startswith("idx_")
        assert name.endswith("_btree")
        # Hash should be 8 hex characters
        parts: list[str] = name.split("_")
        # The hash is the second-to-last part (before type)
        hash_part: str = parts[-2]
        assert len(hash_part) == 8
        # Verify it's hex
        int(hash_part, 16)

    def test_hash_uniqueness(self) -> None:
        """Test that different table/column combos produce different hashes."""
        name1: str = generate_index_name("a" * 40, "b" * 40, "btree")
        name2: str = generate_index_name("a" * 40, "c" * 40, "btree")
        assert name1 != name2
        assert len(name1) <= 63
        assert len(name2) <= 63

    def test_exactly_63_chars(self) -> None:
        """Test name exactly at 63 chars is not truncated."""
        # idx_ = 4, _btree = 6, middle needs 53
        # 4 + table + _ + col + 6 = 63 => table_col = 53
        table: str = "t" * 26
        col: str = "c" * 26  # idx_ + 26 + _ + 26 + _btree = 4+26+1+26+6 = 63
        name: str = generate_index_name(table, col, "btree")
        assert name == f"idx_{table}_{col}_btree"
        assert len(name) == 63

    def test_64_chars_triggers_truncation(self) -> None:
        """Test name at 64 chars triggers truncation."""
        table: str = "t" * 27
        col: str = "c" * 26  # idx_ + 27 + _ + 26 + _btree = 4+27+1+26+6 = 64
        name: str = generate_index_name(table, col, "btree")
        assert len(name) <= 63
        assert "_btree" in name

    def test_no_trailing_underscore(self) -> None:
        """Test that truncated names don't end with trailing underscore."""
        name: str = generate_index_name("a" * 50, "b" * 50, "btree")
        # Split to get the truncated portion
        # Pattern: idx_{truncated}_{hash8}_{type}
        assert len(name) <= 63
        # No double underscores from truncation
        assert "___" not in name

    def test_consistent_results(self) -> None:
        """Test that same inputs always produce same output."""
        name1: str = generate_index_name("products_data", "name", "gin")
        name2: str = generate_index_name("products_data", "name", "gin")
        assert name1 == name2


def _make_mock_conn() -> MagicMock:
    """Create a mock psycopg Connection with cursor context manager."""
    mock_conn: MagicMock = MagicMock()
    mock_cursor: MagicMock = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


def _get_mock_cursor(mock_conn: MagicMock) -> MagicMock:
    """Get the mock cursor from a mock connection."""
    cursor: MagicMock = mock_conn.cursor.return_value.__enter__.return_value
    return cursor


_TEST_DATASET_ID: str = "12345678-1234-1234-1234-123456789abc"
_TEST_USERNAME: str = "testuser"
_TEST_TABLE: str = "products_data"


@pytest.mark.unit
class TestCreateBtreeIndexes:
    """T007: Test B-tree index creation in create_indexes_for_dataset()."""

    def test_btree_index_created_for_each_column(self) -> None:
        """Test that B-tree indexes are created for all columns."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "name", "type": "TEXT"},
            {"name": "quantity", "type": "INTEGER"},
        ]

        # Mock _is_identifier_column to always return False
        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        # Should have B-tree for all 3 + GIN for 1 TEXT column
        btree_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.BTREE
        ]
        assert len(btree_entries) == 3

    def test_btree_index_names_follow_convention(self) -> None:
        """Test B-tree index names follow idx_{table}_{col}_btree."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        btree_entry: IndexMetadataEntry = results[0]
        assert btree_entry.index_name == "idx_products_data_price_btree"
        assert btree_entry.index_type == IndexType.BTREE
        assert btree_entry.capability == IndexCapability.FILTERING

    def test_btree_uses_create_index_sql(self) -> None:
        """Test that CREATE INDEX IF NOT EXISTS SQL is executed."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        # Verify cursor.execute was called (B-tree CREATE INDEX)
        assert mock_cursor.execute.call_count >= 1
        first_call_arg: object = mock_cursor.execute.call_args_list[0][0][0]
        assert isinstance(first_call_arg, sql.Composed)

    def test_btree_entries_have_status_created(self) -> None:
        """Test that successful B-tree entries have CREATED status."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "quantity", "type": "INTEGER"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        for entry in results:
            if entry.index_type == IndexType.BTREE:
                assert entry.status == IndexStatus.CREATED

    def test_btree_generated_column_is_none(self) -> None:
        """Test B-tree indexes don't have a generated column name."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        btree_entry: IndexMetadataEntry = results[0]
        assert btree_entry.generated_column_name is None


@pytest.mark.unit
class TestCreateFtsIndexes:
    """T008: Test tsvector + GIN index creation for TEXT columns."""

    def test_gin_index_created_for_text_columns(self) -> None:
        """Test GIN index created only for TEXT columns."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "name", "type": "TEXT"},
            {"name": "description", "type": "TEXT"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        gin_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.GIN
        ]
        assert len(gin_entries) == 2

    def test_gin_index_has_generated_tsvector_column(self) -> None:
        """Test GIN entries include _ts_ generated column name."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        gin_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.GIN
        ]
        assert len(gin_entries) == 1
        assert gin_entries[0].generated_column_name == "_ts_name"
        assert gin_entries[0].capability == IndexCapability.FULL_TEXT_SEARCH

    def test_gin_index_naming_convention(self) -> None:
        """Test GIN index names follow idx_{table}_{col}_gin."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "description", "type": "TEXT"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        gin_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.GIN
        ]
        assert gin_entries[0].index_name == ("idx_products_data_description_gin")

    def test_identifier_columns_skipped_for_fts(self) -> None:
        """Test FR-002: identifier-like TEXT columns skip FTS."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "sku", "type": "TEXT"},
            {"name": "description", "type": "TEXT"},
        ]

        def _mock_is_identifier(
            _conn: object,
            _schema: str,
            _table: str,
            col_name: str,
        ) -> bool:
            return col_name == "sku"

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            side_effect=_mock_is_identifier,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        gin_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.GIN
        ]
        # Only description should get GIN, not sku
        assert len(gin_entries) == 1
        assert gin_entries[0].column_name == "description"

    def test_fts_executes_alter_table_and_create_index(self) -> None:
        """Test FTS creates tsvector column and GIN index via SQL."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        # Should have: B-tree CREATE INDEX + ALTER TABLE + GIN CREATE
        # Plus metadata inserts
        assert mock_cursor.execute.call_count >= 3

    def test_no_gin_for_non_text_columns(self) -> None:
        """Test only TEXT columns get GIN indexes."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
            {"name": "quantity", "type": "INTEGER"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            results: list[IndexMetadataEntry] = create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        gin_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.GIN
        ]
        assert len(gin_entries) == 0


@pytest.mark.unit
class TestCreateIndexesErrorHandling:
    """T009: Test error handling in create_indexes_for_dataset()."""

    @patch("backend.src.services.index_manager._insert_metadata_entry")
    def test_btree_failure_raises_index_creation_error(
        self,
        _mock_insert: MagicMock,
    ) -> None:
        """Test IndexCreationError raised on B-tree creation failure."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.execute.side_effect = RuntimeError("DB error")

        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with pytest.raises(IndexCreationError) as exc_info:
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        assert "B-tree" in str(exc_info.value)
        assert exc_info.value.failed_index == ("idx_products_data_price_btree")

    @patch("backend.src.services.index_manager._insert_metadata_entry")
    def test_fts_failure_raises_index_creation_error(
        self,
        _mock_insert: MagicMock,
    ) -> None:
        """Test IndexCreationError raised on FTS creation failure."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        call_count: int = 0

        def _side_effect(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            # First call succeeds (B-tree for 'name')
            if call_count == 1:
                return
            # Second call fails (ALTER TABLE for tsvector)
            raise RuntimeError("ALTER TABLE failed")

        mock_cursor.execute.side_effect = _side_effect

        columns: list[dict[str, str]] = [
            {"name": "name", "type": "TEXT"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            with pytest.raises(IndexCreationError) as exc_info:
                create_indexes_for_dataset(
                    mock_conn,
                    _TEST_USERNAME,
                    _TEST_DATASET_ID,
                    _TEST_TABLE,
                    columns,
                )

        assert "FTS" in str(exc_info.value)

    @patch("backend.src.services.index_manager._insert_metadata_entry")
    def test_partial_results_populated_on_failure(
        self,
        _mock_insert: MagicMock,
    ) -> None:
        """Test partial_results contains successful entries."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        call_count: int = 0

        def _side_effect(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            # First 2 B-tree calls succeed, 3rd fails
            if call_count <= 2:
                return
            raise RuntimeError("Third index failed")

        mock_cursor.execute.side_effect = _side_effect

        columns: list[dict[str, str]] = [
            {"name": "col_a", "type": "NUMERIC"},
            {"name": "col_b", "type": "NUMERIC"},
            {"name": "col_c", "type": "NUMERIC"},
        ]

        with pytest.raises(IndexCreationError) as exc_info:
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        # First 2 succeeded before failure
        assert len(exc_info.value.partial_results) == 2
        assert exc_info.value.partial_results[0].column_name == "col_a"
        assert exc_info.value.partial_results[1].column_name == "col_b"

    def test_failed_entry_metadata_inserted(self) -> None:
        """Test that failed index gets metadata recorded."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        call_count: int = 0

        def _side_effect(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            # First call (CREATE INDEX) fails
            if call_count == 1:
                raise RuntimeError("DB error")
            # Subsequent calls (metadata insert) succeed

        mock_cursor.execute.side_effect = _side_effect

        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with pytest.raises(IndexCreationError):
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        # Should have called commit after recording failure
        mock_conn.commit.assert_called()

    def test_metadata_committed_on_success(self) -> None:
        """Test conn.commit() called after successful index creation."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with patch(
            "backend.src.services.index_manager._is_identifier_column",
            return_value=False,
        ):
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        mock_conn.commit.assert_called_once()
