# Tasks: Index-Aware SQL Generation

**Input**: Design documents from `/specs/003-index-aware-sql/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per constitution (TDD NON-NEGOTIABLE). Tests MUST be written and FAIL before implementation.

**Organization**: Tasks grouped by user story. US2 (Index Creation) and US3 (Metadata Tracking) are implemented as separate phases despite tight coupling, because US2 can be independently verified via `pg_indexes` and US3 via the metadata registry. US1 (SQL Agent FTS) depends on US2+US3. US5 (Embedding Generation) depends on US2+US3. US4 (Agent Vector Similarity) depends on US5.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: New files and project structure for the feature

- [x] T001 [P] Create Pydantic models (IndexType, IndexCapability, IndexStatus enums, IndexMetadataEntry, DataColumnIndexProfile) in backend/src/models/index_metadata.py per data-model.md
- [x] T002 [P] Create IndexCreationError exception class in backend/src/services/index_manager.py (stub file with error type only, per contract)
- [x] T003 Add `index_metadata` table DDL to `ensure_user_schema_exists()` in backend/src/db/schemas.py per data-model.md DDL

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Implement index name generation utility function `generate_index_name(table_name, column_name, index_type)` in backend/src/services/index_manager.py with 63-character identifier truncation and MD5 hash suffix per data-model.md Identifier Length Handling
- [x] T005 Write unit tests for Pydantic models (IndexMetadataEntry validation, DataColumnIndexProfile properties: has_fulltext, has_vector, fulltext_column, embedding_column) in tests/unit/models/test_index_metadata.py
- [x] T006 Write unit tests for index name generation (normal names, truncated names exceeding 63 chars, hash uniqueness) in tests/unit/services/test_index_manager.py

**Checkpoint**: Foundation ready — models validated, name generation tested, schema DDL in place

---

## Phase 3: User Story 2 — Automatic Index Creation During CSV Ingestion (Priority: P1)

**Goal**: Every column in every uploaded CSV receives a B-tree index; every TEXT column receives a tsvector generated column and GIN index. Indexes created after bulk data load. Failed index creation fails the entire ingestion.

**Independent Test**: Upload a CSV, then query `pg_indexes` system catalog to verify B-tree indexes on all columns and GIN indexes on text columns' tsvector columns.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T007 [P] [US2] Write unit tests for `create_indexes_for_dataset()` B-tree index creation (all column types, correct SQL generation, naming conventions) in tests/unit/services/test_index_manager.py
- [ ] T008 [P] [US2] Write unit tests for `create_indexes_for_dataset()` tsvector column + GIN index creation (TEXT columns only, correct ALTER TABLE and CREATE INDEX SQL, naming conventions) in tests/unit/services/test_index_manager.py
- [ ] T009 [P] [US2] Write unit tests for index creation error handling (IndexCreationError raised on failure, partial_results populated, failed_index identified) in tests/unit/services/test_index_manager.py
- [ ] T010 [P] [US2] Write integration test for index creation on a real PostgreSQL table (upload CSV, verify B-tree indexes exist on all columns via pg_indexes, verify GIN indexes on text columns, verify tsvector generated columns exist) in tests/integration/test_index_creation.py

### Implementation for User Story 2

- [ ] T011 [US2] Implement B-tree index creation logic in `create_indexes_for_dataset()` in backend/src/services/index_manager.py — for each column: generate index name, execute CREATE INDEX IF NOT EXISTS, handle errors per FR-001, FR-007
- [ ] T012 [US2] Implement tsvector generated column + GIN index creation in `create_indexes_for_dataset()` in backend/src/services/index_manager.py — for each TEXT column: ALTER TABLE ADD COLUMN _ts_{col} TSVECTOR GENERATED ALWAYS, CREATE INDEX USING GIN, handle errors per FR-002
- [ ] T013 [US2] Implement error handling and cleanup in `create_indexes_for_dataset()` in backend/src/services/index_manager.py — on any failure: record status='failed' metadata entries, raise IndexCreationError with partial_results per FR-012, FR-013
- [ ] T014 [US2] Integrate `create_indexes_for_dataset()` into ingestion pipeline in backend/src/services/ingestion.py — call after `ingest_csv_data()` (step 9 per ingestion contract), pass connection, username, dataset_id, table_name, columns
- [ ] T015 [US2] Add error handling in backend/src/api/datasets.py upload endpoint — catch IndexCreationError, drop data table, delete dataset metadata, return HTTP 500 with error details per FR-016
- [ ] T016 [US2] Add progress reporting for index creation steps in backend/src/services/ingestion.py — emit progress events "Creating B-tree indexes" and "Creating full-text search indexes" per FR-015, FR-023

**Checkpoint**: Upload a CSV → all columns have B-tree indexes, TEXT columns have tsvector + GIN indexes, failures properly handled

---

## Phase 4: User Story 3 — Index Metadata Tracking and Discovery (Priority: P1)

**Goal**: Every created index is tracked in the `index_metadata` registry with its type, capability, and status. Index profiles can be queried per dataset. The `build_index_context()` function produces the INDEX CAPABILITIES text block for the SQL generation task.

**Independent Test**: Upload a CSV, then query `index_metadata` table to verify entries match the indexes created. Verify `get_index_profiles()` returns correct profiles.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T017 [P] [US3] Write unit tests for index metadata insertion (correct entries for B-tree, GIN indexes; status tracking; unique constraint on dataset_id+column_name+index_type) in tests/unit/services/test_index_manager.py
- [ ] T018 [P] [US3] Write unit tests for `get_index_profiles()` (groups by dataset_id and column_name, returns DataColumnIndexProfile objects, handles multiple datasets) in tests/unit/services/test_index_manager.py
- [ ] T019 [P] [US3] Write unit tests for `build_index_context()` (correct format per sql-generation-task-context contract; B-tree only columns; FTS columns with tsvector patterns; 4000 char cap per FR-018; empty profiles return empty string) in tests/unit/services/test_index_manager.py
- [ ] T020 [P] [US3] Write integration test for metadata tracking end-to-end (upload CSV → query index_metadata table → verify entries match pg_indexes catalog → verify ON DELETE CASCADE cleanup) in tests/integration/test_index_creation.py

### Implementation for User Story 3

- [ ] T021 [US3] Implement metadata insertion in `create_indexes_for_dataset()` in backend/src/services/index_manager.py — INSERT into index_metadata after each successful index creation, with correct index_type, capability, generated_column_name, and status per FR-003, FR-004
- [ ] T022 [US3] Implement `get_index_profiles()` in backend/src/services/index_manager.py — query index_metadata for given dataset_ids, group by (dataset_id, column_name), return dict[str, list[DataColumnIndexProfile]] per contract
- [ ] T023 [US3] Implement `build_index_context()` in backend/src/services/index_manager.py — format INDEX CAPABILITIES text block per sql-generation-task-context contract format, include B-tree/FTS patterns, enforce 4000-char cap with summarization per FR-018
- [ ] T024 [US3] Verify dataset deletion cleanup — confirm ON DELETE CASCADE removes index_metadata rows when dataset deleted, no additional code needed in backend/src/api/datasets.py per FR-009 (add assertion test in tests/integration/test_index_creation.py)

**Checkpoint**: Index metadata accurately reflects all created indexes, `build_index_context()` produces correctly formatted context string, deletion cleans up metadata

---

## Phase 5: User Story 1 — SQL Agent Uses Full-Text Search for Text Queries (Priority: P1) 🎯 MVP

**Goal**: The SQL generation agent receives index capability context and generates queries using `tsvector`/`tsquery` with `ts_rank` instead of `ILIKE` for text searches.

**Independent Test**: Upload a CSV with text columns, ask a text search question, verify the generated SQL uses `plainto_tsquery` and `ts_rank` instead of `ILIKE '%term%'`.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T025 [P] [US1] Write unit tests for `create_sql_generation_task()` with index_context parameter (context injected into task description after schema context; None handled gracefully; FTS and B-tree rules appended to requirements) in tests/unit/crew/test_sql_generation_task.py
- [ ] T026 [P] [US1] Write unit tests for index context retrieval in query processing flow (get_index_profiles called with correct dataset_ids; build_index_context called with correct profiles and table_names; index_context passed to task) in tests/unit/services/test_text_to_sql.py

### Implementation for User Story 1

- [ ] T027 [US1] Add `index_context: str | None = None` parameter to `create_sql_generation_task()` in backend/src/crew/tasks.py — inject index_context into task description after schema_context and before requirements section per sql-generation-task-context contract
- [ ] T028 [US1] Add two new requirements to the SQL generation task description in backend/src/crew/tasks.py — requirement 15 (PREFER FTS over ILIKE) and requirement 16 (use vector cosine distance) per sql-generation-task-context contract Updated Requirements Section
- [ ] T029 [US1] Modify query processing flow in backend/src/services/text_to_sql.py — after resolving target dataset_ids, call get_index_profiles() and build_index_context(), pass index_context to create_sql_generation_task() per sql-generation-task-context Caller Changes
- [ ] T030 [US1] Handle None/empty index_context gracefully in backend/src/crew/tasks.py — when index_context is None (pre-existing datasets), skip INDEX CAPABILITIES section, agent falls back to current behavior per FR-017

**Checkpoint**: P1 MVP complete — text queries produce FTS-aware SQL with tsvector/tsquery and relevance ranking instead of ILIKE

---

## Phase 6: User Story 5 — Embedding Generation for Data Column Values (Priority: P2)

**Goal**: Text columns with rich descriptive content (avg length >= 50 chars) get vector embeddings for all rows, stored in companion `_emb_{col}` columns with HNSW indexes.

**Independent Test**: Upload a CSV with a descriptive text column, verify that a vector column and HNSW index are created, and confirm that embeddings are populated for all rows.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T031 [P] [US5] Write unit tests for `identify_qualifying_columns()` (columns with avg length >= 50 qualify; short columns excluded; configurable threshold; sample_size behavior; datasets with < sample_size rows use all rows) in tests/unit/services/test_index_manager.py
- [ ] T032 [P] [US5] Write unit tests for `create_embedding_indexes()` (ALTER TABLE adds vector column; embeddings generated via ThreadPoolExecutor; batch UPDATE in 500-row chunks per FR-022; HNSW index created; NULL/empty text handling per FR-020; retry logic per FR-021; metadata recorded) in tests/unit/services/test_index_manager.py
- [ ] T033 [P] [US5] Write integration test for embedding generation end-to-end (upload CSV with descriptive text column → verify _emb_ column exists → verify HNSW index in pg_indexes → verify embeddings populated → verify index_metadata entry with capability=vector_similarity) in tests/integration/test_embedding_generation.py

### Implementation for User Story 5

- [ ] T034 [US5] Implement `identify_qualifying_columns()` in backend/src/services/index_manager.py — compute AVG(LENGTH(col)) over sample, return columns with avg >= min_avg_length per contract
- [ ] T035 [US5] Implement `create_embedding_indexes()` in backend/src/services/index_manager.py — for each qualifying column: ALTER TABLE ADD COLUMN _emb_{col} vector(1536), read text values, generate embeddings with ThreadPoolExecutor (10-20 workers), batch UPDATE (500 rows per FR-022), CREATE INDEX USING hnsw with vector_cosine_ops per research R5
- [ ] T036 [US5] Implement NULL/empty handling and retry logic in `create_embedding_indexes()` in backend/src/services/index_manager.py — skip NULL and empty strings (set NULL embedding per FR-020), retry failed rows 3 times, proceed if >90% success per FR-021
- [ ] T037 [US5] Integrate P2 steps into ingestion pipeline in backend/src/services/ingestion.py — after existing steps: call identify_qualifying_columns(), call create_embedding_indexes() for qualifying columns, record metadata, emit progress events per ingestion contract steps 13-14
- [ ] T038 [US5] Add P2 error handling in backend/src/api/datasets.py — if embedding generation initiated but fails catastrophically (<90% success), fail ingestion per FR-013 extended edge cases

**Checkpoint**: Descriptive text columns receive embeddings and HNSW indexes, metadata tracks vector_similarity capability

---

## Phase 7: User Story 4 — SQL Agent Uses Vector Similarity for Semantic Queries (Priority: P2)

**Goal**: When embedding indexes are available, the SQL generation agent generates queries using cosine distance operator for semantic/meaning-based searches. The query execution layer handles runtime embedding generation.

**Independent Test**: Upload a CSV with embedded descriptive columns, ask a semantic question, verify generated SQL includes `<=>` cosine distance operator.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T039 [P] [US4] Write unit tests for vector context in `build_index_context()` (columns with has_vector include _emb_ column and distance operator pattern; mixed columns show both FTS and vector patterns) in tests/unit/services/test_index_manager.py
- [ ] T040 [P] [US4] Write unit tests for runtime embedding detection in query execution (detect %s::vector placeholders in generated SQL; generate embedding via VectorSearchService; pass as query parameter) in tests/unit/services/test_text_to_sql.py

### Implementation for User Story 4

- [ ] T041 [US4] Extend `build_index_context()` in backend/src/services/index_manager.py — for columns with has_vector, add vector similarity pattern block (ORDER BY _emb_{col} <=> %s::vector LIMIT 10, "Use for semantic/meaning-based searches") per sql-generation-task-context contract
- [ ] T042 [US4] Implement runtime embedding generation in query execution layer in backend/src/services/text_to_sql.py — detect `%s::vector` placeholders in generated SQL, call VectorSearchService.generate_embedding(query_text), pass embedding as query parameter per sql-generation-task-context Runtime Embedding section
- [ ] T043 [US4] Validate VectorSearchService thread safety for use with ThreadPoolExecutor in backend/src/services/vector_search.py — inspect for shared mutable state, refactor if needed per research R10

**Checkpoint**: Semantic queries produce vector similarity SQL, runtime embeddings generated for query execution

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, validation, and cross-cutting improvements

- [ ] T044 [P] Run quality gates: `ruff check backend/src backend/tests`, `ruff format backend/src backend/tests`, `mypy --strict backend/src backend/tests`, `pylint backend/src backend/tests` — fix all violations
- [ ] T045 [P] Run `python scripts/check_local_var_types.py backend/src/**/*.py backend/tests/**/*.py` — fix all missing local variable type annotations
- [ ] T046 Run full test suite `pytest tests/ -v` — verify all tests pass (unit, integration, contract)
- [ ] T047 Validate quickstart.md scenarios — upload a CSV, verify indexes via SQL queries shown in quickstart.md, verify FTS query generates correct SQL

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US2 (Phase 3)**: Depends on Phase 2 — Index creation must exist before metadata or context
- **US3 (Phase 4)**: Depends on Phase 3 — Metadata tracking needs index creation to populate entries
- **US1 (Phase 5)**: Depends on Phase 4 — SQL task context needs metadata profiles and build_index_context
- **US5 (Phase 6)**: Depends on Phase 4 — Embedding generation reuses IndexManagerService and metadata infrastructure
- **US4 (Phase 7)**: Depends on Phase 5 + Phase 6 — Vector context needs both SQL task injection and embedding indexes
- **Polish (Phase 8)**: Depends on all phases complete

### User Story Dependencies

```text
Phase 1 (Setup) → Phase 2 (Foundational)
                        ↓
                  Phase 3 (US2: Index Creation)
                        ↓
                  Phase 4 (US3: Metadata Tracking)
                      ↙       ↘
