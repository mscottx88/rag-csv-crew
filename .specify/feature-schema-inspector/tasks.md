# Tasks: Schema Inspector Agent & Metadata Precomputation

**Feature**: Enhance RAG CSV Crew with schema inspection and metadata precomputation capabilities

**Input**: Plan from agent afcd092, feature specification from .specify/feature-schema-inspector.md

**Organization**: Tasks organized by capability (US1: Metadata Precomputation, US2: Schema Inspector Agent)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 or US2)
- Include exact file paths in descriptions

## Path Conventions

Project uses web app structure:
- Backend: `backend/src/`, `backend/tests/`
- Frontend: `frontend/src/`

---

## Phase 1: Setup (Database Schema)

**Purpose**: Add database schema for column metadata storage

- [X] T001 Add COLUMN_METADATA_TABLE_SQL constant to backend/src/db/schemas.py
- [X] T002 Add column_metadata table indexes (dataset, top_values GIN) to backend/src/db/schemas.py
- [X] T003 Create add_column_metadata_table() migration function in backend/src/db/migrations.py
- [X] T004 Update create_user_schema() to include column_metadata table in backend/src/db/migrations.py

---

## Phase 2: Foundational (Core Services)

**Purpose**: Core services needed by both user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Create ColumnMetadataService class with __init__ in backend/src/services/column_metadata.py
- [X] T006 [P] Create SchemaInspectorService class with __init__ in backend/src/services/schema_inspector.py (already existed)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Metadata Precomputation (Priority: P1) 🎯 MVP

**Goal**: Compute and store column-level statistics (min/max, distinct counts, sample values) during CSV upload to enable richer embeddings and better query understanding

**Independent Test**: Upload CSV → verify column_metadata table populated with statistics → verify embeddings include metadata context

### Implementation for User Story 1

**Step 1: Metadata Computation**

- [X] T007 [P] [US1] Implement _compute_numeric_stats() method in backend/src/services/column_metadata.py
- [X] T008 [P] [US1] Implement _compute_text_stats() method in backend/src/services/column_metadata.py
- [X] T009 [P] [US1] Implement _compute_general_stats() method in backend/src/services/column_metadata.py
- [X] T010 [US1] Implement _compute_column_metadata() method with type dispatching in backend/src/services/column_metadata.py
- [X] T011 [US1] Implement compute_and_store_metadata() with ThreadPoolExecutor in backend/src/services/column_metadata.py
- [X] T012 [US1] Implement _store_metadata_batch() with UPSERT logic in backend/src/services/column_metadata.py
- [X] T013 [US1] Implement get_column_metadata() retrieval method in backend/src/services/column_metadata.py

**Step 2: Ingestion Pipeline Integration**

- [X] T014 [US1] Reorder upload_dataset() pipeline: move metadata computation before embeddings in backend/src/api/datasets.py
- [X] T015 [US1] Add metadata computation call after ingest_csv_data() in backend/src/api/datasets.py
- [X] T016 [US1] Add logging for metadata_computed event in backend/src/api/datasets.py
- [X] T017 [US1] Add error handling with graceful degradation for metadata failures in backend/src/api/datasets.py

**Step 3: Enriched Embeddings**

- [X] T018 [US1] Add include_metadata parameter to generate_column_embeddings() in backend/src/services/ingestion.py
- [X] T019 [US1] Implement metadata enrichment logic in generate_column_embeddings() in backend/src/services/ingestion.py
- [X] T020 [US1] Add numeric range context to embedding text (min/max) in backend/src/services/ingestion.py
- [X] T021 [US1] Add sample values context to embedding text (top 5) in backend/src/services/ingestion.py
- [X] T022 [US1] Add cardinality context to embedding text (distinct count) in backend/src/services/ingestion.py

**Step 4: Quality & Performance**

- [X] T023 [US1] Run ruff check on backend/src/services/column_metadata.py
- [X] T024 [US1] Run ruff format on backend/src/services/column_metadata.py
- [X] T025 [US1] Run mypy --strict on backend/src/services/column_metadata.py
- [X] T026 [US1] Run pylint on backend/src/services/column_metadata.py and fix to 10.00/10
- [ ] T027 [US1] Commit metadata precomputation implementation with quality gates passed

**Checkpoint**: Metadata is computed during upload, stored in database, and enriches embeddings

---

## Phase 4: User Story 2 - Schema Inspector Agent (Priority: P2)

