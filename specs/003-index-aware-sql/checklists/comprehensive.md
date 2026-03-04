# Comprehensive Pre-Implementation Checklist: Index-Aware SQL Generation

**Purpose**: Deep requirements quality audit across all domains (data model, pipeline, AI agent context, embeddings) before implementation begins
**Created**: 2026-03-02
**Feature**: [spec.md](../spec.md)
**Depth**: Deep | **Audience**: Author (self-review) | **Scope**: All domains
**Resolved**: 2026-03-02 — All 43 items resolved via spec/data-model/contract/research updates

## Requirement Completeness — Data Model & Schema

- [x] CHK001 - Is it specified what happens to the existing `_fulltext` tsvector column (which concatenates ALL text columns) when per-column `_ts_{col}` tsvectors are added? Are both kept, or does the per-column approach replace it? [Gap, Spec §FR-002] → **Resolved**: FR-014 added. Both kept; `_fulltext` for cross-column search, `_ts_{col}` for targeted per-column search. See Spec §FR-014 and Clarifications Session 2 (CHK001).
- [x] CHK002 - Are the allowed values for `index_type` and `capability` in the `index_metadata` table explicitly constrained (e.g., CHECK constraint or enum), or just documented as convention? [Clarity, Data Model §Field Definitions] → **Resolved**: Application-layer enforcement via Pydantic StrEnum. No database CHECK constraints — documented in data-model.md field definitions.
- [x] CHK003 - Is the relationship between `index_metadata.column_name` and `column_mappings.column_name` specified — should there be a formal FK or just naming consistency? [Gap, Data Model §Relationships] → **Resolved**: Naming consistency only (no FK). Documented in data-model.md relationships section with rationale.
- [x] CHK004 - Are requirements defined for what happens to `index_metadata` rows if a column is renamed or table schema changes? [Edge Case, Gap] → **Resolved**: Not applicable. Datasets are immutable once ingested. No rename/schema change operations exist. See Clarifications Session 2 (CHK004).
- [x] CHK005 - Is PostgreSQL's 63-character identifier limit addressed for generated names like `idx_{table}_{column}_btree` when both table and column names are long? [Edge Case, Research §R8] → **Resolved**: Truncation with hash suffix strategy documented in spec edge cases, data-model.md, and research.md R8.

## Requirement Completeness — Ingestion Pipeline

- [x] CHK006 - Are progress reporting requirements specified for the new index creation steps (steps 7-9 in the modified pipeline)? The existing pipeline reports progress — should index creation status be included? [Gap, Contract §Ingestion Pipeline] → **Resolved**: FR-015 added. Progress events required for index creation and embedding generation steps. Updated in ingestion pipeline contract.
- [x] CHK007 - Is it specified which HTTP status code the upload endpoint returns when index creation fails mid-ingestion? [Gap, Contract §Ingestion Pipeline Error Handling] → **Resolved**: FR-016 added. HTTP 500 on failure, HTTP 201 only on complete success. Updated in ingestion pipeline contract.
- [x] CHK008 - Are requirements defined for what happens to the partially-created data table and already-loaded data when index creation fails? Is the table dropped, or left in a failed state? [Gap, Spec §Edge Cases] → **Resolved**: Data table dropped, dataset metadata deleted. See spec extended edge cases and ingestion pipeline contract error handling.
- [x] CHK009 - Is the behavior specified when `ALTER TABLE ADD COLUMN` fails for the tsvector generated column (e.g., column name conflict with existing `_ts_` prefix)? [Edge Case, Gap] → **Resolved**: Treated as index creation failure. See spec extended edge cases.
- [x] CHK010 - Are transaction boundary requirements explicitly documented beyond the plan? The contract notes DDL causes implicit commits — is it specified whether partial index creation is rolled back or left in place? [Clarity, Contract §Transaction Boundaries] → **Resolved**: Already documented in ingestion pipeline contract §Transaction Boundaries. DDL runs in own transaction; failure triggers full cleanup (table drop + metadata delete).

## Requirement Completeness — AI Agent Context

