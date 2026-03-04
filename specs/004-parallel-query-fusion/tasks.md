# Tasks: Parallel Query Fusion

**Input**: Design documents from `/specs/004-parallel-query-fusion/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: TDD is required per constitution (Principle II). Tests MUST be written and FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/` for production code, `tests/` for test code

---

## Phase 1: Setup

**Purpose**: Verify prerequisites and understand existing interfaces that will be modified

- [X] T001 Review existing interfaces in backend/src/services/text_to_sql.py, backend/src/services/query_execution.py, backend/src/services/response_generator.py, backend/src/crew/tasks.py, and backend/src/api/queries.py to understand current signatures and patterns

---

## Phase 2: Foundational — Pydantic Models

**Purpose**: Core data models used by ALL user stories. MUST complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first, verify they fail)

- [X] T002 Write unit tests for all fusion Pydantic models (StrategyType enum, StrategySQL, StrategyResult, StrategyAttribution, FusedRow, FusedResult, StrategyDispatchPlan) validating constraints, defaults, frozen configs, and model validators in tests/unit/models/test_fusion_models.py

### Implementation

- [X] T003 Implement all Pydantic models (StrategyType, StrategySQL, StrategyResult, StrategyAttribution, FusedRow, FusedResult, StrategyDispatchPlan) per data-model.md in backend/src/models/fusion.py
- [X] T004 Verify fusion model tests pass and run quality checks (ruff, mypy --strict, pylint) on new files

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Parallel Multi-Strategy Query Execution (Priority: P1) 🎯 MVP

**Goal**: Dispatch up to three query strategies (structured, fulltext, vector) in parallel using ThreadPoolExecutor and collect all results, with graceful degradation when individual strategies fail or time out.

**Independent Test**: Submit a natural language query against a dataset with FTS and vector indexes, verify that multiple SQL statements were dispatched concurrently and results from each are returned.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T005 [P] [US1] Write unit tests for StrategyDispatcherService.plan_strategies — test index_metadata queries returning applicable strategies, dataset_ids=None handling (FR-017), structured-always-first validation — in tests/unit/services/test_strategy_dispatcher.py
- [X] T006 [P] [US1] Write unit tests for multi-strategy SQL prompt generation — test create_sql_generation_task with strategy_dispatch parameter, labeled block format, per-strategy guidelines, ctid inclusion — in tests/unit/crew/test_sql_generation_task.py
- [X] T007 [P] [US1] Write unit tests for parse_multi_strategy_sql — test regex extraction of strategy blocks, malformed output handling (FR-020), retry on zero blocks (FR-016), fallback to single-strategy, parameter extraction — in tests/unit/services/test_text_to_sql.py
- [X] T008 [P] [US1] Write unit tests for execute_strategies_parallel — test parallel execution of multiple strategies, per-strategy timeout (NFR-002), graceful degradation on failure (FR-012), cancel_event propagation (FR-006), vector parameter resolution, server-side row limit enforcement to 50 rows (FR-011), StrategyResult construction — in tests/unit/services/test_query_execution.py

### Implementation for User Story 1

- [X] T009 [P] [US1] Implement StrategyDispatcherService with plan_strategies method — query index_metadata for dataset capabilities (filtering, full_text_search, vector_similarity), build StrategyDispatchPlan with applicable strategies, handle dataset_ids=None (FR-005, FR-017) — in backend/src/services/strategy_dispatcher.py
- [X] T010 [P] [US1] Modify create_sql_generation_task to accept strategy_dispatch parameter — add multi-strategy prompt section with labeled block delimiters (---STRATEGY: name--- / ---END STRATEGY---), per-strategy guidelines for structured/fulltext/vector, ctid as first SELECT column, LIMIT 50 per strategy (FR-016) — in backend/src/crew/tasks.py
- [X] T011 [P] [US1] Implement parse_multi_strategy_sql (regex parser for labeled blocks), generate_multi_strategy_sql (orchestrates CrewAI call, parses output, retries once on zero blocks, falls back to single-strategy on double failure) — in backend/src/services/text_to_sql.py
- [X] T012 [P] [US1] Implement execute_strategies_parallel (ThreadPoolExecutor dispatch) and _execute_single_strategy (connection acquisition, search_path, SQL execution, vector embedding resolution for %s::vector, timeout, server-side row limit enforcement truncating results to 50 rows regardless of LLM LIMIT clause per FR-011, StrategyResult construction) — in backend/src/services/query_execution.py
- [X] T013 [US1] Verify all US1 unit tests pass and run quality checks (ruff, mypy --strict, pylint)