**Goal**: Add CrewAI agent that inspects database schemas to provide context for SQL query generation, improving query accuracy and reducing errors

**Independent Test**: Submit query → schema inspector provides table/column context → SQL generator uses correct schema → query executes successfully

### Implementation for User Story 2

**Step 1: Schema Query Methods**

- [ ] T028 [P] [US2] Implement get_available_datasets() in backend/src/services/schema_inspector.py
- [ ] T029 [P] [US2] Implement get_dataset_schema() in backend/src/services/schema_inspector.py
- [ ] T030 [P] [US2] Implement get_column_details() in backend/src/services/schema_inspector.py
- [ ] T031 [P] [US2] Implement get_relationships() in backend/src/services/schema_inspector.py
- [ ] T032 [P] [US2] Implement get_sample_data() in backend/src/services/schema_inspector.py
- [ ] T033 [US2] Integrate get_column_metadata() call in get_column_details() in backend/src/services/schema_inspector.py

**Step 2: CrewAI Tools**

- [ ] T034 [P] [US2] Create set_schema_inspector_context() global state injection in backend/src/crew/tools.py
- [ ] T035 [P] [US2] Implement list_datasets_tool() with @tool decorator in backend/src/crew/tools.py
- [ ] T036 [P] [US2] Implement inspect_schema_tool() with @tool decorator in backend/src/crew/tools.py
- [ ] T037 [P] [US2] Implement get_sample_data_tool() with @tool decorator in backend/src/crew/tools.py

**Step 3: CrewAI Agent & Task**

- [ ] T038 [US2] Create create_schema_inspector_agent() function in backend/src/crew/agents.py
- [ ] T039 [US2] Define agent role, goal, and backstory in create_schema_inspector_agent() in backend/src/crew/agents.py
- [ ] T040 [US2] Create create_schema_inspection_task() function in backend/src/crew/tasks.py
- [ ] T041 [US2] Define task description with tool usage instructions in create_schema_inspection_task() in backend/src/crew/tasks.py

**Step 4: Integration with Text-to-SQL**

- [ ] T042 [US2] Add use_schema_inspection parameter to generate_sql() in backend/src/services/text_to_sql.py
- [ ] T043 [US2] Instantiate SchemaInspectorService in generate_sql() in backend/src/services/text_to_sql.py
- [ ] T044 [US2] Call set_schema_inspector_context() with service and username in backend/src/services/text_to_sql.py
- [ ] T045 [US2] Create schema inspector agent and attach tools in backend/src/services/text_to_sql.py
- [ ] T046 [US2] Create schema inspection task in backend/src/services/text_to_sql.py
- [ ] T047 [US2] Set inspector task as context for SQL generation task in backend/src/services/text_to_sql.py
- [ ] T048 [US2] Update create_sql_generation_task() to reference schema context in backend/src/crew/tasks.py

**Step 5: Quality & Performance**

- [ ] T049 [US2] Run ruff check on backend/src/services/schema_inspector.py
- [ ] T050 [US2] Run ruff format on backend/src/services/schema_inspector.py
- [ ] T051 [US2] Run mypy --strict on backend/src/services/schema_inspector.py
- [ ] T052 [US2] Run pylint on backend/src/services/schema_inspector.py and fix to 10.00/10
- [ ] T053 [US2] Run quality checks on backend/src/crew/tools.py (ruff, mypy, pylint)
- [ ] T054 [US2] Commit schema inspector implementation with quality gates passed

**Checkpoint**: Schema inspector provides database context to SQL generation, improving query accuracy

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Testing, optimization, and documentation

**Integration Testing**

- [ ] T055 [P] Test metadata computation accuracy against manual calculations
- [ ] T056 [P] Test metadata computation performance (<5s for 50-column dataset)
- [ ] T057 [P] Test enriched embeddings improve semantic search relevance
- [ ] T058 [P] Test schema inspector provides correct table/column names
- [ ] T059 [P] Test schema inspector completes in <2s for typical queries
- [ ] T060 [P] Test SQL generation uses schema context correctly

**Performance Optimization**

- [ ] T061 Verify ThreadPoolExecutor provides speedup for metadata computation
- [ ] T062 Profile and optimize slow metadata queries if needed
- [ ] T063 Add caching layer to SchemaInspectorService for repeated queries

**Documentation**