- [x] CHK011 - Are requirements defined for how the agent should behave when `index_context` is None (e.g., querying a pre-existing dataset without indexes)? [Gap, Contract §SQL Generation Task] → **Resolved**: FR-017 added. Agent falls back to current behavior when index_context is None.
- [x] CHK012 - Is the maximum size of the index context string bounded? For a dataset with 50+ columns, the context block could be very large — are token budget concerns addressed? [Gap, Spec §Assumptions] → **Resolved**: FR-018 added. 4,000 character cap with summarization for wide datasets.
- [x] CHK013 - Are requirements specified for how the agent should handle queries that span both indexed and non-indexed datasets in a cross-dataset query? [Gap, Spec §Story 3 Scenario 3] → **Resolved**: FR-019 added. Index-aware patterns for datasets with metadata; standard patterns for others.
- [x] CHK014 - Is the agent guidance clear on when to use `to_tsquery` vs `plainto_tsquery` vs `phraseto_tsquery`? The acceptance scenarios mention all three but the rules section only shows `plainto_tsquery`. [Consistency, Contract §Context Format vs Spec §Story 1 Scenarios] → **Resolved**: `plainto_tsquery` is the default in the context pattern. Agent MAY use `phraseto_tsquery` or `to_tsquery` at its discretion based on natural language phrasing. See Clarifications Session 2 (CHK014).
- [x] CHK015 - Are requirements defined for how the agent should handle parameterization of vector similarity queries? The `%s::vector` placeholder requires the caller to provide an embedding — is it specified who generates the query embedding at runtime? [Gap, Contract §Context Format] → **Resolved**: Query execution layer generates embeddings. Agent emits `%s::vector` placeholder; execution layer calls `VectorSearchService.generate_embedding()`. Documented in SQL generation task context contract.

## Requirement Completeness — Embedding Generation (P2)

- [x] CHK016 - Are requirements defined for handling NULL or empty text values during embedding generation? Should NULLs result in NULL embeddings or be skipped? [Edge Case, Gap] → **Resolved**: FR-020 added. NULL → NULL embedding; empty string → NULL embedding (skipped). Updated in IndexManagerService contract.
- [x] CHK017 - Are requirements specified for embedding generation failure on individual rows (e.g., API timeout for one row out of 100K)? Is partial embedding acceptable or must all rows succeed? [Gap, Spec §FR-008] → **Resolved**: FR-021 added. Retry 3 times per row; partial embeddings acceptable if >90% success rate.
- [x] CHK018 - Is the batch size for embedding UPDATE operations specified? Updating 100K rows one at a time vs. batches of 1000 has significant performance implications. [Gap, Research §R5] → **Resolved**: FR-022 added. 500 rows per batch. Updated in IndexManagerService contract.
- [x] CHK019 - Are requirements defined for the `sample_size` parameter in `identify_qualifying_columns`? Is sampling 1000 rows sufficient to determine average text length for datasets with highly variable content? [Clarity, Contract §identify_qualifying_columns] → **Resolved**: 1000 rows is adequate for target scale. Configurable parameter. Datasets with <1000 rows use all rows. See Clarifications Session 2 (CHK019).

## Requirement Clarity — Thresholds & Heuristics

- [x] CHK020 - Is "average character length of 50 characters" an adequate heuristic for identifying descriptive content? Are there examples where this could misclassify (e.g., addresses averaging 45 chars, or encoded data averaging 60 chars)? [Clarity, Spec §Assumptions] → **Resolved**: Threshold is configurable. Boundary misclassification is acceptable (worst case: unnecessary but not harmful embeddings). See Clarifications Session 2 (CHK020).
- [x] CHK021 - Is the high-cardinality edge case ("millions of unique values") quantified with a specific threshold for skipping FTS indexes, or left as a vague guideline? [Clarity, Spec §Edge Cases] → **Resolved**: Quantified as cardinality ratio >0.95 AND avg text length <50. See Clarifications Session 2 (CHK021).
- [x] CHK022 - Is the distinction between "TEXT column" and "text-type column" explicitly defined? Does it include only columns inferred as TEXT, or also VARCHAR, CHAR? [Clarity, Spec §FR-002] → **Resolved**: Only columns inferred as PostgreSQL `TEXT` by schema detection. CSV schema detection infers all string columns as TEXT, so no ambiguity. See Clarifications Session 2 (CHK022).
- [x] CHK023 - Is "semantic intent" in FR-011 defined with specific criteria the agent can evaluate, or is it left to LLM judgment? [Ambiguity, Spec §FR-011] → **Resolved**: Intentionally left to LLM judgment. Natural language understanding of "similar to" vs "containing" is the agent's core competency. See Clarifications Session 2 (CHK023).

## Requirement Consistency

