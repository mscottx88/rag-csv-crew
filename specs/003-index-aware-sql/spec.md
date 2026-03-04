# Feature Specification: Index-Aware SQL Generation

**Feature Branch**: `003-index-aware-sql`
**Created**: 2026-03-02
**Status**: Draft
**Input**: User description: "Something is terribly wrong with the create_sql_generation_task. I don't see any reference to the fact that the underlying database supports full text search and vector search. Is there something missing from the backend that could assist the agent to understanding what is possible for columns? Can we track metadata about indexes that are built? Can we always ensure that every column has a btree index (at least) and any auto-generated full text search indexes are used and that the embeddings are being used."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - SQL Agent Uses Full-Text Search for Text Queries (Priority: P1)

When a user asks a natural language question that involves searching text content (e.g., "find all employees named Smith"), the SQL generation agent should produce a query that leverages PostgreSQL full-text search capabilities (tsvector/tsquery with ts_rank) instead of falling back to inefficient ILIKE wildcard patterns. The agent must know which columns have full-text search indexes and use them appropriately.

**Why this priority**: This is the core problem. The SQL agent currently generates ILIKE queries for text searches because it has no awareness that full-text search indexes exist (or could exist) on data columns. Full-text search provides dramatically better performance and relevance ranking. This is the highest-impact improvement.

**Independent Test**: Can be fully tested by uploading a CSV with text columns, asking a text search question, and verifying the generated SQL uses `to_tsvector`/`to_tsquery` with `ts_rank` instead of `ILIKE '%term%'`. Delivers immediate query quality improvement.

**Acceptance Scenarios**:

1. **Given** a dataset with text columns that have full-text search indexes, **When** a user asks "find employees named Johnson", **Then** the generated SQL uses `to_tsquery` and `ts_rank` for the search instead of `ILIKE`.
2. **Given** a dataset with text columns that have full-text search indexes, **When** a user asks a multi-word text search like "senior software engineer", **Then** the generated SQL uses `plainto_tsquery` or `phraseto_tsquery` with proper Boolean logic and relevance ranking.
3. **Given** the SQL generation task context, **When** the agent receives schema information, **Then** the context includes which columns have full-text search indexes and example query patterns for using them.

---

### User Story 2 - Automatic Index Creation During CSV Ingestion (Priority: P1)

When a CSV file is uploaded and a data table is created, the system should automatically create appropriate indexes on every column: B-tree indexes on all columns (for efficient filtering and sorting), and full-text search indexes (tsvector column + GIN index) on text columns. This ensures every data table is query-optimized from the moment it is available.

**Why this priority**: Without indexes on data columns, all queries against uploaded CSV data perform full table scans. This is a prerequisite for the SQL agent to generate index-aware queries — the indexes must actually exist before the agent can reference them.

**Independent Test**: Can be fully tested by uploading a CSV file and then querying the database system catalog to verify that B-tree indexes exist on all columns and GIN indexes exist on text columns' tsvector columns.

**Acceptance Scenarios**:

1. **Given** a CSV file with mixed column types (text, numeric, date, boolean), **When** the file is ingested, **Then** every column receives a B-tree index.
2. **Given** a CSV file with text columns, **When** the file is ingested, **Then** each text column receives a generated tsvector column and a GIN index on that tsvector column.
3. **Given** a large CSV file (100,000+ rows), **When** the file is ingested, **Then** indexes are created after bulk data loading (not before) to optimize ingestion speed.
4. **Given** a CSV with columns containing mostly NULL values, **When** the file is ingested, **Then** the system still creates standard indexes on those columns (B-tree handles NULL filtering efficiently without partial indexes).

---

### User Story 3 - Index Metadata Tracking and Discovery (Priority: P1)

The system should maintain a metadata registry that tracks which indexes exist on every data column, including the index type (B-tree, GIN, HNSW), what capability it enables (filtering, sorting, full-text search, vector similarity), and the column it applies to. This metadata is the bridge between what the database can do and what the SQL generation agent knows about.

