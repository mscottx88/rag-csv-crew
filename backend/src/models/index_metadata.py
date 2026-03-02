"""Index metadata models for tracking database indexes on data columns.

Defines Pydantic models for index metadata registry per data-model.md:
- IndexType, IndexCapability, IndexStatus enums (StrEnum)
- IndexMetadataEntry: single index record
- DataColumnIndexProfile: aggregate view of all indexes on a column

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- Thread-based operations only (no async/await)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IndexType(StrEnum):
    """PostgreSQL index type.

    Enforced at application layer (no database CHECK constraint).

    Values:
        BTREE: Standard B-tree index for filtering and sorting
        GIN: Generalized Inverted Index for full-text search
        HNSW: Hierarchical Navigable Small World for vector similarity
    """

    BTREE = "btree"
    GIN = "gin"
    HNSW = "hnsw"


class IndexCapability(StrEnum):
    """Search capability enabled by an index.

    Enforced at application layer (no database CHECK constraint).
    B-tree indexes use FILTERING (sorting is implicit in INDEX CAPABILITIES context).

    Values:
        FILTERING: Standard filtering and sorting (B-tree)
        FULL_TEXT_SEARCH: Full-text search via tsvector/tsquery (GIN)
        VECTOR_SIMILARITY: Vector cosine distance search (HNSW)
    """

    FILTERING = "filtering"
    FULL_TEXT_SEARCH = "full_text_search"
    VECTOR_SIMILARITY = "vector_similarity"


class IndexStatus(StrEnum):
    """Index creation status.

    Tracks lifecycle of index creation during ingestion.

    Values:
        PENDING: Index creation not yet started
        CREATED: Index successfully created in PostgreSQL
        FAILED: Index creation failed (logged, ingestion fails per FR-013)
    """

    PENDING = "pending"
    CREATED = "created"
    FAILED = "failed"


class IndexMetadataEntry(BaseModel):
    """Single index metadata record.

    Represents one index on a data column in the index_metadata registry.
    Maps to a row in {username}_schema.index_metadata.

    Attributes:
        id: Unique identifier for the index metadata entry
        dataset_id: The dataset this index belongs to
        column_name: The data column name (sanitized, matches table column)
        index_name: The PostgreSQL index name (truncated with hash if >63 chars)
        index_type: One of: btree, gin, hnsw
        capability: One of: filtering, full_text_search, vector_similarity
        generated_column_name: Name of system-generated column (e.g., _ts_name),
            NULL for B-tree indexes which use the original column
        status: One of: pending, created, failed
        created_at: When the index metadata was recorded
    """

    id: UUID
    dataset_id: UUID
    column_name: str = Field(..., min_length=1, max_length=255)
    index_name: str = Field(..., min_length=1, max_length=255)
    index_type: IndexType
    capability: IndexCapability
    generated_column_name: str | None = None
    status: IndexStatus = IndexStatus.PENDING
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DataColumnIndexProfile(BaseModel):
    """Aggregate view of all indexes on a single data column.

    Used by the SQL generation task to understand the full set of
    query strategies available for each column.

    Attributes:
        column_name: The data column name
        dataset_id: The dataset this column belongs to
        indexes: All index metadata entries for this column
    """

    column_name: str
    dataset_id: UUID
    indexes: list[IndexMetadataEntry]

    @property
    def has_fulltext(self) -> bool:
        """Check if column has a created full-text search index."""
        return any(
            idx.capability == IndexCapability.FULL_TEXT_SEARCH and idx.status == IndexStatus.CREATED
            for idx in self.indexes
        )

    @property
    def has_vector(self) -> bool:
        """Check if column has a created vector similarity index."""
        return any(
            idx.capability == IndexCapability.VECTOR_SIMILARITY
            and idx.status == IndexStatus.CREATED
            for idx in self.indexes
        )

    @property
    def fulltext_column(self) -> str | None:
        """Get the generated tsvector column name, if available."""
        for idx in self.indexes:
            if (
                idx.capability == IndexCapability.FULL_TEXT_SEARCH
                and idx.status == IndexStatus.CREATED
            ):
                return idx.generated_column_name
        return None

    @property
    def embedding_column(self) -> str | None:
        """Get the generated embedding column name, if available."""
        for idx in self.indexes:
            if (
                idx.capability == IndexCapability.VECTOR_SIMILARITY
                and idx.status == IndexStatus.CREATED
            ):
                return idx.generated_column_name
        return None