- [x] CHK024 - FR-012 says "record index creation status to enable graceful degradation" but the clarification says "dataset should not become available with missing indexes" (FR-013). Is "graceful degradation" still relevant if failure means the dataset is unavailable? [Conflict, Spec §FR-012 vs §FR-013] → **Resolved**: FR-012 amended. "Graceful degradation" → "failure diagnosis and informative error reporting." No conflict with FR-013.
- [x] CHK025 - Story 2, Scenario 4 mentions "partial indexes to exclude NULLs where appropriate" but the scope boundaries say "Partial indexes based on data distribution analysis" are out of scope. Are NULL-based partial indexes in scope or out? [Conflict, Spec §Story 2 vs §Scope Boundaries] → **Resolved**: Story 2 Scenario 4 updated to remove partial indexes. Standard indexes created on all columns (B-tree handles NULLs efficiently). Partial indexes are out of scope per scope boundaries.
- [x] CHK026 - The data model shows `capability` as a single value per index entry (filtering, full_text_search, vector_similarity), but B-tree indexes support both filtering AND sorting. Is one entry per capability, or should capability be a list/set? [Consistency, Data Model §Field Definitions] → **Resolved**: Single entry with `capability='filtering'`. Sorting is implicit B-tree capability conveyed in INDEX CAPABILITIES context. Documented in data-model.md field definitions.
- [x] CHK027 - The contract shows `create_indexes_for_dataset` takes `conn: Connection` but `create_embedding_indexes` takes `pool: ConnectionPool`. Is this inconsistency intentional (DDL needs dedicated connection) or should both use the same pattern? [Consistency, Contract §IndexManagerService] → **Resolved**: Intentional. `create_indexes_for_dataset` uses `conn` (sequential pipeline). `create_embedding_indexes` uses `pool` (needs multiple connections for ThreadPoolExecutor). Documented in IndexManagerService contract.

## Acceptance Criteria Quality

- [x] CHK028 - SC-001 states "All text search queries" should use FTS operators, but what about queries where the user explicitly asks for substring matching (e.g., "find names containing 'son'")? Is ILIKE ever acceptable? [Measurability, Spec §SC-001] → **Resolved**: ILIKE acceptable for explicit substring matching (FTS operates on word boundaries). SC-001 clarified to mean keyword/phrase searches. See Clarifications Session 2 (CHK028).
- [x] CHK029 - SC-004 defines success as "more relevant results (measured by user satisfaction or result quality)" — is this measurable without a formal evaluation framework? [Measurability, Spec §SC-004] → **Resolved**: SC-004 amended. Now measured by presence of `ORDER BY ts_rank()` in generated SQL (objective, verifiable).
- [x] CHK030 - SC-005 defines "no more than 50% increase in ingestion time" — is the baseline defined (with or without existing optional steps like column metadata computation)? [Measurability, Spec §SC-005] → **Resolved**: Baseline = current pipeline (steps 1-12 without new index steps). Measured on 100K-row reference dataset. See Clarifications Session 2 (CHK030).
- [x] CHK031 - Are acceptance scenarios defined for the `build_index_context` output format? Can the exact string format be tested against a known good example? [Gap, Contract §build_index_context] → **Resolved**: Five specific acceptance criteria defined. See Clarifications Session 2 (CHK031).

## Scenario Coverage

- [x] CHK032 - Are requirements defined for the scenario where a CSV has zero text columns (all numeric/date/boolean)? No tsvector columns or GIN indexes would be created — is the metadata registry still populated with just B-tree entries? [Coverage, Gap] → **Resolved**: Only B-tree indexes created; metadata populated with B-tree entries only. See spec extended edge cases.
- [x] CHK033 - Are requirements defined for the scenario where a CSV has only one row? The average text length calculation for embedding qualification may not be meaningful with a single sample. [Coverage, Edge Case] → **Resolved**: Single row used for average calculation. All indexes still created. See spec extended edge cases.
- [x] CHK034 - Are requirements defined for concurrent uploads by the same user? If two CSVs are uploaded simultaneously, could index creation for one interfere with the other in the same schema? [Coverage, Gap] → **Resolved**: No interference — unique table names per dataset, schema isolation. See spec extended edge cases.
- [x] CHK035 - Are requirements defined for the scenario where the embedding API is unavailable during ingestion (P2)? Does the dataset become available with only P1 indexes, or does the entire ingestion fail? [Coverage, Spec §FR-013] → **Resolved**: If P2 steps initiated, API failure fails ingestion. If no qualifying columns, P2 skipped. See spec extended edge cases.
- [x] CHK036 - Are requirements specified for what happens when a query targets multiple datasets where some have embedding indexes and others don't? [Coverage, Spec §Story 4 Scenario 2] → **Resolved**: See FR-019. Agent uses vector search for datasets with embeddings, standard patterns for others.

