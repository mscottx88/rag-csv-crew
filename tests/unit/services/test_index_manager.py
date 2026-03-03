"""Unit tests for IndexManagerService.

Tests index name generation utility with 63-character identifier truncation
and MD5 hash suffix per data-model.md Identifier Length Handling.
Tests create_indexes_for_dataset() B-tree, FTS, and error handling.
Tests get_index_profiles() and build_index_context() for metadata tracking.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from psycopg import sql
import pytest

from backend.src.models.index_metadata import (
    DataColumnIndexProfile,
    IndexCapability,
    IndexMetadataEntry,
    IndexStatus,
    IndexType,
)
from backend.src.services.index_manager import (
    IndexCreationError,
    build_index_context,
    create_embedding_indexes,
    create_indexes_for_dataset,
    generate_index_name,
    get_index_profiles,
    identify_qualifying_columns,
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


# --- Phase 4: US3 Metadata Tracking Tests ---


def _make_entry(
    column_name: str,
    index_type: IndexType,
    capability: IndexCapability,
    dataset_id: UUID | None = None,
    generated_column_name: str | None = None,
    index_status: IndexStatus = IndexStatus.CREATED,
) -> IndexMetadataEntry:
    """Helper to create an IndexMetadataEntry for tests."""
    ds_id: UUID = dataset_id if dataset_id is not None else UUID(_TEST_DATASET_ID)
    idx_name: str = f"idx_{_TEST_TABLE}_{column_name}_{index_type.value}"
    return IndexMetadataEntry(
        id=uuid4(),
        dataset_id=ds_id,
        column_name=column_name,
        index_name=idx_name,
        index_type=index_type,
        capability=capability,
        generated_column_name=generated_column_name,
        status=index_status,
        created_at=datetime.now(UTC),
    )


def _make_profile(
    column_name: str,
    entries: list[IndexMetadataEntry],
    dataset_id: UUID | None = None,
) -> DataColumnIndexProfile:
    """Helper to create a DataColumnIndexProfile for tests."""
    ds_id: UUID = dataset_id if dataset_id is not None else UUID(_TEST_DATASET_ID)
    return DataColumnIndexProfile(
        column_name=column_name,
        dataset_id=ds_id,
        indexes=entries,
    )


@pytest.mark.unit
class TestMetadataInsertion:
    """T017: Test index metadata insertion correctness."""

    def test_btree_metadata_entries_correct(self) -> None:
        """Test B-tree indexes produce correct metadata entries."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
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

        btree_entries: list[IndexMetadataEntry] = [
            e for e in results if e.index_type == IndexType.BTREE
        ]
        assert len(btree_entries) == 2
        for entry in btree_entries:
            assert entry.status == IndexStatus.CREATED
            assert entry.capability == IndexCapability.FILTERING
            assert entry.dataset_id == UUID(_TEST_DATASET_ID)

    def test_gin_metadata_entries_correct(self) -> None:
        """Test GIN indexes produce correct metadata entries."""
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
        assert gin_entries[0].capability == IndexCapability.FULL_TEXT_SEARCH
        assert gin_entries[0].generated_column_name == "_ts_name"
        assert gin_entries[0].status == IndexStatus.CREATED

    def test_metadata_insert_sql_called(self) -> None:
        """Test _insert_metadata_entry called for each index."""
        mock_conn: MagicMock = _make_mock_conn()
        columns: list[dict[str, str]] = [
            {"name": "price", "type": "NUMERIC"},
        ]

        with (
            patch(
                "backend.src.services.index_manager._is_identifier_column",
                return_value=False,
            ),
            patch(
                "backend.src.services.index_manager._insert_metadata_entry",
            ) as mock_insert,
        ):
            create_indexes_for_dataset(
                mock_conn,
                _TEST_USERNAME,
                _TEST_DATASET_ID,
                _TEST_TABLE,
                columns,
            )

        # 1 B-tree entry for price
        assert mock_insert.call_count == 1

    def test_unique_constraint_on_dataset_column_type(self) -> None:
        """Test that each entry has unique (dataset_id, column_name, index_type)."""
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

        # name gets both btree and gin = 2 entries, unique combo
        keys: set[tuple[UUID, str, IndexType]] = set()
        for entry in results:
            key: tuple[UUID, str, IndexType] = (
                entry.dataset_id,
                entry.column_name,
                entry.index_type,
            )
            assert key not in keys, f"Duplicate key: {key}"
            keys.add(key)