Phase 5 (US1: FTS)      Phase 6 (US5: Embeddings)
                      ↘       ↙
                  Phase 7 (US4: Vector Similarity)
                        ↓
                  Phase 8 (Polish)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/utilities before services
- Services before endpoint integration
- Core implementation before error handling and progress reporting

### Parallel Opportunities

**Within Phase 1**: T001, T002, T003 can all run in parallel (different files)
**Within Phase 2**: T005, T006 can run in parallel (different test files)
**Within US2 tests**: T007, T008, T009, T010 can all run in parallel
**Within US3 tests**: T017, T018, T019, T020 can all run in parallel
**Within US1 tests**: T025, T026 can run in parallel
**Within US5 tests**: T031, T032, T033 can all run in parallel
**Within US4 tests**: T039, T040 can run in parallel
**Across stories**: US1 (Phase 5) and US5 (Phase 6) can run in parallel once Phase 4 completes

---

## Parallel Example: Phase 1 (Setup)

```bash
# All three tasks create different files — run in parallel:
Task T001: "Create Pydantic models in backend/src/models/index_metadata.py"
Task T002: "Create IndexCreationError in backend/src/services/index_manager.py"
Task T003: "Add index_metadata DDL in backend/src/db/schemas.py"
```

## Parallel Example: US2 Tests