**Why this priority**: This is the critical link between index creation (Story 2) and index-aware SQL generation (Story 1). Without a metadata registry, the SQL agent has no way to discover what search capabilities are available on each column.

**Independent Test**: Can be fully tested by uploading a CSV, then querying the index metadata registry to verify it accurately reflects the indexes that were created. The metadata should match what the database system catalog reports.

**Acceptance Scenarios**:

1. **Given** a newly ingested dataset, **When** indexes are created, **Then** the index metadata registry is populated with an entry for each index including: dataset, column name, index type, and search capability.
2. **Given** an existing dataset in the index metadata registry, **When** the SQL generation task is constructed, **Then** the task context includes a summary of all available indexes and their capabilities for the target dataset(s).
3. **Given** multiple datasets with different column types, **When** a user queries across datasets, **Then** the index metadata correctly reflects per-column capabilities for each dataset independently.

---

### User Story 4 - SQL Agent Uses Vector Similarity for Semantic Queries (Priority: P2)

When a user asks a question that requires semantic understanding (e.g., "find products similar to outdoor furniture"), the SQL generation agent should know that vector embeddings exist on certain text columns and generate queries that use cosine similarity search, rather than relying solely on keyword matching.

**Why this priority**: Vector similarity search enables semantic understanding beyond keyword matching. While full-text search handles exact and stemmed term matching (P1), vector search handles synonyms, paraphrasing, and conceptual similarity. This builds on the index metadata infrastructure from Stories 2-3.

**Independent Test**: Can be fully tested by uploading a CSV with descriptive text columns, generating embeddings for those columns, asking a semantic question, and verifying the generated SQL includes vector distance operations with appropriate similarity thresholds.

**Acceptance Scenarios**:

1. **Given** a dataset with text columns that have vector embeddings, **When** a user asks a semantically complex question, **Then** the generated SQL uses the cosine distance operator for similarity search.
2. **Given** the SQL generation task context, **When** embedding indexes are available on target columns, **Then** the context includes the embedding dimension, distance operator syntax, and guidance on combining vector search with traditional filters.
3. **Given** a user query that benefits from both keyword and semantic matching, **When** the SQL agent generates a query, **Then** it may combine full-text search and vector similarity in a single query using appropriate scoring and ranking.

---

### User Story 5 - Embedding Generation for Data Column Values (Priority: P2)

When text columns in uploaded CSV data contain meaningful descriptive content (product descriptions, comments, notes), the system should generate vector embeddings for those values and store them alongside the data. This enables vector similarity search directly on data rows, not just on column names.

**Why this priority**: Currently, embeddings are only generated for column names (in the column mappings system), not for the actual data values in text columns. Generating embeddings for data values unlocks row-level semantic search, which is a significant capability enhancement beyond column-level search.

**Independent Test**: Can be fully tested by uploading a CSV with a descriptive text column (e.g., product descriptions), verifying that a vector column and HNSW index are created for that text column, and confirming that similarity searches return semantically relevant rows.

**Acceptance Scenarios**:

1. **Given** a CSV with text columns containing descriptive content, **When** the file is ingested, **Then** the system generates vector embeddings for text values in qualifying columns and stores them in companion vector columns.
2. **Given** a text column with embedding-worthy content, **When** embeddings are generated, **Then** an HNSW index is created on the embedding column for efficient similarity search.
3. **Given** a dataset where some text columns are short labels (e.g., status codes) and others are long descriptions, **When** the system decides which columns get embeddings, **Then** only columns with sufficient textual richness (average length above a threshold) receive embeddings, avoiding wasted computation on short categorical values.

---

### Edge Cases