**Checkpoint**: Parallel multi-strategy query execution works. Strategies are selected, SQL is generated, queries run in parallel, and individual results are collected.

---

## Phase 4: User Story 2 — Result Fusion and Deduplication (Priority: P1) 🎯 MVP

**Goal**: Merge results from all parallel strategies into a single composite result set using Reciprocal Rank Fusion (RRF, k=60) with ctid-based deduplication. Rows found by multiple strategies receive boosted composite scores.

**Independent Test**: Provide overlapping result sets from structured and FTS strategies, verify duplicates are collapsed by ctid, RRF scores are computed correctly, and final ordering reflects cross-strategy relevance.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T014 [P] [US2] Write unit tests for ResultFusionService — test compute_rrf_scores (k=60 formula, single strategy, multi-strategy, tie-breaking per FR-009), deduplicate_rows (ctid matching, data from first strategy in priority order, source_strategies accumulation), fuse (end-to-end: filter failed strategies, score, dedup, sort, build attributions), system column exclusion (ctid, _ts_*, _emb_*, rank, similarity per FR-007), edge cases (all strategies fail, one returns empty, missing ctid column, single strategy pass-through) — in tests/unit/services/test_result_fusion.py

### Implementation for User Story 2

- [X] T015 [US2] Implement ResultFusionService with fuse(), compute_rrf_scores(), and deduplicate_rows() methods — RRF scoring with k=60 (FR-009), ctid-based dedup keeping first strategy's data in priority order structured>fulltext>vector (FR-008), system column filtering (FR-007), StrategyAttribution construction, FusedResult assembly with sorted rows (FR-010) — in backend/src/services/result_fusion.py
- [X] T016 [US2] Verify all US2 unit tests pass and run quality checks (ruff, mypy --strict, pylint)

**Checkpoint**: US1 + US2 together form the core MVP. Strategies execute in parallel and results are fused into a single deduplicated, scored result set.

---

## Phase 5: User Story 3 — Composite HTML Response (Priority: P2)

**Goal**: Format the fused result set into a single unified HTML response with strategy attribution summary when multiple strategies contributed. Single-strategy responses look identical to pre-feature output.

**Independent Test**: Provide a pre-fused result set to the HTML formatter and verify the output contains a strategy attribution summary and a single unified data presentation.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T017 [P] [US3] Write unit tests for modified generate_html_response — test fused_result parameter acceptance, multi-strategy attribution inclusion (FR-014: "Results from structured query (N rows), full-text search (N rows), and semantic search (N rows)"), single-strategy attribution omission (FR-015), zero-results handling, ctid exclusion from output (FR-013), backwards compatibility when fused_result=None — in tests/unit/services/test_response_generator.py

### Implementation for User Story 3

- [X] T018 [US3] Modify ResponseGenerator.generate_html_response to add keyword-only fused_result: FusedResult | None = None parameter (preserving existing params: query_text, query_results, _query_id, confidence_threshold) — when fused_result provided and is_multi_strategy, add attribution summary to CrewAI prompt with human-readable strategy names (structured→"structured query", fulltext→"full-text search", vector→"semantic search"), when single-strategy or None, preserve existing behavior (FR-014, FR-015) — in backend/src/services/response_generator.py
- [X] T019 [US3] Verify all US3 unit tests pass and run quality checks (ruff, mypy --strict, pylint)