```bash
# All four test tasks write to different files or test different concerns:
Task T007: "Unit tests for B-tree index creation"
Task T008: "Unit tests for tsvector + GIN index creation"
Task T009: "Unit tests for error handling"
Task T010: "Integration test for index creation on PostgreSQL"
```

---

## Implementation Strategy

### MVP First (P1 Complete = Phases 1-5)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: US2 — Index Creation (T007-T016)
4. Complete Phase 4: US3 — Metadata Tracking (T017-T024)
5. Complete Phase 5: US1 — SQL Agent FTS (T025-T030)
6. **STOP and VALIDATE**: Upload CSV, ask text search, verify FTS SQL generated
7. Deploy/demo if ready — P1 delivers full value without P2

### Incremental Delivery

1. Phases 1-2 → Foundation ready
2. Add US2 (Phase 3) → Upload CSV → indexes visible in pg_indexes
3. Add US3 (Phase 4) → Index metadata tracked → build_index_context works
4. Add US1 (Phase 5) → **MVP!** Text queries produce FTS SQL
5. Add US5 (Phase 6) → Descriptive columns get vector embeddings
6. Add US4 (Phase 7) → Semantic queries produce vector similarity SQL
7. Phase 8 → Quality gates, polish, validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently verifiable at its checkpoint
- Constitution requires TDD — tests written and failing before implementation
- Constitution requires: ruff, mypy --strict, pylint 10.00/10.00, explicit local variable types
- Thread-based concurrency only (no async/await) — ThreadPoolExecutor for parallel embedding
- Commit after each task or logical group per CLAUDE.md checkpoint commit guidelines