- What happens when a CSV column has extremely high cardinality (millions of unique values)? The system creates B-tree indexes on all columns regardless. For FTS, the identifier heuristic (cardinality ratio > 0.95 AND avg text length < 50) skips tsvector/GIN creation on identifier-like columns per FR-002.
- How does the system handle columns with mixed content (numbers stored as text)? The system should use the inferred type to determine which indexes are appropriate, not just the storage type.
- What happens when index creation fails mid-ingestion (e.g., disk space)? The system should log the failure, record partial index status in metadata, and fail the ingestion — the dataset should not become available with missing indexes.
- What if the same CSV is re-uploaded? Since backwards compatibility is not required, the system treats each upload as a fresh ingestion with full index creation.
- What happens when a dataset is deleted? All associated indexes and index metadata entries should be cleaned up.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create a B-tree index on every column of every dynamically created data table during CSV ingestion.
- **FR-002**: System MUST create a tsvector generated column and GIN index for every text-type column in dynamically created data tables, **except** columns identified as identifier-like by the heuristic: cardinality ratio (unique values / total rows) > 0.95 AND average text length < 50 characters. Identifier-like columns receive only a B-tree index.
- **FR-003**: System MUST maintain an index metadata registry that records, for each data column: the index type(s) present, the search capabilities enabled, and any associated generated columns (e.g., tsvector column names).
- **FR-004**: System MUST populate the index metadata registry automatically during CSV ingestion, immediately after index creation.
- **FR-005**: System MUST include index capability metadata in the context provided to the SQL generation task, so the agent knows which columns support full-text search, vector similarity, and standard B-tree operations.
- **FR-006**: The SQL generation task description MUST include query pattern examples for each available search capability (e.g., tsvector query syntax for full-text columns, cosine distance syntax for vector columns).
- **FR-007**: System MUST create indexes after bulk data loading is complete, not before, to optimize ingestion performance.
- **FR-008**: System MUST generate vector embeddings for every row in text data columns that contain descriptive content (average character length above a configurable threshold) and create HNSW indexes on the resulting embedding columns. There is no row count limit — all rows in qualifying columns are embedded.
- **FR-009**: System MUST clean up all associated indexes and index metadata when a dataset is deleted.
- **FR-010**: The SQL generation agent MUST prefer full-text search operators over ILIKE patterns when a full-text search index is available on the target column.
- **FR-011**: The SQL generation agent MUST use vector cosine distance operators when vector indexes are available and the query has semantic intent.
- **FR-012**: System MUST record index creation status (success/failure) in the metadata registry to enable failure diagnosis and informative error reporting when index creation fails.
- **FR-013**: System MUST NOT mark a dataset as available for querying until all index creation and metadata population steps have completed successfully.

### Key Entities

- **Index Metadata Entry**: Represents a single index on a data column. Key attributes: dataset ID, column name, index name, index type (btree, gin, hnsw), capability (filtering, full_text_search, vector_similarity), associated generated column name (e.g., tsvector column), creation status (created, failed, pending), creation timestamp.
- **Data Column Index Profile**: An aggregate view of all indexes on a single column. Used by the SQL generation task to understand the full set of query strategies available for each column.
- **Embedding Column**: A companion vector column added to a data table for text columns with sufficient content richness. Linked to the source text column via index metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All text search queries against indexed columns produce results using full-text search operators (not ILIKE) in the generated SQL, as verified by inspecting the SQL output for each query.
- **SC-002**: Every column in every uploaded dataset has at least a B-tree index, verifiable by querying the index metadata registry after ingestion.
- **SC-003**: The SQL generation agent receives complete index capability context for 100% of target columns when generating queries, as verified by examining the task description passed to the agent framework.
- **SC-004**: Text search queries using full-text search indexes return results ranked by relevance (via `ts_rank`), providing relevance-ordered output that ILIKE-based queries cannot produce, as verified by confirming generated SQL includes `ORDER BY ts_rank()` for text search queries.
- **SC-005**: Dataset ingestion time increases by no more than 50% due to additional index creation, compared to ingestion without indexes.
- **SC-006**: When vector embeddings are available on data columns, semantic queries leverage vector similarity search, as verified by the presence of cosine distance operators in generated SQL.

## Clarifications

### Session 2026-03-02