- [ ] T064 [P] Update MEMORY.md with metadata precomputation learnings
- [ ] T065 [P] Update MEMORY.md with schema inspector integration patterns
- [ ] T066 [P] Document metadata computation performance characteristics

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3 & 4)**: Both depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (different files)
  - Or sequentially in priority order (US1 → US2)
- **Polish (Phase 5)**: Depends on both user stories being complete

### User Story Dependencies

- **User Story 1 (US1)**: Can start after Foundational (Phase 2) - No dependencies on US2
- **User Story 2 (US2)**: Can start after Foundational (Phase 2) - US1 not required but recommended (richer metadata for schema context)

### Within User Story 1

1. T007-T009 (stat methods) → T010 (dispatcher) → T011 (orchestrator) → T012 (storage) → T013 (retrieval)
2. T014-T017 (ingestion integration) depends on T011 complete
3. T018-T022 (enriched embeddings) depends on T013 complete
4. T023-T027 (quality) runs after all implementation

### Within User Story 2

1. T028-T033 (schema methods) can run in parallel
2. T034-T037 (tools) can run in parallel, requires T028-T032 complete
3. T038-T041 (agent/task) depends on T034-T037 complete
4. T042-T048 (integration) depends on T038-T041 complete
5. T049-T054 (quality) runs after all implementation

### Parallel Opportunities

- **Phase 1**: All 4 tasks modify same file, run sequentially
- **Phase 2**: T005 and T006 can run in parallel (different files)
- **US1 Step 1**: T007, T008, T009 can run in parallel (same file, different methods)
- **US1 Step 4**: T023-T026 can run in parallel (same file, different tools)
- **US2 Step 1**: T028-T032 can run in parallel (same file, different methods)
- **US2 Step 2**: T034-T037 can run in parallel (same file, different functions)
- **Phase 5 Integration**: T055-T060 can run in parallel (different test files)
- **Phase 5 Docs**: T064-T066 can run in parallel (different sections)

---

## Parallel Example: User Story 1 Step 1

```bash
# Launch all stat computation methods together:
Task: "Implement _compute_numeric_stats() method in backend/src/services/column_metadata.py"
Task: "Implement _compute_text_stats() method in backend/src/services/column_metadata.py"
Task: "Implement _compute_general_stats() method in backend/src/services/column_metadata.py"
```

## Parallel Example: User Story 2 Step 1

```bash
# Launch all schema query methods together:
Task: "Implement get_available_datasets() in backend/src/services/schema_inspector.py"
Task: "Implement get_dataset_schema() in backend/src/services/schema_inspector.py"
Task: "Implement get_column_details() in backend/src/services/schema_inspector.py"
Task: "Implement get_relationships() in backend/src/services/schema_inspector.py"
Task: "Implement get_sample_data() in backend/src/services/schema_inspector.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (database schema)
2. Complete Phase 2: Foundational (core services)
3. Complete Phase 3: User Story 1 (metadata precomputation)
4. **STOP and VALIDATE**: Upload CSV, verify metadata in database, test enriched embeddings
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **Deploy/Demo (MVP! Richer embeddings)**
3. Add User Story 2 → Test independently → **Deploy/Demo (Full system with schema inspection)**
4. Each story adds value without breaking previous functionality

### Parallel Team Strategy

With 2 developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Metadata Precomputation)
   - Developer B: User Story 2 (Schema Inspector Agent)
3. Stories complete and integrate independently
4. Integration testing in Phase 5

---

## Task Summary

**Total Tasks**: 66

**By Phase**:
- Phase 1 (Setup): 4 tasks
- Phase 2 (Foundational): 2 tasks
- Phase 3 (US1 - Metadata): 21 tasks
- Phase 4 (US2 - Schema Inspector): 27 tasks
- Phase 5 (Polish): 12 tasks

**By Story**:
- US1 (Metadata Precomputation): 21 tasks
- US2 (Schema Inspector Agent): 27 tasks
- Infrastructure/Setup: 6 tasks
- Polish/Testing: 12 tasks

**Parallel Opportunities**: 28 tasks marked [P]

**Suggested MVP**: US1 only (metadata precomputation) = 27 tasks total (Setup + Foundational + US1)

---

## Notes

- [P] tasks = different files or independent sections, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each major step (T027, T054, etc.)
- Quality gates (ruff, mypy, pylint) MUST pass before committing
- Stop at any checkpoint to validate story independently
- US1 provides foundation for US2 (richer metadata) but US2 can proceed without US1 complete