@pytest.mark.unit
class TestGetIndexProfiles:
    """T018: Test get_index_profiles() grouping and profile creation."""

    def test_returns_empty_dict_for_no_datasets(self) -> None:
        """Test empty list returns empty dict."""
        mock_conn: MagicMock = _make_mock_conn()
        result: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
            mock_conn,
            _TEST_USERNAME,
            [],
        )
        assert result == {}

    def test_groups_by_dataset_and_column(self) -> None:
        """Test entries grouped into DataColumnIndexProfile objects."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        ds_id: str = _TEST_DATASET_ID
        now: datetime = datetime.now(UTC)
        entry_id_1: UUID = uuid4()
        entry_id_2: UUID = uuid4()

        # Simulate two rows: name btree and name gin
        mock_cursor.fetchall.return_value = [
            (
                entry_id_1,
                UUID(ds_id),
                "name",
                "idx_t_name_btree",
                "btree",
                "filtering",
                None,
                "created",
                now,
            ),
            (
                entry_id_2,
                UUID(ds_id),
                "name",
                "idx_t_name_gin",
                "gin",
                "full_text_search",
                "_ts_name",
                "created",
                now,
            ),
        ]

        result: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
            mock_conn,
            _TEST_USERNAME,
            [ds_id],
        )

        assert ds_id in result
        profiles: list[DataColumnIndexProfile] = result[ds_id]
        assert len(profiles) == 1
        assert profiles[0].column_name == "name"
        assert len(profiles[0].indexes) == 2

    def test_multiple_columns_create_separate_profiles(self) -> None:
        """Test different columns produce separate profiles."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        ds_id: str = _TEST_DATASET_ID
        now: datetime = datetime.now(UTC)

        mock_cursor.fetchall.return_value = [
            (
                uuid4(),
                UUID(ds_id),
                "name",
                "idx_t_name_btree",
                "btree",
                "filtering",
                None,
                "created",
                now,
            ),
            (
                uuid4(),
                UUID(ds_id),
                "price",
                "idx_t_price_btree",
                "btree",
                "filtering",
                None,
                "created",
                now,
            ),
        ]

        result: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
            mock_conn,
            _TEST_USERNAME,
            [ds_id],
        )

        profiles: list[DataColumnIndexProfile] = result[ds_id]
        assert len(profiles) == 2
        col_names: set[str] = {p.column_name for p in profiles}
        assert col_names == {"name", "price"}

    def test_multiple_datasets_separated(self) -> None:
        """Test entries from different datasets are in separate keys."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        ds_id_1: str = _TEST_DATASET_ID
        ds_id_2: str = str(uuid4())
        now: datetime = datetime.now(UTC)

        mock_cursor.fetchall.return_value = [
            (
                uuid4(),
                UUID(ds_id_1),
                "name",
                "idx_t1_name_btree",
                "btree",
                "filtering",
                None,
                "created",
                now,
            ),
            (
                uuid4(),
                UUID(ds_id_2),
                "price",
                "idx_t2_price_btree",
                "btree",
                "filtering",
                None,
                "created",
                now,
            ),
        ]

        result: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
            mock_conn,
            _TEST_USERNAME,
            [ds_id_1, ds_id_2],
        )

        assert ds_id_1 in result
        assert ds_id_2 in result
        assert result[ds_id_1][0].column_name == "name"
        assert result[ds_id_2][0].column_name == "price"

    def test_profile_has_fulltext_property(self) -> None:
        """Test DataColumnIndexProfile.has_fulltext with FTS index."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)

        ds_id: str = _TEST_DATASET_ID
        now: datetime = datetime.now(UTC)

        mock_cursor.fetchall.return_value = [
            (
                uuid4(),
                UUID(ds_id),
                "name",
                "idx_t_name_btree",
                "btree",
                "filtering",
                None,
                "created",
                now,
            ),
            (
                uuid4(),
                UUID(ds_id),
                "name",
                "idx_t_name_gin",
                "gin",
                "full_text_search",
                "_ts_name",
                "created",
                now,
            ),
        ]

        result: dict[str, list[DataColumnIndexProfile]] = get_index_profiles(
            mock_conn,
            _TEST_USERNAME,
            [ds_id],
        )

        profile: DataColumnIndexProfile = result[ds_id][0]
        assert profile.has_fulltext is True
        assert profile.fulltext_column == "_ts_name"
        assert profile.has_vector is False