**Checkpoint**: Multi-strategy responses include attribution. Single-strategy responses are unchanged.

---

## Phase 6: User Story 4 — Strategy Selection Based on Index Availability (Priority: P2)

**Goal**: Detect aggregation intent in user queries and skip FTS/vector strategies for aggregate questions. Verify correct strategy selection across datasets with varying index profiles.

**Independent Test**: Configure datasets with varying index profiles (all indexes, FTS-only, B-tree-only) and verify only applicable strategies are dispatched. Submit aggregation queries and verify only structured strategy is used.

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US4] Write unit tests for detect_aggregation_intent — test keyword matching (count, sum, average, avg, total, minimum, min, maximum, max, "how many", "what is the total/average/sum"), case insensitivity, false positive acceptance (FR-019), non-aggregation queries — in tests/unit/services/test_strategy_dispatcher.py
- [X] T021 [US4] Write unit tests for aggregation-aware plan_strategies — test is_aggregation=True returns only structured (FR-019), cross-dataset queries with different index profiles (US4 AS3), single-strategy bypass detection (FR-021) — in tests/unit/services/test_strategy_dispatcher.py

### Implementation for User Story 4

- [X] T022 [US4] Implement detect_aggregation_intent static method with case-insensitive keyword matching in backend/src/services/strategy_dispatcher.py
- [X] T023 [US4] Verify all US4 unit tests pass and run quality checks (ruff, mypy --strict, pylint)

**Checkpoint**: Strategy selection is now intelligent — aggregation queries use structured only, and strategy dispatch respects per-dataset index profiles.

---

## Phase 7: Integration & Pipeline Wiring

**Purpose**: Wire all components together in the API layer and validate end-to-end behavior

### Tests

- [ ] T024 Write end-to-end integration tests for multi-strategy query pipeline — cover US1 AS1 (3 strategies dispatched), US1 AS2 (B-tree only → structured only), US1 AS3 (one strategy fails, others succeed), US2 AS1 (overlapping rows fused with boosted scores), US2 AS2 (single strategy pass-through), US2 AS3 (row in all 3 strategies), US3 AS1 (multi-strategy HTML with attribution), US3 AS2 (single-strategy no attribution), US3 AS3 (zero results), US4 AS1 (FTS but no vector), US4 AS2 (B-tree only) — in tests/integration/test_parallel_query.py

### Implementation

- [ ] T025 Integrate multi-strategy pipeline into _execute_sql_query in backend/src/api/queries.py — add strategy dispatch (call StrategyDispatcherService with aggregation detection), route to multi-strategy or single-strategy path (FR-021), call generate_multi_strategy_sql, execute_strategies_parallel, ResultFusionService.fuse, ResponseGenerator with fused_result, store multi-strategy SQL in generated_sql field (FR-022), add progress messages (FR-023: "Generating multi-strategy SQL...", "Executing N strategies in parallel...", "Fusing results from N strategies...", "Generating response..."), add observability logging (FR-018: strategy_dispatch, strategy_execution_complete, fusion_complete events)
- [ ] T026 Verify integration tests pass and run full quality suite (pytest, ruff, mypy --strict, pylint)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and quality assurance

