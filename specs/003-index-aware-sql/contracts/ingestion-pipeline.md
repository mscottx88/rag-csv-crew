# Contract: Ingestion Pipeline Extension

**Feature**: 003-index-aware-sql
**Date**: 2026-03-02
**Module**: `backend/src/services/ingestion.py`, `backend/src/api/datasets.py`

## Modified Flow: Dataset Upload

### Current Steps (for reference)

1. `CSVValidator.validate_csv_file()` → validation
2. `detect_csv_format()` → `{delimiter, encoding, quotechar, has_header}`
3. `detect_csv_schema()` → `[{name, type, nullable}]`
4. `check_filename_conflict()` → `{conflict, suggested_filename}`
5. `create_dataset_table()` → table_name
6. `store_dataset_metadata()` → dataset_id
7. `ingest_csv_data()` → row_count (COPY protocol)
8. UPDATE row_count
9. `store_column_mappings()` → column metadata
10. `ColumnMetadataService.compute_and_store_metadata()` → stats (optional)
11. `generate_column_embeddings()` → column name embeddings (optional)
12. `detect_and_store_cross_references()` → relationships (optional)

### Modified Steps (changes in bold)

1. `CSVValidator.validate_csv_file()` → validation
2. `detect_csv_format()` → format info
3. `detect_csv_schema()` → column definitions
4. `check_filename_conflict()` → conflict check
5. `create_dataset_table()` → table_name
6. `store_dataset_metadata()` → dataset_id
7. `ingest_csv_data()` → row_count (COPY protocol)
8. UPDATE row_count
9. **`IndexManagerService.create_indexes_for_dataset()`** → index metadata entries (NEW, REQUIRED)
10. `store_column_mappings()` → column metadata
11. `ColumnMetadataService.compute_and_store_metadata()` → stats (optional)
12. `generate_column_embeddings()` → column name embeddings (optional)
13. **`IndexManagerService.identify_qualifying_columns()`** → qualifying text columns (NEW, P2)
14. **`IndexManagerService.create_embedding_indexes()`** → embedding indexes (NEW, P2)
15. `detect_and_store_cross_references()` → relationships (optional)
16. **Dataset marked as available** (MODIFIED — only after step 9 minimum for P1, step 14 for P2)

### Error Handling Changes

**Current**: Steps 10-12 are optional — failure doesn't block upload.

**Modified**:
- Step 9 (index creation) is **REQUIRED** — failure prevents dataset from being available (FR-013)
- Steps 13-14 (embedding generation) follow the same pattern: if initiated, must complete before dataset is available
- If step 9 fails: record partial index metadata with `status='failed'`, drop the data table, delete dataset metadata, and return **HTTP 500** with error details (FR-016)
- The upload endpoint returns **HTTP 201** only when ALL steps complete successfully

### Progress Reporting

The ingestion pipeline emits progress events (FR-015) for the new steps:
- Step 9: `"Creating indexes for dataset"` (includes sub-progress for B-tree and GIN phases)
- Step 13: `"Identifying columns for embedding generation"`
- Step 14: `"Generating embeddings for data columns"` (includes throughput: rows/second)

### Transaction Boundaries

- Steps 5-8 run in a single transaction (existing behavior)
- Step 9 (index creation) runs in its own transaction — DDL statements (CREATE INDEX) in PostgreSQL cause implicit commits
- Steps 10-12 run independently (existing behavior)
- Steps 13-14 run in their own transaction(s)
- Dataset availability flag update is the final transaction

## Modified Flow: Dataset Deletion

### Current Behavior

1. Look up `table_name` from datasets table
2. `DROP TABLE IF EXISTS {schema}.{table} CASCADE` — removes table and all indexes
3. `DELETE FROM {schema}.datasets WHERE id = %s` — cascading deletes remove column_mappings, cross_references, column_metadata

### Modified Behavior

No changes needed. The `ON DELETE CASCADE` on `index_metadata.dataset_id` automatically removes index metadata rows when the dataset is deleted. The `DROP TABLE ... CASCADE` already removes all PostgreSQL indexes on the data table.

## Schema DDL Changes

### New table in `schemas.py`

The `index_metadata` table DDL (see data-model.md) must be added to the `ensure_user_schema_exists()` function in `backend/src/db/schemas.py`, so it is created alongside the existing tables when a new user schema is initialized.
