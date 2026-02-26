"""Response model for paginated dataset row retrieval.

Defines the Pydantic model for GET /datasets/{dataset_id}/rows
endpoint response.

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from typing import Any

from pydantic import BaseModel, Field


class DatasetRowsResponse(BaseModel):
    """Paginated rows from a dataset table.

    Returns raw data rows with column metadata for display
    in the Dataset Inspector frontend component.

    Attributes:
        dataset_id: UUID of the dataset
        table_name: PostgreSQL table name
        columns: Ordered list of user-facing column names
        rows: 2D array of cell values (row-major order)
        total_row_count: Total rows in the dataset
        offset: Starting row index for this page
        limit: Maximum rows requested
        has_more: Whether more rows exist beyond this page
    """

    dataset_id: str
    table_name: str
    columns: list[str]
    rows: list[list[Any]]
    total_row_count: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=500)
    has_more: bool