- Q: Should existing datasets (uploaded before this feature) be backfilled with indexes? → A: No backfill. Only new uploads get indexes. Existing datasets can be deleted and re-imported. Backwards compatibility with pre-existing data is not required.
- Q: Is the dataset available for queries while indexes are still building? → A: No. The dataset only becomes queryable after all indexes and metadata are fully built. Index creation is part of the ingestion pipeline and must complete before the dataset is marked as available.
- Q: For data value embeddings (P2), should all rows be embedded or should there be a row count cap? → A: Embed all rows in qualifying columns, regardless of table size. No row count limit. Datasets are uploaded once and queried many times, so the upfront cost is acceptable.

### Session 2026-03-02 — Checklist Resolution (CHK001–CHK043)

**Data Model & Schema:**
- Q (CHK001): Does the per-column `_ts_{col}` approach replace the existing `_fulltext` column? → A: No. Both are kept. `_fulltext` provides cross-column search; per-column tsvectors enable targeted search with per-column ranking. See FR-014.
- Q (CHK002): Are `index_type` and `capability` values enforced at the database level? → A: Enforcement is at the application layer via Pydantic StrEnum (IndexType, IndexCapability). No CHECK constraints in DDL — the application layer is the sole writer and validates before insert. This avoids DDL coupling with application enums.
- Q (CHK003): Is there a formal FK between `index_metadata.column_name` and `column_mappings.column_name`? → A: No FK. Naming consistency only. The column_name in index_metadata matches the sanitized column name used in the data table and column_mappings. No FK because index_metadata tracks system-generated columns (e.g., `_ts_name`) that don't appear in column_mappings.
- Q (CHK004): What happens to index_metadata if a column is renamed or schema changes? → A: Not applicable. Datasets are immutable once ingested. There is no column rename or schema modification operation. Users delete and re-import to get a new schema.
- Q (CHK005): How is PostgreSQL's 63-character identifier limit handled? → A: Index names that would exceed 63 characters are truncated with a hash suffix: `idx_{truncated}_{hash8}_{type}`. See extended edge cases.

**Ingestion Pipeline:**
- Q (CHK006): Are progress reporting requirements specified for new index creation steps? → A: Yes, see FR-015. Index creation emits progress events consistent with existing pipeline reporting.
- Q (CHK007): What HTTP status code when index creation fails? → A: HTTP 500 (Internal Server Error). See FR-016.
- Q (CHK008): What happens to the data table when index creation fails? → A: The data table is dropped and dataset metadata deleted. See extended edge cases.
- Q (CHK009): What if ALTER TABLE ADD COLUMN fails for tsvector? → A: Treated as index creation failure — see extended edge cases.
- Q (CHK010): Are transaction boundaries explicitly documented? → A: Yes, documented in the ingestion pipeline contract. DDL runs in its own transaction due to implicit commits. Dataset availability update is the final transaction.

**AI Agent Context:**
- Q (CHK011): How does the agent behave when `index_context` is None? → A: Falls back to current behavior (no index-aware patterns). See FR-017.
- Q (CHK012): Is the index context string size bounded? → A: Yes, capped at 4,000 characters with summarization for wide datasets. See FR-018.
- Q (CHK013): How does the agent handle cross-dataset queries with mixed index availability? → A: Index-aware patterns used only for datasets with metadata; standard patterns for others. See FR-019.
- Q (CHK014): When should the agent use `to_tsquery` vs `plainto_tsquery` vs `phraseto_tsquery`? → A: The agent context provides `plainto_tsquery` as the default pattern (handles multi-word input safely). The agent MAY use `phraseto_tsquery` for exact phrase matching or `to_tsquery` for advanced Boolean queries at its discretion based on the user's natural language phrasing. The context rules say "PREFER full-text search over ILIKE" — the choice of tsquery function is left to the agent's judgment. This is intentional: the LLM can infer phrase vs keyword intent from natural language.
- Q (CHK015): Who generates the query embedding at runtime for vector similarity queries? → A: The SQL generation agent emits `%s::vector` as a placeholder parameter. The query execution layer (existing in `backend/src/services/`) calls `VectorSearchService.generate_embedding(query_text)` to produce the embedding vector, then passes it as a query parameter when executing the generated SQL. This follows the existing parameterized query pattern.

