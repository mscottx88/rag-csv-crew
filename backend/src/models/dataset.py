"""Dataset models for CSV file management.

Defines Pydantic models for CSV dataset upload, metadata tracking,
and schema inference per FR-001, FR-003, FR-013, FR-014.

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- Thread-based operations only (no async/await)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ColumnSchema(BaseModel):
    """Schema for a single CSV column.

    Describes column metadata including type inference results
    from CSV sampling per FR-014 and data-model.md type mapping.

    Attributes:
        name: Column name from CSV header (1-255 characters)
        inferred_type: PostgreSQL type inferred from data
        nullable: Whether column allows NULL values
        semantic_type: Optional semantic classification
        description: Optional human-readable description
    """

    name: str = Field(..., min_length=1, max_length=255)
    inferred_type: str = Field(
        ...,
        pattern=r"^(text|integer|bigint|numeric|boolean|date|timestamp)$",
    )
    nullable: bool = False
    semantic_type: str | None = None
    description: str | None = None


class DatasetBase(BaseModel):
    """Base dataset model.

    Common fields for dataset creation and retrieval.

    Attributes:
        filename: Display name for the dataset
    """

    filename: str = Field(..., min_length=1, max_length=255)


class DatasetCreate(DatasetBase):
    """Dataset creation request model.

    Used when uploading a new CSV file via POST /datasets.
    File content provided as multipart/form-data.

    Inherits:
        filename: Display name from UserBase
    """


class Dataset(DatasetBase):
    """Complete dataset model with metadata.

    Full dataset information including schema, statistics,
    and ingestion metadata per data-model.md datasets table.

    Attributes:
        id: Unique dataset identifier (UUID)
        filename: Display name (inherited)
        original_filename: Original CSV filename from upload
        table_name: PostgreSQL table name (sanitized)
        uploaded_at: Upload timestamp
        row_count: Number of data rows ingested (>= 0)
        column_count: Number of columns detected (> 0)
        file_size_bytes: Original file size in bytes (> 0)
        schema_json: List of column schemas with types
    """

    id: UUID
    original_filename: str
    table_name: str
    uploaded_at: datetime
    row_count: int = Field(..., ge=0)
    column_count: int = Field(..., gt=0)
    file_size_bytes: int = Field(..., gt=0)
    schema_json: list[ColumnSchema] = Field(...)  # type: ignore[assignment]

    model_config = ConfigDict(from_attributes=True)


class DatasetList(BaseModel):
    """Paginated list of datasets.

    Used for GET /datasets endpoint response with pagination.

    Attributes:
        datasets: List of dataset models
        total_count: Total number of datasets (all pages)
        page: Current page number (1-indexed)
        page_size: Number of items per page
    """

    datasets: list[Dataset]
    total_count: int = Field(..., ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
