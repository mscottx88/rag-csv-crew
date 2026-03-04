# Research: Index-Aware SQL Generation

**Feature**: 003-index-aware-sql
**Date**: 2026-03-02
**Purpose**: Resolve technical unknowns and document design decisions for implementation

## R1: B-Tree Index Creation on Dynamic Columns

**Decision**: Create B-tree indexes on all user data columns during ingestion, using `CREATE INDEX IF NOT EXISTS` with the naming convention `idx_{table}_{column}_btree`.

**Rationale**: B-tree indexes are PostgreSQL's default index type and support equality, range, and sort operations. They are the most versatile general-purpose index and add minimal storage overhead. Creating them after bulk COPY loading avoids the per-row index maintenance penalty during ingestion.

**Alternatives Considered**:
- Skip B-tree for high-cardinality identifier columns: Rejected — B-tree is still beneficial for exact lookups on identifiers, and the heuristic for "is this an identifier" adds complexity without clear benefit.
- Create indexes during table creation (before data load): Rejected — indexes would need to be maintained during bulk COPY, significantly slowing ingestion. Post-load `CREATE INDEX` builds the entire index at once, which is far more efficient.
- Use `CREATE INDEX CONCURRENTLY`: Considered but unnecessary — the dataset is not yet available for querying during ingestion (per clarification Q2), so no concurrent reads need to be supported.

**Implementation Pattern**:
```python
# For each column in the data table:
index_sql: sql.Composed = sql.SQL(
    "CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table} ({column})"
).format(
    index_name=sql.Identifier(f"idx_{table_name}_{col_name}_btree"),
    schema=sql.Identifier(schema_name),
    table=sql.Identifier(table_name),
    column=sql.Identifier(col_name),
)
```

## R2: Tsvector Generated Columns and GIN Indexes on Text Columns

**Decision**: For each TEXT-type column, add a `GENERATED ALWAYS AS` tsvector column named `_ts_{column_name}` and create a GIN index on it. Use `'english'` language configuration, consistent with the existing `_fulltext` column pattern.

**Rationale**: PostgreSQL `GENERATED ALWAYS AS ... STORED` columns automatically maintain the tsvector representation as data changes. This is the same pattern already used for the `_fulltext` column on the data table (which concatenates all text columns). Per-column tsvector columns enable the SQL agent to target specific columns for full-text search with relevance ranking.

**Alternatives Considered**:
- Functional GIN index (no stored column): Rejected — `ts_rank()` requires a tsvector value at query time, so without a stored column the tsvector would need to be computed on every row during query execution, negating the performance benefit.
- Single combined tsvector for all text columns: Already exists as `_fulltext` on data tables. Per-column tsvectors complement this by enabling column-specific search and ranking.
- Use `'simple'` language config instead of `'english'`: Rejected — `'english'` provides stemming (e.g., "running" matches "run") which is more useful for natural language queries. Consistent with existing codebase pattern.

**Implementation Pattern**:
```python
# ALTER TABLE to add generated tsvector column:
alter_sql: sql.Composed = sql.SQL(
    "ALTER TABLE {schema}.{table} ADD COLUMN {ts_col} TSVECTOR "
    "GENERATED ALWAYS AS (to_tsvector('english', COALESCE({col}, ''))) STORED"
).format(
    schema=sql.Identifier(schema_name),
    table=sql.Identifier(table_name),
    ts_col=sql.Identifier(f"_ts_{col_name}"),
    col=sql.Identifier(col_name),
)

# GIN index on the tsvector column:
gin_sql: sql.Composed = sql.SQL(
    "CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table} USING GIN ({ts_col})"
).format(
    index_name=sql.Identifier(f"idx_{table_name}_{col_name}_gin"),
    schema=sql.Identifier(schema_name),
    table=sql.Identifier(table_name),
    ts_col=sql.Identifier(f"_ts_{col_name}"),
)
```

**Naming Conventions**:
- Tsvector column: `_ts_{original_column_name}` (underscore prefix indicates system-generated)
- GIN index: `idx_{table_name}_{column_name}_gin`

## R3: Index Metadata Registry Table Design

**Decision**: Create a new `index_metadata` table in the per-user schema that records every index created on data tables. This table is populated during ingestion and queried during SQL generation task construction.

**Rationale**: PostgreSQL's system catalog (`pg_indexes`) contains index information, but querying it requires catalog-level access and complex joins. A dedicated metadata table in the user schema provides a clean, fast lookup that can include capability annotations (what the index enables) that the system catalog lacks.

