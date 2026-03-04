# Quickstart: Index-Aware SQL Generation

**Feature**: 003-index-aware-sql
**Date**: 2026-03-02

## What This Feature Does

When a CSV file is uploaded, the system now automatically:

1. Creates **B-tree indexes** on every data column (enables fast filtering, sorting, range queries)
2. Creates **full-text search indexes** on every text column (enables `tsvector`/`tsquery` with relevance ranking)
3. Creates **vector embedding columns + HNSW indexes** on descriptive text columns (enables semantic similarity search)
4. Records all index metadata so the SQL generation agent knows what capabilities are available
5. Injects index capability context into the SQL generation task so the agent produces optimized queries

## User-Visible Changes

### Before (current behavior)

User asks: "Find employees named Johnson"

Generated SQL:
```sql
SELECT * FROM employees_data WHERE name ILIKE '%Johnson%' LIMIT 100
```
No relevance ranking. Full table scan on text. Slow for large datasets.

### After (with this feature)

User asks: "Find employees named Johnson"

Generated SQL:
```sql
SELECT *, ts_rank(_ts_name, plainto_tsquery('english', 'Johnson')) AS relevance
FROM employees_data
WHERE _ts_name @@ plainto_tsquery('english', 'Johnson')
ORDER BY relevance DESC
LIMIT 100
```
Full-text search with stemming and relevance ranking. Uses GIN index. Fast.

### Semantic Search (P2)

User asks: "Find products similar to outdoor furniture"

Generated SQL:
```sql
SELECT *, 1 - (_emb_description <=> '{embedding_vector}'::vector) AS similarity
FROM products_data
ORDER BY _emb_description <=> '{embedding_vector}'::vector
LIMIT 10
```
Vector cosine similarity search. Finds semantically related items even without keyword match.

## Developer Workflow

### Running Tests

```bash
# Unit tests for index manager service
pytest tests/unit/test_index_manager.py -v

# Integration tests (requires PostgreSQL + pgvector running)
pytest tests/integration/test_index_creation.py -v

# All tests
pytest tests/ -v
```

### Quality Checks

```bash
ruff check backend/src backend/tests
ruff format backend/src backend/tests
mypy --strict backend/src backend/tests
pylint backend/src backend/tests
```

### Key Files

| File | Purpose |
|---|---|
| `backend/src/services/index_manager.py` | NEW — Index creation, metadata, and context building |
| `backend/src/models/index_metadata.py` | NEW — Pydantic models for index metadata |
| `backend/src/db/schemas.py` | MODIFIED — Added index_metadata table DDL |
| `backend/src/services/ingestion.py` | MODIFIED — Calls IndexManagerService after data load |
| `backend/src/crew/tasks.py` | MODIFIED — Accepts and injects index_context parameter |
| `backend/src/api/datasets.py` | MODIFIED — Integrates index creation into upload flow |

### Verifying Indexes Were Created

After uploading a CSV, you can verify indexes in PostgreSQL:

```sql
-- Check index metadata registry
SELECT column_name, index_type, capability, status, generated_column_name
FROM {username}_schema.index_metadata
WHERE dataset_id = '{dataset_id}'
ORDER BY column_name, index_type;

-- Check actual PostgreSQL indexes on the data table
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = '{username}_schema'
  AND tablename = '{table_name}'
ORDER BY indexname;
```

### Configuration

| Setting | Default | Description |
|---|---|---|
| Embedding threshold | 50 chars avg | Minimum average text length for a column to qualify for data value embeddings |
| Embedding workers | 10 | ThreadPoolExecutor max_workers for parallel embedding API calls |
| HNSW m | 16 | Number of neighbors in HNSW graph (higher = more accurate, more memory) |
| HNSW ef_construction | 64 | Build-time search width (higher = better index quality, slower build) |