## Non-Functional Requirements

- [x] CHK037 - Are disk space requirements estimated for the additional indexes and generated columns? Each B-tree index, tsvector column, and embedding column adds storage — is this quantified for the 100K-row reference dataset? [Gap, NFR] → **Resolved**: Estimated 165MB-4GB for 100K-row, 15-column dataset depending on embedding qualification. See Clarifications Session 2 (CHK037).
- [x] CHK038 - Are embedding API cost implications specified? At $0.02/1M tokens (text-embedding-3-small), 100K rows of 200-char descriptions is ~20M tokens — is cost budgeting in scope? [Gap, NFR] → **Resolved**: ~$0.10 per qualifying column per ingestion. Cost monitoring out of scope. See Clarifications Session 2 (CHK038).
- [x] CHK039 - Are logging/observability requirements specified for index creation progress, embedding generation throughput, and failure diagnostics? [Gap, NFR] → **Resolved**: FR-023 added. Logging required for index creation progress, embedding throughput, and errors.
- [x] CHK040 - Are memory requirements addressed for the embedding generation step? Holding 100K embeddings (1536 floats each) in memory is ~600MB — is chunked processing required? [Gap, Research §R5] → **Resolved**: FR-022 limits batch to 500 rows (~3MB peak). Total memory bounded at ~50MB. See Clarifications Session 2 (CHK040).

## Dependencies & Assumptions

- [x] CHK041 - Is the assumption that "the existing agent framework supports extended task descriptions without token limit issues" validated? With 50+ columns, the index context could add 2000+ tokens to an already-long task description. [Assumption, Spec §Assumptions] → **Resolved**: FR-018 caps context at 4,000 characters (~1,000 tokens). Combined with existing ~2-3K token task description, stays within model context window. See Clarifications Session 2 (CHK041).
- [x] CHK042 - Is the assumption that the 'english' text search configuration is appropriate validated? For datasets containing non-English text (common in international CSV data), stemming would be incorrect. [Assumption, Spec §Assumptions] → **Resolved**: Validated. English config appropriate for current deployment. Non-English text matches on exact terms (degraded stemming). Multi-language out of scope. See updated assumption in spec and research.md R9.
- [x] CHK043 - Is the dependency on `VectorSearchService.generate_embedding()` being thread-safe validated? Concurrent calls from ThreadPoolExecutor must not share mutable state. [Assumption, Research §R5] → **Resolved**: Validation deferred to P2 implementation. Analysis and action plan documented in research.md R10.

## Notes

- Check items off as completed: `[x]`
- Items marked [Gap] indicate requirements that may need to be added to the spec
- Items marked [Conflict] indicate requirements that contradict each other
- Items marked [Ambiguity] indicate requirements that need sharper definition
- CHK001-CHK005: Data model domain
- CHK006-CHK010: Pipeline domain
- CHK011-CHK015: Agent context domain
- CHK016-CHK019: Embedding generation domain
- CHK020-CHK023: Thresholds & heuristics
- CHK024-CHK027: Consistency
- CHK028-CHK031: Acceptance criteria
- CHK032-CHK036: Scenario coverage
- CHK037-CHK040: Non-functional requirements
- CHK041-CHK043: Dependencies & assumptions

### Resolution Summary (2026-03-02)

All 43 items resolved. Changes made to:
- **spec.md**: Added FR-014 through FR-023, extended edge cases (7 new), Clarifications Session 2 (43 Q&As), amended FR-012, updated Story 2 Scenario 4, amended SC-004, updated language config assumption
- **data-model.md**: Updated field definitions (enforcement documentation, B-tree capability), added identifier length handling section, added column_name relationship note
- **contracts/index-metadata-service.md**: Updated `create_embedding_indexes` with batch size, NULL handling, retry behavior, conn vs pool rationale
- **contracts/sql-generation-task-context.md**: Added runtime embedding section documenting who generates query embeddings
- **contracts/ingestion-pipeline.md**: Added HTTP status codes, progress reporting section
- **research.md**: Added R9 (language config validation), R10 (thread safety analysis), identifier length handling note