**Alternatives Considered**:
- Query `pg_indexes` / `pg_class` directly at SQL generation time: Rejected — adds latency to every query, requires parsing PostgreSQL system catalog schema, and cannot store capability annotations (e.g., "this index enables full_text_search").
- Extend existing `column_mappings` table: Rejected — `column_mappings` is per-column with a single embedding. A column can have multiple indexes (B-tree + GIN + HNSW), so a separate table with one row per index is cleaner.
- Store index metadata as JSONB in `column_metadata`: Rejected — JSONB is less queryable for structured metadata and doesn't enforce schema.

**Table Schema**: See `data-model.md` for full DDL.

## R4: SQL Generation Task Context Enhancement

**Decision**: Add an "INDEX CAPABILITIES" section to the task description string built in `create_sql_generation_task()`. This section lists, per column, what search strategies are available and provides example query patterns.

**Rationale**: The SQL generation agent is an LLM (Claude Opus). It needs explicit instructions about what database capabilities exist. Simply listing index names is insufficient — the agent needs to know what query patterns to use (e.g., `to_tsquery()` syntax, `<=>` operator syntax) and when to prefer them over simpler patterns like ILIKE.

**Alternatives Considered**:
- Add a separate CrewAI tool that the agent can call to discover indexes: Rejected — adds a tool-use round-trip. Since index metadata is static for a given dataset, it's more efficient to include it directly in the task description.
- Add index context to the Schema Inspector agent instead: Rejected — the Schema Inspector already provides column names and types. Index capabilities are a concern of SQL generation, not schema inspection.
- Minimal context (just "FTS available on column X"): Rejected — the LLM needs example syntax to generate correct queries. Saying "FTS available" without showing `to_tsquery()` syntax would lead to incorrect SQL.

**Context Format**:
```text
INDEX CAPABILITIES (use these for optimal query performance):
================================================================================
Table: {table_name}

Column: {column_name} (TEXT)
  - B-tree index: Available (supports =, <, >, BETWEEN, ORDER BY, LIKE 'prefix%')
  - Full-text search: Available via column '_ts_{column_name}'
    Pattern: WHERE _ts_{column_name} @@ plainto_tsquery('english', %s)
    Ranking: ORDER BY ts_rank(_ts_{column_name}, plainto_tsquery('english', %s)) DESC
    PREFER THIS over ILIKE for text searches.
  - Vector similarity: Available via column '_emb_{column_name}' (1536 dimensions)
    Pattern: ORDER BY _emb_{column_name} <=> %s::vector LIMIT 10
    Use for semantic/meaning-based searches, not exact keyword matches.

Column: {column_name} (BIGINT)
  - B-tree index: Available (supports =, <, >, BETWEEN, ORDER BY)
================================================================================
```

## R5: Data Value Embedding Generation Strategy

**Decision**: Use `ThreadPoolExecutor` with the existing `VectorSearchService.generate_embedding()` method to generate embeddings for all rows in qualifying text columns (average character length >= 50). Store embeddings in a new companion vector column `_emb_{column_name}` with an HNSW index.

**Rationale**: The existing `VectorSearchService` already wraps OpenAI's `text-embedding-3-small` model. Batch processing with ThreadPoolExecutor enables parallel API calls (thread-based, per constitution). All rows are embedded (per clarification Q3) since datasets are uploaded once and queried many times.

**Alternatives Considered**:
- Use OpenAI batch API: Considered but the existing `generate_embedding()` method handles single texts. ThreadPoolExecutor with 10-20 workers provides sufficient parallelism for the API rate limits.
- Embed only a sample of rows: Rejected per clarification Q3 — all rows must be embedded.
- Use a different embedding model for data values vs. column names: Rejected — using the same model (text-embedding-3-small, 1536d) ensures compatibility and simplifies the architecture.

**Qualifying Column Heuristic**:
- Column must be TEXT type (inferred_type)
- Average character length across sampled rows >= 50 characters (configurable threshold)
- This filters out short categorical values (status codes, abbreviations) while including descriptive content (descriptions, comments, notes)

**Implementation Pattern**:
```python
# Add companion vector column:
alter_sql: sql.Composed = sql.SQL(
    "ALTER TABLE {schema}.{table} ADD COLUMN {emb_col} vector(1536)"
).format(
    schema=sql.Identifier(schema_name),
    table=sql.Identifier(table_name),
    emb_col=sql.Identifier(f"_emb_{col_name}"),
)

# Generate embeddings in parallel:
with ThreadPoolExecutor(max_workers=10) as executor:
    embeddings: list[list[float]] = list(executor.map(
        vector_service.generate_embedding,
        text_values,
    ))

# Batch UPDATE with embeddings (chunked for memory):
update_sql: sql.Composed = sql.SQL(
    "UPDATE {schema}.{table} SET {emb_col} = %s WHERE _row_id = %s"
).format(...)

# HNSW index after all embeddings stored:
hnsw_sql: sql.Composed = sql.SQL(
    "CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table} "
    "USING hnsw ({emb_col} vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
).format(
    index_name=sql.Identifier(f"idx_{table_name}_{col_name}_hnsw"),
    schema=sql.Identifier(schema_name),
    table=sql.Identifier(table_name),
    emb_col=sql.Identifier(f"_emb_{col_name}"),
)
```

