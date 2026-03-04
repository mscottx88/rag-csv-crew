# Contract: IndexManagerService

**Feature**: 003-index-aware-sql
**Date**: 2026-03-02
**Module**: `backend/src/services/index_manager.py`

## Service Interface

This is an internal service (not exposed via API). It is called by the ingestion pipeline and the SQL generation task builder.

### create_indexes_for_dataset

Creates all indexes (B-tree, tsvector+GIN) for a newly ingested dataset's data table.

```python
def create_indexes_for_dataset(
    conn: Connection[tuple[str, ...]],
    username: str,
    dataset_id: str,
    table_name: str,
    columns: list[dict[str, Any]],
) -> list[IndexMetadataEntry]:
    """Create B-tree and full-text search indexes on all data columns.

    Args:
        conn: Active database connection (caller manages transaction).
        username: User's username (determines schema name).
        dataset_id: UUID of the dataset.
        table_name: Name of the data table (e.g., 'products_data').
        columns: List of column definitions from schema detection.
            Each dict has keys: 'name' (str), 'type' (str), 'nullable' (bool).

    Returns:
        List of IndexMetadataEntry objects for all created indexes.

    Raises:
        IndexCreationError: If any index creation fails.
            Contains partial_results with successfully created indexes.
    """
```

**Behavior**:
1. For each column in `columns`:
   a. Create B-tree index: `idx_{table}_{col}_btree`
   b. Record metadata entry with status='created' or status='failed'
   c. If column type is TEXT:
      - ALTER TABLE to add `_ts_{col}` tsvector generated column
      - Create GIN index: `idx_{table}_{col}_gin`
      - Record metadata entry
2. Insert all metadata entries into `index_metadata` table
3. If any index creation fails, raise `IndexCreationError` (ingestion fails per FR-013)

### create_embedding_indexes

Creates vector embedding columns and HNSW indexes for qualifying text columns (P2).

```python
def create_embedding_indexes(
    pool: ConnectionPool,
    username: str,
    dataset_id: str,
    table_name: str,
    qualifying_columns: list[str],
) -> list[IndexMetadataEntry]:
    """Generate embeddings for data values and create HNSW indexes.

    Args:
        pool: Connection pool for database access (takes pool, not conn,
            because ThreadPoolExecutor needs multiple connections for
            parallel embedding writes).
        username: User's username.
        dataset_id: UUID of the dataset.
        table_name: Name of the data table.
        qualifying_columns: Column names that qualify for embeddings
            (avg text length >= threshold).

    Returns:
        List of IndexMetadataEntry objects for created HNSW indexes.
    """
```

**Behavior**:
1. For each qualifying column:
   a. ALTER TABLE to add `_emb_{col}` vector(1536) column
   b. Read all text values from the column (NULL and empty strings skipped — set to NULL embedding)
   c. Generate embeddings via VectorSearchService (ThreadPoolExecutor, 10-20 workers)
      - Retry failed rows up to 3 times
      - If >90% rows succeed, proceed; otherwise raise error
   d. Batch UPDATE embeddings into the vector column (500 rows per batch per FR-022)
   e. Create HNSW index: `idx_{table}_{col}_hnsw`
   f. Record metadata entry

**Note on `pool` vs `conn`**: This method takes `ConnectionPool` (not `Connection`) because it uses `ThreadPoolExecutor` internally for parallel embedding generation and needs to acquire multiple connections for concurrent batch writes. In contrast, `create_indexes_for_dataset` takes a single `Connection` because it runs sequential DDL as part of the ingestion pipeline where the caller manages the connection.

### get_index_profiles

Retrieves index capability profiles for columns in the target dataset(s).

```python
def get_index_profiles(
    conn: Connection[tuple[str, ...]],
    username: str,
    dataset_ids: list[str],
) -> dict[str, list[DataColumnIndexProfile]]:
    """Get index profiles for all columns across the specified datasets.

    Args:
        conn: Active database connection.
        username: User's username.
        dataset_ids: List of dataset UUIDs to query.

    Returns:
        Dict mapping dataset_id to list of DataColumnIndexProfile objects.
        Each profile contains all indexes for a single column.
    """
```

**Behavior**:
1. Query `index_metadata` for all entries matching the dataset_ids
2. Group by (dataset_id, column_name)
3. Return as dict of DataColumnIndexProfile objects

### build_index_context

Builds the text context string to inject into the SQL generation task.

```python
def build_index_context(
    profiles: dict[str, list[DataColumnIndexProfile]],
    table_names: dict[str, str],
) -> str:
    """Build the INDEX CAPABILITIES context string for the SQL generation task.

    Args:
        profiles: Index profiles from get_index_profiles().
        table_names: Dict mapping dataset_id to table_name.

    Returns:
        Formatted text block describing available indexes and query patterns
        for each column across all target datasets.
    """
```

**Behavior**:
1. For each dataset and each column profile:
   a. List B-tree capability (always present for data columns)
   b. If has_fulltext: include tsvector column name and query pattern
   c. If has_vector: include embedding column name and distance operator pattern
2. Format as the structured text block documented in research.md R4

### identify_qualifying_columns

Identifies text columns that qualify for data value embeddings.

```python
def identify_qualifying_columns(
    conn: Connection[tuple[str, ...]],
    username: str,
    table_name: str,
    text_columns: list[str],
    min_avg_length: int = 50,
    sample_size: int = 1000,
) -> list[str]:
    """Identify text columns with sufficient content for embeddings.

    Args:
        conn: Active database connection.
        username: User's username.
        table_name: Data table name.
        text_columns: List of TEXT column names to evaluate.
        min_avg_length: Minimum average character length threshold.
        sample_size: Number of rows to sample for average calculation.

    Returns:
        List of column names that qualify for embedding generation.
    """
```

**Behavior**:
1. For each text column, compute `AVG(LENGTH(col))` over a sample
2. Return columns where average length >= `min_avg_length`

## Error Types

```python
class IndexCreationError(Exception):
    """Raised when index creation fails."""

    def __init__(
        self,
        message: str,
        partial_results: list[IndexMetadataEntry],
        failed_index: str,
    ) -> None:
        super().__init__(message)
        self.partial_results: list[IndexMetadataEntry] = partial_results
        self.failed_index: str = failed_index
```