@pytest.mark.unit
class TestBuildIndexContext:
    """T019: Test build_index_context() formatting and rules."""

    def test_empty_profiles_returns_empty_string(self) -> None:
        """Test empty profiles produces empty string."""
        result: str = build_index_context({}, {})
        assert result == ""

    def test_btree_only_column(self) -> None:
        """Test B-tree only column shows correct capabilities."""
        btree_entry: IndexMetadataEntry = _make_entry(
            "price",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        profile: DataColumnIndexProfile = _make_profile(
            "price",
            [btree_entry],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: [profile],
        }
        table_names: dict[str, str] = {_TEST_DATASET_ID: _TEST_TABLE}

        result: str = build_index_context(profiles, table_names)

        assert "Table: products_data" in result
        assert "Column: price" in result
        assert "B-tree: supports" in result
        assert "Full-text search" not in result
        assert "Vector similarity" not in result

    def test_fts_column_includes_search_pattern(self) -> None:
        """Test TEXT column with FTS includes tsvector query pattern."""
        btree_entry: IndexMetadataEntry = _make_entry(
            "name",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        gin_entry: IndexMetadataEntry = _make_entry(
            "name",
            IndexType.GIN,
            IndexCapability.FULL_TEXT_SEARCH,
            generated_column_name="_ts_name",
        )
        profile: DataColumnIndexProfile = _make_profile(
            "name",
            [btree_entry, gin_entry],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: [profile],
        }
        table_names: dict[str, str] = {_TEST_DATASET_ID: _TEST_TABLE}

        result: str = build_index_context(profiles, table_names)

        assert "Full-text search via '_ts_name'" in result
        assert "plainto_tsquery" in result
        assert "ts_rank" in result
        assert "PREFER full-text search" in result

    def test_context_includes_rules_section(self) -> None:
        """Test context includes RULES section at the end."""
        btree_entry: IndexMetadataEntry = _make_entry(
            "price",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        profile: DataColumnIndexProfile = _make_profile(
            "price",
            [btree_entry],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: [profile],
        }
        table_names: dict[str, str] = {_TEST_DATASET_ID: _TEST_TABLE}

        result: str = build_index_context(profiles, table_names)

        assert "RULES:" in result
        assert "ALWAYS use full-text search" in result
        assert "B-tree indexes are always available" in result

    def test_context_includes_header(self) -> None:
        """Test context starts with INDEX CAPABILITIES header."""
        btree_entry: IndexMetadataEntry = _make_entry(
            "price",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        profile: DataColumnIndexProfile = _make_profile(
            "price",
            [btree_entry],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: [profile],
        }
        table_names: dict[str, str] = {_TEST_DATASET_ID: _TEST_TABLE}

        result: str = build_index_context(profiles, table_names)

        assert result.startswith("INDEX CAPABILITIES")

    def test_4000_char_cap(self) -> None:
        """Test context truncated at 4000 characters per FR-018."""
        entries: list[IndexMetadataEntry] = []
        profiles_list: list[DataColumnIndexProfile] = []
        # Create many columns to exceed 4000 chars
        for i in range(50):
            col_name: str = f"column_{i:03d}_with_a_long_name"
            btree: IndexMetadataEntry = _make_entry(
                col_name,
                IndexType.BTREE,
                IndexCapability.FILTERING,
            )
            gin: IndexMetadataEntry = _make_entry(
                col_name,
                IndexType.GIN,
                IndexCapability.FULL_TEXT_SEARCH,
                generated_column_name=f"_ts_{col_name}",
            )
            entries.extend([btree, gin])
            profiles_list.append(
                _make_profile(col_name, [btree, gin]),
            )

        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: profiles_list,
        }
        table_names: dict[str, str] = {_TEST_DATASET_ID: _TEST_TABLE}

        result: str = build_index_context(profiles, table_names)

        assert len(result) <= 4000
        assert result.endswith("...")

    def test_text_column_type_annotation(self) -> None:
        """Test TEXT columns labeled correctly in output."""
        btree_entry: IndexMetadataEntry = _make_entry(
            "description",
            IndexType.BTREE,
            IndexCapability.FILTERING,
        )
        gin_entry: IndexMetadataEntry = _make_entry(
            "description",
            IndexType.GIN,
            IndexCapability.FULL_TEXT_SEARCH,
            generated_column_name="_ts_description",
        )
        profile: DataColumnIndexProfile = _make_profile(
            "description",
            [btree_entry, gin_entry],
        )
        profiles: dict[str, list[DataColumnIndexProfile]] = {
            _TEST_DATASET_ID: [profile],
        }
        table_names: dict[str, str] = {_TEST_DATASET_ID: _TEST_TABLE}

        result: str = build_index_context(profiles, table_names)

        assert "Column: description (TEXT)" in result
        assert "LIKE 'prefix%'" in result


@pytest.mark.unit
class TestIdentifyQualifyingColumns:
    """T031: Unit tests for identify_qualifying_columns()."""

    def test_long_text_qualifies(self) -> None:
        """Test columns with avg length >= 50 qualify for embeddings."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # AVG(LENGTH(col)) = 75.0
        mock_cursor.fetchone.return_value = (75.0,)

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["description"],
        )

        assert result == ["description"]

    def test_short_text_excluded(self) -> None:
        """Test columns with avg length < 50 are excluded."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # AVG(LENGTH(col)) = 10.0 (short, like "Widget")
        mock_cursor.fetchone.return_value = (10.0,)

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["name"],
        )

        assert result == []

    def test_configurable_threshold(self) -> None:
        """Test custom min_avg_length threshold."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # avg 30 chars — under default 50, above custom 20
        mock_cursor.fetchone.return_value = (30.0,)

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["notes"],
            min_avg_length=20,
        )

        assert result == ["notes"]

    def test_empty_columns_list(self) -> None:
        """Test empty columns list returns empty result."""
        mock_conn: MagicMock = _make_mock_conn()

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            [],
        )

        assert result == []

    def test_null_avg_excluded(self) -> None:
        """Test columns with NULL avg (empty data) are excluded."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchone.return_value = (None,)

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["empty_col"],
        )

        assert result == []

    def test_multiple_columns_mixed(self) -> None:
        """Test mix of qualifying and non-qualifying columns."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # First col: 75 (qualifies), second col: 10 (doesn't)
        mock_cursor.fetchone.side_effect = [(75.0,), (10.0,)]

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["description", "name"],
        )

        assert result == ["description"]

    def test_sample_size_passed_to_query(self) -> None:
        """Test sample_size is used in the SQL LIMIT clause."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchone.return_value = (60.0,)

        identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["description"],
            sample_size=500,
        )

        call_args: tuple[object, ...] = mock_cursor.execute.call_args[0]
        # The composed SQL should contain the sample_size as Literal(500)
        # Check the string representation of the Composed object
        query_repr: str = repr(call_args[0])
        assert "500" in query_repr

    def test_exact_threshold_qualifies(self) -> None:
        """Test columns with avg exactly equal to threshold qualify."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchone.return_value = (50.0,)

        result: list[str] = identify_qualifying_columns(
            mock_conn,
            _TEST_USERNAME,
            _TEST_TABLE,
            ["notes"],
        )

        assert result == ["notes"]


@pytest.mark.unit
class TestCreateEmbeddingIndexes:
    """T032: Unit tests for create_embedding_indexes()."""

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_vector_column_added(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test ALTER TABLE adds _emb_ vector column."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchall.return_value = []

        mock_vs: MagicMock = MagicMock()
        mock_vs_cls.return_value = mock_vs

        create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=["description"],
        )

        # Should execute ALTER TABLE ADD COLUMN _emb_description vector(1536)
        calls: list[tuple[object, ...]] = [c[0] for c in mock_cursor.execute.call_args_list]
        alter_found: bool = any("_emb_description" in str(c) and "vector" in str(c) for c in calls)
        assert alter_found, "Expected ALTER TABLE with _emb_description vector column"

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_hnsw_index_created(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test HNSW index created on embedding column."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchall.return_value = []

        mock_vs: MagicMock = MagicMock()
        mock_vs_cls.return_value = mock_vs

        create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=["description"],
        )

        calls: list[tuple[object, ...]] = [c[0] for c in mock_cursor.execute.call_args_list]
        hnsw_found: bool = any(
            "hnsw" in str(c).lower() and "_emb_description" in str(c) for c in calls
        )
        assert hnsw_found, "Expected CREATE INDEX USING hnsw"

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_metadata_recorded(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test metadata entry with HNSW type and vector_similarity cap."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchall.return_value = []

        mock_vs: MagicMock = MagicMock()
        mock_vs_cls.return_value = mock_vs

        results: list[IndexMetadataEntry] = create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=["description"],
        )

        assert len(results) == 1
        entry: IndexMetadataEntry = results[0]
        assert entry.index_type == IndexType.HNSW
        assert entry.capability == IndexCapability.VECTOR_SIMILARITY
        assert entry.generated_column_name == "_emb_description"
        assert entry.status == IndexStatus.CREATED

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_null_and_empty_skipped(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test NULL and empty text values get NULL embeddings (FR-020)."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # Simulate rows: (row_id, text_value)
        mock_cursor.fetchall.return_value = [
            (1, "A valid long text for embedding generation"),
            (2, None),
            (3, ""),
            (4, "Another valid text for embedding generation"),
        ]

        mock_vs: MagicMock = MagicMock()
        mock_vs.generate_embedding.return_value = [0.1] * 1536
        mock_vs_cls.return_value = mock_vs

        create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=["description"],
        )

        # Only 2 non-null/non-empty texts should be embedded
        assert mock_vs.generate_embedding.call_count == 2

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_batch_update_500_rows(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test batch UPDATE in 500-row chunks (FR-022)."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # Simulate 1200 rows
        mock_cursor.fetchall.return_value = [
            (i, f"Text value {i} that is long enough for embedding") for i in range(1200)
        ]

        mock_vs: MagicMock = MagicMock()
        mock_vs.generate_embedding.return_value = [0.1] * 1536
        mock_vs_cls.return_value = mock_vs

        create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=["description"],
        )

        # Should have batch UPDATE calls: 500 + 500 + 200 = 3 batches
        update_calls: list[tuple[object, ...]] = [
            c
            for c in mock_cursor.execute.call_args_list
            if "UPDATE" in str(c[0]).upper() and "_emb_" in str(c[0])
        ]
        # executemany or multiple execute calls for batch updates
        assert len(update_calls) >= 3 or mock_cursor.executemany.call_count >= 3

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_retry_on_embedding_failure(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test retry logic for failed embedding generation (FR-021)."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        mock_cursor.fetchall.return_value = [
            (1, "Valid text for embedding generation test"),
        ]

        mock_vs: MagicMock = MagicMock()
        # Fail first 2 times, succeed on 3rd retry
        mock_vs.generate_embedding.side_effect = [
            Exception("API error"),
            Exception("API error"),
            [0.1] * 1536,
        ]
        mock_vs_cls.return_value = mock_vs

        results: list[IndexMetadataEntry] = create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=["description"],
        )

        # Should succeed after retries
        assert len(results) == 1
        assert results[0].status == IndexStatus.CREATED
        # 3 total calls (2 failures + 1 success)
        assert mock_vs.generate_embedding.call_count == 3

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_catastrophic_failure_raises(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test <90% success rate raises IndexCreationError (FR-021)."""
        mock_conn: MagicMock = _make_mock_conn()
        mock_cursor: MagicMock = _get_mock_cursor(mock_conn)
        # 10 rows — need >90% success (at least 9)
        mock_cursor.fetchall.return_value = [
            (i, f"Text value {i} for embedding generation test") for i in range(10)
        ]

        mock_vs: MagicMock = MagicMock()
        # All calls fail (after retries)
        mock_vs.generate_embedding.side_effect = Exception("API down")
        mock_vs_cls.return_value = mock_vs

        with pytest.raises(IndexCreationError):
            create_embedding_indexes(
                conn=mock_conn,
                username=_TEST_USERNAME,
                dataset_id=_TEST_DATASET_ID,
                table_name=_TEST_TABLE,
                qualifying_columns=["description"],
            )

    @patch("backend.src.services.vector_search.VectorSearchService")
    def test_empty_qualifying_columns(
        self,
        mock_vs_cls: MagicMock,
    ) -> None:
        """Test empty qualifying columns returns empty results."""
        mock_conn: MagicMock = _make_mock_conn()

        results: list[IndexMetadataEntry] = create_embedding_indexes(
            conn=mock_conn,
            username=_TEST_USERNAME,
            dataset_id=_TEST_DATASET_ID,
            table_name=_TEST_TABLE,
            qualifying_columns=[],
        )

        assert results == []