**Embedding Generation (P2):**
- Q (CHK016): How are NULL/empty text values handled during embedding? → A: NULL → NULL embedding (skipped). Empty string → NULL embedding (skipped). See FR-020.
- Q (CHK017): What happens when embedding fails for individual rows? → A: Retry 3 times, then skip. Partial embeddings acceptable if >90% success. See FR-021.
- Q (CHK018): What is the batch size for embedding UPDATE operations? → A: 500 rows per database round-trip. See FR-022.
- Q (CHK019): Is sampling 1000 rows sufficient for `identify_qualifying_columns`? → A: Yes. For the target scale (up to 100K rows), 1000 rows provides a statistically adequate sample. The `sample_size` parameter is configurable for edge cases. For datasets with fewer than 1000 rows, all rows are used (no sampling).

**Thresholds & Heuristics:**
- Q (CHK020): Is "average 50 characters" an adequate heuristic? → A: It is a practical default. Short categorical values (status, codes, abbreviations) typically average <20 chars. Descriptive content (descriptions, comments) typically averages >80 chars. The 50-char threshold is configurable per deployment to handle edge cases like addresses (~45 chars) or encoded data (~60 chars). Misclassification at the boundary is acceptable because the worst case is unnecessary (but not harmful) embedding generation.
- Q (CHK021): Is the high-cardinality edge case quantified? → A: No specific threshold. The system creates B-tree indexes on all columns regardless of cardinality. The "high cardinality" edge case applies only to the recommendation to "skip FTS if column appears to be an identifier." The heuristic is: if a TEXT column has cardinality ratio (unique values / total rows) > 0.95 AND average text length < 50, skip FTS. This indicates identifier-like content (UUIDs, codes). Otherwise, FTS indexes are always created for TEXT columns.
- Q (CHK022): What does "text-type column" include? → A: Only columns whose inferred type resolves to PostgreSQL `TEXT` during schema detection. This excludes `VARCHAR(N)`, `CHAR(N)`, and other character types because the CSV schema detection in the existing codebase infers all string columns as `TEXT`. There is no ambiguity in practice.
- Q (CHK023): Is "semantic intent" in FR-011 defined with specific criteria? → A: No. It is intentionally left to the LLM agent's judgment. The agent receives both FTS and vector search patterns in the INDEX CAPABILITIES context. The agent determines which to use based on the user's natural language query. Keywords like "similar to," "like," "related to" suggest semantic intent; keywords like "named," "containing," "with the word" suggest keyword intent. This is the agent's core competency and does not need rigid rules.

**Requirement Consistency:**
- Q (CHK024): Does FR-012 ("graceful degradation") conflict with FR-013 ("not available with missing indexes")? → A: FR-012 is updated to clarify: "record index creation status" serves diagnostic purposes, not runtime degradation. If any P1 index fails, the dataset is not made available (FR-013). The `status='failed'` entries in index_metadata help diagnose what went wrong. "Graceful degradation" in FR-012 refers to informative error reporting, not to serving partial results. FR-012 is hereby amended to: "System MUST record index creation status (success/failure) in the metadata registry to enable failure diagnosis and informative error reporting."
- Q (CHK025): Are NULL-based partial indexes in scope (Story 2 Scenario 4 vs scope boundaries)? → A: Story 2 Scenario 4 is removed. Partial indexes (including NULL-based) are out of scope per the scope boundaries. The system creates standard indexes on all columns. For columns with mostly NULL values, the B-tree index naturally handles NULL filtering efficiently. The original scenario was aspirational and conflicts with the explicit scope boundary.
- Q (CHK026): Should `capability` be a list/set since B-tree supports both filtering and sorting? → A: Each index gets a single metadata entry with a single `capability` value. B-tree indexes record `capability='filtering'` because filtering is the primary use case. Sorting is an implicit capability of B-tree indexes that the SQL agent understands from the INDEX CAPABILITIES context pattern (which includes "ORDER BY" in B-tree descriptions). Adding a separate `sorting` capability would double the B-tree metadata entries without adding information the agent doesn't already have.
- Q (CHK027): Is the `conn` vs `pool` inconsistency intentional between `create_indexes_for_dataset` and `create_embedding_indexes`? → A: Yes, intentional. `create_indexes_for_dataset` takes `conn` because it runs as part of a sequential pipeline where the caller manages the connection. `create_embedding_indexes` takes `pool` because it uses ThreadPoolExecutor internally and needs to acquire multiple connections for parallel embedding writes. This is documented in the contract.