- [ ] T027 [P] Write performance benchmark comparing multi-strategy vs single-strategy p95 latency on dataset with 10K+ rows and all three index types — verify total latency ≤ 130% of single-strategy baseline (NFR-001, SC-002) — in tests/performance/test_multi_strategy_latency.py
- [ ] T028 Run full test suite (pytest) and all quality checks (ruff check, ruff format, mypy --strict, pylint 10.00/10.00) across all modified and new files
- [ ] T029 Validate quickstart.md scenarios — test multi-strategy query with all 3 strategies, single-strategy fallback, aggregation query bypass, graceful degradation on strategy failure

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 review — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 completion (models available)
- **US2 (Phase 4)**: Depends on Phase 2 completion (models available). Independent of US1 code (tests with mock data)
- **US3 (Phase 5)**: Depends on Phase 2 completion (models available). Independent of US1/US2 code
- **US4 (Phase 6)**: Depends on Phase 3 T009 (StrategyDispatcherService exists — adds methods to it)
- **Integration (Phase 7)**: Depends on ALL user story phases (3, 4, 5, 6) complete
- **Polish (Phase 8)**: Depends on Phase 7 completion

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. No dependencies on other stories.
- **US2 (P1)**: Can start after Phase 2. Testable independently with mock StrategyResult data. No code dependency on US1.
- **US3 (P2)**: Can start after Phase 2. Testable independently with mock FusedResult data. No code dependency on US1/US2.
- **US4 (P2)**: Depends on US1 (adds to StrategyDispatcherService created in T009). Tests are independent.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD — constitutional requirement)
- Models before services
- Services before integration
- Story complete and quality-checked before moving to next priority

### Parallel Opportunities

- **Phase 2**: T002 (tests) runs first, then T003 (implementation)
- **Phase 3**: T005, T006, T007, T008 (all tests) can run in parallel. Then T009, T010, T011, T012 (all implementations) can run in parallel.
- **Phase 3 + Phase 4 + Phase 5**: US1 tests, US2 tests (T014), and US3 tests (T017) can all start in parallel once Phase 2 completes, since they test different services with mock data.
- **Phase 6**: T020 then T021 (both target test_strategy_dispatcher.py, sequential).

---

## Parallel Example: Phase 3 (US1) + Phase 4 (US2) + Phase 5 (US3)

```bash
# After Phase 2 completes, launch all test-writing tasks in parallel:
Task T005: "Unit tests for StrategyDispatcherService.plan_strategies"
Task T006: "Unit tests for multi-strategy SQL prompt"
Task T007: "Unit tests for parse_multi_strategy_sql"
Task T008: "Unit tests for execute_strategies_parallel"
Task T014: "Unit tests for ResultFusionService"
Task T017: "Unit tests for response generator attribution"

# After tests are written, launch all implementation tasks in parallel:
Task T009: "Implement StrategyDispatcherService"
Task T010: "Modify create_sql_generation_task"
Task T011: "Implement parse_multi_strategy_sql"
Task T012: "Implement execute_strategies_parallel"
Task T015: "Implement ResultFusionService"
Task T018: "Modify ResponseGenerator"
```

---

## Implementation Strategy

### MVP First (US1 + US2 — Core Pipeline)

1. Complete Phase 1: Setup (review existing code)
2. Complete Phase 2: Foundational (Pydantic models)
3. Complete Phase 3: US1 — Parallel execution pipeline
4. Complete Phase 4: US2 — Result fusion
5. **STOP and VALIDATE**: Test US1 + US2 independently — strategies dispatch, execute in parallel, and results are fused
6. Deploy/demo core pipeline

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) + Phase 4 (US2) → Core pipeline functional (MVP!)
3. Phase 5 (US3) → HTML attribution enhancement
4. Phase 6 (US4) → Smart strategy selection (aggregation detection)
5. Phase 7 → Full integration wired
6. Phase 8 → Quality validated

### Suggested MVP Scope

**US1 + US2** (both P1): The core value of this feature is parallel multi-strategy dispatch and RRF fusion. These two stories together deliver the key improvement — better recall and relevance through multi-strategy search. US3 (attribution) and US4 (aggregation detection) are P2 enhancements that can ship later.

---

## Notes

- [P] tasks = different files, no dependencies on other [P] tasks
- [Story] label maps task to specific user story for traceability
- All new code MUST use thread-based concurrency only (ThreadPoolExecutor, threading.Event) — no async/await
- All Python files MUST pass: ruff check, ruff format, mypy --strict, pylint 10.00/10.00
- All local variables MUST have explicit type annotations per constitution
- Commit after each completed task or logical group of tasks
