"""Unit tests for index metadata Pydantic models.

Tests IndexType, IndexCapability, IndexStatus enums,
IndexMetadataEntry validation, and DataColumnIndexProfile properties.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest

from backend.src.models.index_metadata import (
    DataColumnIndexProfile,
    IndexCapability,
    IndexMetadataEntry,
    IndexStatus,
    IndexType,
)


def _make_entry(
    index_type: IndexType = IndexType.BTREE,
    capability: IndexCapability = IndexCapability.FILTERING,
    status: IndexStatus = IndexStatus.CREATED,
    generated_column_name: str | None = None,
    column_name: str = "name",
    dataset_id: UUID | None = None,
) -> IndexMetadataEntry:
    """Create an IndexMetadataEntry for testing."""
    return IndexMetadataEntry(
        id=uuid4(),
        dataset_id=dataset_id or uuid4(),
        column_name=column_name,
        index_name=f"idx_test_{column_name}_{index_type.value}",
        index_type=index_type,
        capability=capability,
        generated_column_name=generated_column_name,
        status=status,
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
class TestIndexType:
    """Test IndexType StrEnum values."""

    def test_values(self) -> None:
        """Test that IndexType has exactly btree, gin, hnsw values."""
        assert IndexType.BTREE == "btree"
        assert IndexType.GIN == "gin"
        assert IndexType.HNSW == "hnsw"
        members: list[str] = [m.value for m in IndexType]
        assert members == ["btree", "gin", "hnsw"]


@pytest.mark.unit
class TestIndexCapability:
    """Test IndexCapability StrEnum values."""

    def test_values(self) -> None:
        """Test that IndexCapability has filtering, full_text_search, vector_similarity."""
        assert IndexCapability.FILTERING == "filtering"
        assert IndexCapability.FULL_TEXT_SEARCH == "full_text_search"
        assert IndexCapability.VECTOR_SIMILARITY == "vector_similarity"
        members: list[str] = [m.value for m in IndexCapability]
        assert members == ["filtering", "full_text_search", "vector_similarity"]


@pytest.mark.unit
class TestIndexStatus:
    """Test IndexStatus StrEnum values."""

    def test_values(self) -> None:
        """Test that IndexStatus has pending, created, failed."""
        assert IndexStatus.PENDING == "pending"
        assert IndexStatus.CREATED == "created"
        assert IndexStatus.FAILED == "failed"


@pytest.mark.unit
class TestIndexMetadataEntry:
    """Test IndexMetadataEntry Pydantic model validation."""

    def test_valid_entry(self) -> None:
        """Test creating a valid index metadata entry."""
        entry: IndexMetadataEntry = _make_entry()
        assert entry.column_name == "name"
        assert entry.index_type == IndexType.BTREE
        assert entry.capability == IndexCapability.FILTERING
        assert entry.status == IndexStatus.CREATED
        assert entry.generated_column_name is None

    def test_generated_column_name(self) -> None:
        """Test entry with generated column name for tsvector."""
        entry: IndexMetadataEntry = _make_entry(
            index_type=IndexType.GIN,
            capability=IndexCapability.FULL_TEXT_SEARCH,
            generated_column_name="_ts_name",
        )
        assert entry.generated_column_name == "_ts_name"

    def test_default_status_pending(self) -> None:
        """Test that default status is pending."""
        entry: IndexMetadataEntry = IndexMetadataEntry(
            id=uuid4(),
            dataset_id=uuid4(),
            column_name="col",
            index_name="idx_test_col_btree",
            index_type=IndexType.BTREE,
            capability=IndexCapability.FILTERING,
            created_at=datetime.now(UTC),
        )
        assert entry.status == IndexStatus.PENDING

    def test_column_name_min_length(self) -> None:
        """Test that column_name must be at least 1 character."""
        with pytest.raises(ValidationError):
            IndexMetadataEntry(
                id=uuid4(),
                dataset_id=uuid4(),
                column_name="",
                index_name="idx",
                index_type=IndexType.BTREE,
                capability=IndexCapability.FILTERING,
                created_at=datetime.now(UTC),
            )

    def test_index_name_min_length(self) -> None:
        """Test that index_name must be at least 1 character."""
        with pytest.raises(ValidationError):
            IndexMetadataEntry(
                id=uuid4(),
                dataset_id=uuid4(),
                column_name="col",
                index_name="",
                index_type=IndexType.BTREE,
                capability=IndexCapability.FILTERING,
                created_at=datetime.now(UTC),
            )


@pytest.mark.unit
class TestDataColumnIndexProfile:
    """Test DataColumnIndexProfile properties."""

    def test_has_fulltext_true(self) -> None:
        """Test has_fulltext returns True when FTS index is created."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="description",
            dataset_id=ds_id,
            indexes=[
                _make_entry(
                    dataset_id=ds_id,
                    column_name="description",
                ),
                _make_entry(
                    index_type=IndexType.GIN,
                    capability=IndexCapability.FULL_TEXT_SEARCH,
                    generated_column_name="_ts_description",
                    dataset_id=ds_id,
                    column_name="description",
                ),
            ],
        )
        assert profile.has_fulltext is True

    def test_has_fulltext_false_when_failed(self) -> None:
        """Test has_fulltext returns False when FTS index failed."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="name",
            dataset_id=ds_id,
            indexes=[
                _make_entry(
                    index_type=IndexType.GIN,
                    capability=IndexCapability.FULL_TEXT_SEARCH,
                    status=IndexStatus.FAILED,
                    generated_column_name="_ts_name",
                    dataset_id=ds_id,
                    column_name="name",
                ),
            ],
        )
        assert profile.has_fulltext is False

    def test_has_fulltext_false_no_fts(self) -> None:
        """Test has_fulltext returns False when only B-tree exists."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="price",
            dataset_id=ds_id,
            indexes=[
                _make_entry(dataset_id=ds_id, column_name="price"),
            ],
        )
        assert profile.has_fulltext is False

    def test_has_vector_true(self) -> None:
        """Test has_vector returns True when HNSW index is created."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="description",
            dataset_id=ds_id,
            indexes=[
                _make_entry(
                    index_type=IndexType.HNSW,
                    capability=IndexCapability.VECTOR_SIMILARITY,
                    generated_column_name="_emb_description",
                    dataset_id=ds_id,
                    column_name="description",
                ),
            ],
        )
        assert profile.has_vector is True

    def test_has_vector_false(self) -> None:
        """Test has_vector returns False when no HNSW index."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="name",
            dataset_id=ds_id,
            indexes=[
                _make_entry(dataset_id=ds_id, column_name="name"),
            ],
        )
        assert profile.has_vector is False

    def test_fulltext_column(self) -> None:
        """Test fulltext_column returns generated column name."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="title",
            dataset_id=ds_id,
            indexes=[
                _make_entry(
                    index_type=IndexType.GIN,
                    capability=IndexCapability.FULL_TEXT_SEARCH,
                    generated_column_name="_ts_title",
                    dataset_id=ds_id,
                    column_name="title",
                ),
            ],
        )
        assert profile.fulltext_column == "_ts_title"

    def test_fulltext_column_none(self) -> None:
        """Test fulltext_column returns None when no FTS."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="price",
            dataset_id=ds_id,
            indexes=[
                _make_entry(dataset_id=ds_id, column_name="price"),
            ],
        )
        assert profile.fulltext_column is None

    def test_embedding_column(self) -> None:
        """Test embedding_column returns generated column name."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="description",
            dataset_id=ds_id,
            indexes=[
                _make_entry(
                    index_type=IndexType.HNSW,
                    capability=IndexCapability.VECTOR_SIMILARITY,
                    generated_column_name="_emb_description",
                    dataset_id=ds_id,
                    column_name="description",
                ),
            ],
        )
        assert profile.embedding_column == "_emb_description"

    def test_embedding_column_none(self) -> None:
        """Test embedding_column returns None when no vector index."""
        ds_id: UUID = uuid4()
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name="name",
            dataset_id=ds_id,
            indexes=[
                _make_entry(dataset_id=ds_id, column_name="name"),
            ],
        )
        assert profile.embedding_column is None