**Acceptance Criteria:**
- Q (CHK028): Is ILIKE ever acceptable when an FTS index exists? → A: Yes, in one case: when the user explicitly requests substring matching (e.g., "find names containing 'son'" where partial word matching is needed). FTS operates on word boundaries and stemming, so `ILIKE '%son%'` finds "Johnson" while `to_tsquery('son')` may not. The agent MAY use ILIKE for explicit substring patterns. SC-001 is clarified: "All text search queries" means "keyword and phrase searches," not substring searches.
- Q (CHK029): Is SC-004 measurable? → A: SC-004 is amended to: "Text search queries using full-text search indexes return results ranked by relevance (via ts_rank), providing relevance-ordered results that ILIKE-based queries cannot produce. Verifiable by confirming generated SQL includes ORDER BY ts_rank() for text search queries."
- Q (CHK030): Is the SC-005 baseline defined? → A: The baseline is ingestion time for the current pipeline (steps 1-12 in the ingestion contract) without the new index creation steps (steps 9, 13-15). Measured on the 100K-row reference dataset. The 50% increase applies to wall-clock time of the full ingestion request.
- Q (CHK031): Are acceptance scenarios defined for `build_index_context` output? → A: The exact format is specified in the SQL generation task context contract. Acceptance testing verifies: (1) the context string matches the documented format, (2) every column with `status='created'` indexes appears in the context, (3) columns with only B-tree indexes show only B-tree patterns, (4) columns with FTS show tsvector query patterns, (5) columns with embeddings show vector distance patterns.

**Scenario Coverage:**
- Q (CHK032): Zero text columns scenario? → A: See extended edge cases. Only B-tree indexes created; metadata populated with B-tree entries only.
- Q (CHK033): Single-row CSV? → A: See extended edge cases. All indexes still created; single row used for average length calculation.
- Q (CHK034): Concurrent uploads? → A: See extended edge cases. No interference due to unique table names and schema isolation.
- Q (CHK035): Embedding API unavailable during P2? → A: See extended edge cases. Ingestion fails if P2 steps are initiated but fail.
- Q (CHK036): Cross-dataset queries with mixed embedding availability? → A: See FR-019. Agent uses vector search only for datasets that have it, standard patterns for others.

**Non-Functional Requirements:**
- Q (CHK037): Disk space requirements? → A: Estimated for 100K-row dataset with 15 columns (6 text): B-tree indexes ~2-5MB each (75-90MB total), GIN indexes ~5-15MB each (30-90MB total), tsvector columns ~10-30MB each (60-180MB total), embedding columns ~600MB each (0-3.6GB for 0-6 qualifying columns). Total additional storage: 165MB-4GB depending on text column count and embedding qualification. This is acceptable for the target deployment (server with >100GB storage).
- Q (CHK038): Embedding API cost? → A: At $0.02/1M tokens (text-embedding-3-small), 100K rows averaging 200 chars (~50 tokens each) = 5M tokens per qualifying column = $0.10 per qualifying column. For a dataset with 3 qualifying columns, total cost is ~$0.30 per ingestion. Cost is acceptable per the "upload once, query many times" model. Cost monitoring is out of scope for this feature.
- Q (CHK039): Logging/observability requirements? → A: See FR-023. Index creation and embedding generation must log progress, throughput, and errors.
- Q (CHK040): Memory requirements for embedding generation? → A: Addressed by FR-022 (batch size of 500 rows). With 500 embeddings at 1536 floats (4 bytes each), peak memory for the embedding buffer is ~3MB per batch. The ThreadPoolExecutor processes batches sequentially, not all at once. Total memory overhead is bounded at ~50MB for the embedding pipeline regardless of dataset size.

