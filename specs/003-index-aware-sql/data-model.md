# Data Model: Index-Aware SQL Generation

**Feature**: 003-index-aware-sql
**Date**: 2026-03-02

## New Entity: Index Metadata

### Database Table: `index_metadata`

Created in each per-user schema (`{username}_schema`) alongside existing tables (`datasets`, `column_mappings`, etc.).

```sql
CREATE TABLE IF NOT EXISTS {schema_name}.index_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    index_name VARCHAR(255) NOT NULL,
    index_type VARCHAR(50) NOT NULL,
    capability VARCHAR(50) NOT NULL,
    generated_column_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, column_name, index_type)
);

CREATE INDEX IF NOT EXISTS idx_index_metadata_dataset
    ON {schema_name}.index_metadata (dataset_id);

CREATE INDEX IF NOT EXISTS idx_index_metadata_capability
    ON {schema_name}.index_metadata (capability);
```

### Field Definitions

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, auto-generated | Unique identifier for the index metadata entry |
| dataset_id | UUID | FK → datasets.id, ON DELETE CASCADE | The dataset this index belongs to |
| column_name | VARCHAR(255) | NOT NULL | The data column name (sanitized, matches table column) |
| index_name | VARCHAR(255) | NOT NULL | The PostgreSQL index name (e.g., `idx_products_data_name_btree`). Truncated with hash suffix if >63 chars (see Identifier Length Handling below). |
| index_type | VARCHAR(50) | NOT NULL | One of: `btree`, `gin`, `hnsw`. Enforced at application layer via `IndexType` StrEnum. No database CHECK constraint — the application is the sole writer. |
| capability | VARCHAR(50) | NOT NULL | One of: `filtering`, `full_text_search`, `vector_similarity`. Enforced at application layer via `IndexCapability` StrEnum. B-tree indexes use `filtering` (sorting is an implicit B-tree capability conveyed in the INDEX CAPABILITIES context, not as a separate metadata entry). |
| generated_column_name | VARCHAR(255) | nullable | Name of system-generated column (e.g., `_ts_name`, `_emb_description`). NULL for B-tree indexes which use the original column. |
| status | VARCHAR(20) | NOT NULL, default 'pending' | One of: `pending`, `created`, `failed`. Enforced at application layer via `IndexStatus` StrEnum. |
| created_at | TIMESTAMPTZ | NOT NULL, default NOW() | When the index metadata was recorded |

### Identifier Length Handling

PostgreSQL limits identifiers to 63 characters. Generated index names follow the pattern `idx_{table}_{column}_{type}` which may exceed this limit with long table or column names.

**Truncation strategy**: When the full index name exceeds 63 characters, the system truncates the table+column portion and appends an 8-character MD5 hash for uniqueness:
- Pattern: `idx_{truncated}_{hash8}_{type}`
- Example: `idx_very_long_table_name_very_lo_a1b2c3d4_btree` (63 chars max)
- The `index_name` stored in `index_metadata` always reflects the actual PostgreSQL index name (post-truncation)

### Uniqueness Constraint

`UNIQUE (dataset_id, column_name, index_type)` — A column can have at most one index of each type per dataset. For example, a TEXT column could have entries for `btree`, `gin`, and `hnsw`.

### Cascade Behavior

`ON DELETE CASCADE` from `datasets.id` ensures all index metadata is automatically cleaned up when a dataset is deleted. No additional cleanup code needed beyond the existing `DROP TABLE ... CASCADE` which handles the actual PostgreSQL indexes.

## Pydantic Models

### IndexMetadataEntry

```python
class IndexType(StrEnum):
    BTREE = "btree"
    GIN = "gin"
    HNSW = "hnsw"

class IndexCapability(StrEnum):
    FILTERING = "filtering"
    FULL_TEXT_SEARCH = "full_text_search"
    VECTOR_SIMILARITY = "vector_similarity"

class IndexStatus(StrEnum):
    PENDING = "pending"
    CREATED = "created"
    FAILED = "failed"

class IndexMetadataEntry(BaseModel):
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
```