**Naming Conventions**:
- Embedding column: `_emb_{original_column_name}` (underscore prefix indicates system-generated)
- HNSW index: `idx_{table_name}_{column_name}_hnsw`

## R6: Ingestion Pipeline Integration Order

**Decision**: Index creation and metadata population are added to the existing ingestion pipeline after bulk data loading and before the dataset is marked as available. The order is:

1. File validation (existing)
2. Format detection (existing)
3. Schema detection (existing)
4. Table creation (existing — no change)
5. Metadata storage (existing — dataset marked as `ingesting` status)
6. **Bulk data load via COPY** (existing)
7. **B-tree index creation on all columns** (NEW)
8. **Tsvector column + GIN index creation on text columns** (NEW)
9. **Index metadata population** (NEW)
10. Column mappings storage (existing)
11. Column metadata computation (existing)
12. Embedding generation for column names (existing)
13. **Average text length computation for qualifying columns** (NEW)
14. **Data value embedding generation + HNSW index** (NEW — P2)
15. **Index metadata update for embedding indexes** (NEW — P2)
16. Cross-reference detection (existing)
17. **Dataset marked as available** (MODIFIED — only after all indexes complete, per FR-013)

**Rationale**: Indexes must be created after bulk data load for performance (FR-007). Index metadata must be populated before the dataset is available so the SQL generation task always has complete context (FR-004, FR-013). Embedding generation (P2) is the most time-consuming step and happens last.

## R7: Dataset Deletion Cleanup

**Decision**: The existing `DROP TABLE ... CASCADE` in the delete endpoint already removes all indexes on the data table. The only additional cleanup needed is deleting rows from the `index_metadata` table, which should use `ON DELETE CASCADE` from `datasets.id`.

**Rationale**: PostgreSQL automatically drops all indexes when a table is dropped with CASCADE. The `index_metadata` table rows reference `datasets.id`, so an FK with `ON DELETE CASCADE` handles cleanup automatically with no additional code.

## R8: Naming Convention Summary

| Artifact | Pattern | Example |
|---|---|---|
| B-tree index | `idx_{table}_{column}_btree` | `idx_products_data_name_btree` |
| Tsvector column | `_ts_{column}` | `_ts_name` |
| GIN index | `idx_{table}_{column}_gin` | `idx_products_data_name_gin` |
| Embedding column | `_emb_{column}` | `_emb_description` |
| HNSW index | `idx_{table}_{column}_hnsw` | `idx_products_data_description_hnsw` |
| Metadata table | `index_metadata` | `{username}_schema.index_metadata` |

**Identifier Length Handling**: When the full index name exceeds PostgreSQL's 63-character limit, the system truncates the table+column portion and appends an 8-character MD5 hash: `idx_{truncated}_{hash8}_{type}`. The `index_name` stored in metadata always reflects the actual (post-truncation) PostgreSQL identifier.

## R9: Language Configuration Validation (CHK042)

**Decision**: Use `'english'` text search configuration for all tsvector generated columns, consistent with the existing `_fulltext` column pattern.

**Validation**: The current deployment serves English-language users. Non-English text will still be indexed — exact terms will match — but stemming (e.g., "running" → "run") will be inaccurate for non-English words. This is an acceptable trade-off. Multi-language support (configurable language per column or per dataset) is explicitly out of scope.

## R10: VectorSearchService Thread Safety (CHK043)

**Decision**: Validate thread safety of `VectorSearchService.generate_embedding()` during P2 implementation.

**Analysis**: The method calls the OpenAI API via HTTP, which is inherently stateless. Thread safety depends on the implementation:
- If using `requests.get/post` per call: **thread-safe** (each call creates its own connection)
- If sharing a `requests.Session` at class level: **potentially unsafe** (sessions are not thread-safe per requests docs)
- If using the OpenAI SDK client: **check SDK docs** (most modern clients are thread-safe)

**Action**: During P2 implementation, inspect the existing `VectorSearchService` code. If mutable shared state exists, refactor to use per-call HTTP sessions or thread-local storage. Add a thread-safety integration test that calls `generate_embedding()` from multiple threads concurrently.