**Dependencies & Assumptions:**
- Q (CHK041): Is the assumption about agent framework token limits validated? → A: Addressed by FR-018 (4,000 character cap on index context). The existing task description is approximately 2,000-3,000 tokens. Adding up to 4,000 characters (~1,000 tokens) of index context stays well within Claude Opus's context window. For datasets with 50+ columns, the context is summarized rather than listing each column individually.
- Q (CHK042): Is the 'english' text search configuration validated? → A: Yes. See updated assumption. English stemming is appropriate for the current deployment. Non-English text still matches on exact terms. Multi-language support is out of scope.
- Q (CHK043): Is `VectorSearchService.generate_embedding()` thread-safe? → A: Must be validated during implementation. The method calls an external HTTP API (OpenAI), which is inherently stateless. Thread safety requires that the method does not share mutable state between calls. If the existing implementation uses a shared `requests.Session` or mutable class-level state, it must be refactored to be thread-safe (e.g., create a new session per call or use thread-local storage). This is a P2 implementation task, not a specification concern.

### Edge Cases (Extended — Checklist Resolution)

- What happens when generated index names exceed PostgreSQL's 63-character identifier limit? The system MUST truncate the base name (table + column portion) and append a hash suffix to ensure uniqueness while staying within the 63-character limit. Pattern: `idx_{truncated}_{hash8}_{type}` where `{hash8}` is the first 8 characters of MD5(full_table_column). Example: `idx_very_long_tab_a1b2c3d4_btree`.
- What happens when ALTER TABLE ADD COLUMN fails for a tsvector generated column (e.g., column name conflicts with existing `_ts_` prefix)? The system treats this as an index creation failure — logs the error, records `status='failed'` in index metadata, and fails the ingestion per FR-013.
- What happens to the data table and loaded data when index creation fails mid-pipeline? The system MUST drop the data table (`DROP TABLE ... CASCADE`) and delete the dataset metadata. A partially-indexed dataset is never left in place. The upload endpoint returns HTTP 500 with a descriptive error message.
- What happens when a CSV has zero text columns (all numeric/date/boolean)? Only B-tree indexes are created on all columns. No tsvector columns or GIN indexes are generated. The index metadata registry is still populated with B-tree entries only. The INDEX CAPABILITIES context lists only B-tree capabilities.
- What happens when a CSV has only one row? The system still creates all indexes (B-tree, GIN for text columns). The average text length calculation for embedding qualification uses the single row value. If that value exceeds the threshold, embeddings are generated normally.
- What happens with concurrent uploads by the same user? Each upload operates on a distinct data table (unique table names per dataset). Index creation uses schema-qualified, table-specific names, so concurrent uploads do not interfere with each other. Per-user schema isolation provides the boundary.
- What happens when the embedding API is unavailable during P2 ingestion? If P2 embedding generation has been initiated (qualifying columns identified), API failure MUST fail the entire ingestion per FR-013. The dataset is not made available with only P1 indexes when P2 steps have been started. If no columns qualify for embeddings, P2 steps are skipped entirely and the dataset becomes available after P1 completes.

### Functional Requirements (Extended — Checklist Resolution)