### DataColumnIndexProfile

```python
class DataColumnIndexProfile(BaseModel):
    column_name: str
    dataset_id: UUID
    indexes: list[IndexMetadataEntry]

    @property
    def has_fulltext(self) -> bool:
        return any(
            idx.capability == IndexCapability.FULL_TEXT_SEARCH
            and idx.status == IndexStatus.CREATED
            for idx in self.indexes
        )

    @property
    def has_vector(self) -> bool:
        return any(
            idx.capability == IndexCapability.VECTOR_SIMILARITY
            and idx.status == IndexStatus.CREATED
            for idx in self.indexes
        )

    @property
    def fulltext_column(self) -> str | None:
        for idx in self.indexes:
            if idx.capability == IndexCapability.FULL_TEXT_SEARCH and idx.status == IndexStatus.CREATED:
                return idx.generated_column_name
        return None

    @property
    def embedding_column(self) -> str | None:
        for idx in self.indexes:
            if idx.capability == IndexCapability.VECTOR_SIMILARITY and idx.status == IndexStatus.CREATED:
                return idx.generated_column_name
        return None
```

## Modified Entities

### Data Tables (dynamically created from CSV)

**Current columns**: User data columns + `_row_id`, `_dataset_id`, `_ingested_at`, `_fulltext`

**Added columns** (per text column):
- `_ts_{column_name}` — TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', COALESCE({column}, ''))) STORED
- `_emb_{column_name}` — vector(1536) (P2, only for qualifying columns with avg length >= 50)

**Added indexes** (per column):
- `idx_{table}_{column}_btree` — B-tree on every user data column
- `idx_{table}_{column}_gin` — GIN on `_ts_{column}` (text columns only)
- `idx_{table}_{column}_hnsw` — HNSW on `_emb_{column}` (P2, qualifying text columns only)

### Relationships

```text
datasets (1) ──── (N) index_metadata
    │                      │
    │ (existing)           │ (new)
    │                      │
    ├── column_mappings    ├── dataset_id FK → datasets.id
    ├── column_metadata    ├── column_name (naming convention, NOT FK)
    ├── cross_references   └── ON DELETE CASCADE
    └── queries
```

**Note on `column_name` relationship**: `index_metadata.column_name` uses the same sanitized column name as `column_mappings.column_name` and the actual data table column, but there is no formal foreign key between them. This is intentional because `index_metadata` also tracks system-generated columns (e.g., `_ts_name`, `_emb_description`) which do not appear in `column_mappings`. The `column_name` field always references the **source** data column, not the generated column.

## State Transitions

### Index Creation Status

```text
pending ──→ created    (index successfully created in PostgreSQL)
pending ──→ failed     (index creation error; logged, ingestion fails per FR-013)
```

### Dataset Availability (modified)

```text
                    ┌──────────────────────────┐
                    │                          │
uploading ──→ ingesting ──→ indexing ──→ available
                    │                          │
                    └──→ failed (if any step fails, dataset not available)
```

Note: The `indexing` state is a logical phase within the ingestion pipeline. Whether this manifests as a separate `status` value in the `datasets` table or remains implicit depends on implementation. The key constraint is FR-013: dataset is not queryable until all indexes are complete.

## Data Volume Estimates

| Dataset Size | Columns | B-tree Indexes | GIN Indexes | HNSW Indexes | Embedding API Calls |
|---|---|---|---|---|---|
| 1K rows, 5 cols (2 text) | 5 | 5 | 2 | 0-2 | 0-2K |
| 10K rows, 10 cols (4 text) | 10 | 10 | 4 | 0-4 | 0-40K |
| 100K rows, 15 cols (6 text) | 15 | 15 | 6 | 0-6 | 0-600K |

Embedding API calls scale linearly with row count per qualifying text column. For 100K rows with 3 qualifying columns, that is 300K API calls via ThreadPoolExecutor (10-20 workers).
