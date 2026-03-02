"""Index manager service for creating and tracking database indexes.

Implements index creation, metadata tracking, and context generation
for the SQL generation task per FR-001 through FR-023.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import hashlib

from backend.src.models.index_metadata import IndexMetadataEntry
from backend.src.utils.logging import get_structured_logger

logger = get_structured_logger(__name__)


class IndexCreationError(Exception):
    """Raised when index creation fails during ingestion.

    Contains partial results for diagnostics per FR-012.

    Attributes:
        partial_results: Successfully created index entries before failure
        failed_index: Name of the index that failed to create
    """

    def __init__(
        self,
        message: str,
        partial_results: list[IndexMetadataEntry],
        failed_index: str,
    ) -> None:
        """Initialize IndexCreationError.

        Args:
            message: Human-readable error description
            partial_results: Successfully created index entries before failure
            failed_index: Name of the index that failed to create
        """
        super().__init__(message)
        self.partial_results: list[IndexMetadataEntry] = partial_results
        self.failed_index: str = failed_index


_MAX_IDENTIFIER_LENGTH: int = 63


def generate_index_name(
    table_name: str,
    column_name: str,
    index_type: str,
) -> str:
    """Generate a PostgreSQL index name with 63-character limit handling.

    Pattern: idx_{table}_{column}_{type}
    If the full name exceeds 63 characters, truncates the table+column
    portion and appends an 8-character MD5 hash for uniqueness.

    Truncated pattern: idx_{truncated}_{hash8}_{type}

    Args:
        table_name: Name of the data table
        column_name: Name of the column being indexed
        index_type: Index type suffix (btree, gin, hnsw)

    Returns:
        PostgreSQL-safe index name (max 63 characters)
    """
    full_name: str = f"idx_{table_name}_{column_name}_{index_type}"

    if len(full_name) <= _MAX_IDENTIFIER_LENGTH:
        return full_name

    # Need to truncate: idx_{truncated}_{hash8}_{type}
    # Fixed parts: "idx_" (4) + "_" (1) + hash8 (8) + "_" (1) + type
    hash_input: str = f"{table_name}_{column_name}"
    hash_suffix: str = hashlib.md5(hash_input.encode()).hexdigest()[:8]

    # Calculate available space for the truncated portion
    # Format: idx_{truncated}_{hash8}_{type}
    prefix_len: int = 4  # "idx_"
    separator_len: int = 2  # two underscores around hash
    hash_len: int = 8
    type_len: int = len(index_type)
    overhead: int = prefix_len + separator_len + hash_len + type_len
    available: int = _MAX_IDENTIFIER_LENGTH - overhead

    # Truncate the table+column portion
    truncated: str = f"{table_name}_{column_name}"[:available]

    # Remove trailing underscore if truncation landed on one
    truncated = truncated.rstrip("_")

    return f"idx_{truncated}_{hash_suffix}_{index_type}"