- **FR-014**: System MUST retain the existing `_fulltext` tsvector column (which concatenates all text columns) alongside the new per-column `_ts_{col}` tsvector columns. Both serve different purposes: `_fulltext` enables broad cross-column text search; per-column tsvectors enable targeted column-specific search with relevance ranking. Neither replaces the other.
- **FR-015**: System MUST report progress for index creation steps in the ingestion pipeline. Progress events for "Creating B-tree indexes", "Creating full-text search indexes", and "Creating embedding indexes" (P2) MUST be emitted in the same format as existing pipeline progress reporting.
- **FR-016**: System MUST return HTTP 500 (Internal Server Error) when index creation fails during ingestion. The error response body MUST include the specific index that failed and the failure reason. The upload endpoint returns HTTP 201 only when all steps including index creation complete successfully.
- **FR-017**: The SQL generation agent MUST handle datasets with no index context gracefully. When `index_context` is None (e.g., querying a pre-existing dataset uploaded before this feature), the agent falls back to the current behavior (no index-aware query patterns). The absence of index context MUST NOT cause errors.
- **FR-018**: The index context string injected into the SQL generation task MUST NOT exceed 4,000 characters. For datasets with many columns (50+), the context MUST summarize column groups by type rather than listing each column individually. This ensures the context fits within token budgets alongside existing task description content.
- **FR-019**: For queries spanning multiple datasets where some have index metadata and others do not, the SQL generation agent MUST use index-aware patterns only for the datasets that have them, and fall back to standard patterns for datasets without index metadata. The INDEX CAPABILITIES context only includes datasets with registered indexes.
- **FR-020**: System MUST handle NULL and empty text values during embedding generation. NULL values produce NULL embeddings (the vector column is nullable). Empty strings are skipped (no API call made; embedding set to NULL). Rows with NULL embeddings are excluded from HNSW index via the index's default NULL handling.
- **FR-021**: If embedding generation fails for individual rows (e.g., API timeout on specific rows), the system MUST retry failed rows up to 3 times. If rows still fail after retries, the system logs the failure count and proceeds — partial embeddings are acceptable for P2 (unlike P1 indexes which must all succeed). The dataset is still made available, and the index metadata records the embedding index as `created` if >90% of rows were successfully embedded.
- **FR-022**: Embedding UPDATE operations MUST be performed in batches of 500 rows per database round-trip to balance memory usage and database transaction size. This prevents holding 100K+ embeddings in memory simultaneously.
- **FR-023**: System MUST log index creation progress including: index name, index type, column name, creation duration, and success/failure status for each index. For embedding generation, the system MUST log: qualifying column count, total rows to embed, embedding throughput (rows/second), and API error count.

## Assumptions

- The database system with vector search extension is already available and configured in the deployment environment (confirmed by existing codebase).
- The embedding model is available for generating data value embeddings.
- The configurable threshold for "descriptive content" columns that receive embeddings defaults to an average character length of 50 characters per value, which can be tuned per deployment.
- Index creation on large tables (100K+ rows) is acceptable as a post-ingestion step and does not need to be instantaneous.
- The existing agent framework supports extended task descriptions without token limit issues for the additional index context.
- The tsvector generated columns use the 'english' language configuration by default, consistent with the existing column mappings pattern. This is appropriate for the current deployment context. Non-English text will receive degraded stemming but still match on exact terms. Multi-language support is explicitly out of scope for this feature.
- Backwards compatibility with datasets uploaded before this feature is not required. Users will delete and re-import existing data. Only newly ingested datasets receive automatic indexes and metadata.

## Dependencies

- Existing CSV ingestion service — will be extended with index creation logic.
- Existing SQL generation task — will be extended with index capability context.
- Existing database schema management — will be extended with index metadata table.
- Existing vector search service — will be used for data value embedding generation.
- Database system catalog — used for index verification and reconciliation.

## Scope Boundaries

**In scope**:
- Automatic B-tree index creation on all data columns
- Automatic tsvector + GIN index creation on text columns
- Index metadata registry (new table and service)
- Enhanced SQL generation task context with index capabilities
- Vector embedding generation for descriptive text data columns
- Index cleanup on dataset deletion

**Out of scope**:
- Index tuning or optimization after creation (e.g., rebuilding, maintenance)
- User-facing UI for managing indexes
- Custom index configuration per column (all indexing is automatic)
- Partial indexes based on data distribution analysis
- Index usage statistics or query performance monitoring
- Changes to the hybrid search service (which searches column names, not data values)
