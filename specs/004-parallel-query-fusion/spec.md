# Feature Specification: Parallel Query Fusion

**Feature Branch**: `004-parallel-query-fusion`
**Created**: 2026-03-03
**Status**: Draft
**Input**: User description: "When generating the SQL there should be parallelism. multiple queries should be dispatched to answer the question effectively. if semantic query could be used, it should. if structured queries could be used, it should. if full text queries could be used, it should. these results, where possible should all be combined and the final composite result should be formatted in HTML."

## User Scenarios & Testing

### User Story 1 - Parallel Multi-Strategy Query Execution (Priority: P1)

When a user asks a question about their data, the system dispatches up to three query strategies in parallel — structured SQL (B-tree filtering/sorting/aggregation), full-text search (tsvector/GIN), and vector similarity (pgvector/HNSW) — rather than generating a single monolithic query. Each strategy runs independently and concurrently, and all results are collected once every strategy completes or times out.

**Why this priority**: This is the core value proposition. Today the system generates one SQL query that may or may not leverage all available index capabilities. Parallel dispatch ensures every relevant search technique is used, improving both recall and answer quality.

**Independent Test**: Can be tested by submitting a natural language query against a dataset with FTS and vector indexes, then verifying that multiple SQL statements were dispatched concurrently and that results from each are returned.

**Acceptance Scenarios**:

1. **Given** a dataset with B-tree, FTS, and vector indexes on a text column, **When** the user asks "find products related to wireless charging," **Then** the system dispatches a structured SQL query, a full-text search query, and a vector similarity query in parallel (verified by observability logs showing all three strategies dispatched with overlapping execution windows).
2. **Given** a dataset with only B-tree indexes (no FTS or vector), **When** the user asks a question, **Then** the system dispatches only the structured SQL query and does not attempt FTS or vector strategies.
3. **Given** all three strategies are dispatched, **When** one strategy fails or times out, **Then** the remaining strategies still return their results and the response is generated from whatever succeeded.

---

### User Story 2 - Result Fusion and Deduplication (Priority: P1)

After all parallel queries complete, the system merges their result sets into a single composite result. Duplicate rows (identified by matching PostgreSQL `ctid` values across strategy results) are collapsed into a single entry. Each row receives a composite relevance score using Reciprocal Rank Fusion (RRF) that reflects how many strategies found it and how highly each ranked it. The merged result is ordered by composite relevance so the most broadly relevant rows appear first.

**Why this priority**: Without fusion, parallel queries would just produce three disconnected result sets. Fusion is what turns multi-strategy dispatch into a single coherent answer.

**Independent Test**: Can be tested by submitting a query that returns overlapping rows from structured and FTS strategies, then verifying that duplicates are collapsed, composite scores are computed, and the final ordering reflects cross-strategy relevance.

**Acceptance Scenarios**:

1. **Given** the structured query returns rows {A, B, C} and the FTS query returns rows {B, C, D}, **When** results are fused, **Then** rows B and C appear once each with boosted composite scores, and the final set is {B, C, A, D} (B and C ranked higher because two strategies found them).
2. **Given** only the vector similarity strategy returns results (other strategies return empty), **When** results are fused, **Then** the vector results are returned as-is without penalty.
3. **Given** a row appears in all three strategy results, **When** results are fused, **Then** that row's composite score reflects contributions from all three strategies.

---

### User Story 3 - Composite HTML Response (Priority: P2)

The fused, deduplicated result set is formatted into a single HTML response that presents results to the user. The response includes a summary of which query strategies contributed results and how many rows each found. The HTML follows the existing formatting conventions (semantic HTML5, tables for tabular data, clear headings).

**Why this priority**: The user needs a single coherent answer, not three separate result tables. This story depends on US1 and US2 but can be tested independently with mock fused results.

**Independent Test**: Can be tested by providing a pre-fused result set to the HTML formatter and verifying the output contains a strategy attribution summary and a single unified data presentation.

**Acceptance Scenarios**:

1. **Given** a fused result set with contributions from structured and FTS strategies, **When** the HTML response is generated, **Then** it contains a single data table (not separate tables per strategy) with a brief attribution note above the table listing each contributing strategy and its row count (e.g., "Results from structured query (12 rows) and full-text search (18 rows)").
2. **Given** a fused result set where only one strategy contributed, **When** the HTML response is generated, **Then** no strategy attribution is shown (single-strategy responses look identical to today's output).
3. **Given** zero results across all strategies, **When** the HTML response is generated, **Then** a helpful message is displayed suggesting query refinements.

---

### User Story 4 - Strategy Selection Based on Index Availability (Priority: P2)

Before dispatching queries, the system inspects the index metadata for the target datasets and determines which strategies are applicable. A strategy is only dispatched if the necessary indexes exist. This avoids wasting resources on queries that cannot succeed and keeps query generation focused on what each strategy does best.

**Why this priority**: Intelligent selection prevents unnecessary work and ensures each generated query is tailored to its strategy's strengths (e.g., the FTS query uses plainto_tsquery, the vector query uses cosine distance, the structured query uses WHERE/JOIN/GROUP BY).

**Independent Test**: Can be tested by configuring datasets with varying index profiles (all indexes, FTS-only, none) and verifying that only applicable strategies are dispatched.

**Acceptance Scenarios**:

1. **Given** a dataset with FTS indexes but no vector indexes, **When** a query is submitted, **Then** the system dispatches structured and FTS strategies but not vector similarity.
2. **Given** a dataset with no FTS or vector indexes (B-tree only), **When** a query is submitted, **Then** only the structured SQL strategy is dispatched.
3. **Given** multiple datasets where one has FTS indexes and another does not, **When** a cross-dataset query is submitted, **Then** the FTS strategy targets only the dataset with FTS indexes.

---

### Edge Cases

- What happens when all three strategies return empty results? The system returns a "no results found" response with suggestions, identical to today's behavior.
- What happens when one strategy returns thousands of rows? Each strategy applies its own LIMIT (configurable, default 50) before fusion to prevent memory issues.
- What happens when the user targets datasets with different index profiles? Each strategy is scoped to only the datasets where its required indexes exist. For cross-dataset queries where tables have different column schemas (e.g., FTS on table A's "description" but no "description" column on table B), each strategy's SQL targets only the tables/columns where its indexes exist.
- What happens when two strategies return conflicting orderings? Reciprocal Rank Fusion (RRF) determines final ordering — rows found by multiple strategies accumulate higher RRF scores regardless of individual strategy ordering.
- How are parameterized query values handled for vector queries? The query text is embedded at execution time (existing pattern) and passed as a parameter to the vector similarity query. If embedding generation fails (e.g., OpenAI API error), the vector strategy is treated as failed and the remaining strategies' results are still returned (graceful degradation per FR-012).
- What happens when the user asks an aggregation question (e.g., "what is the average price")? Only the structured SQL strategy is dispatched — FTS and vector return row-level results that cannot be meaningfully fused with an aggregate value.
- What happens when aggregation detection yields a false positive (e.g., "how many categories of wireless chargers" where intent is listing, not counting)? The structured strategy still produces a valid result. The user may rephrase to get multi-strategy results. This is an acceptable trade-off; a future conversational query refinement feature could disambiguate intent.
- What happens when two rows have identical RRF scores? Ties are broken by position in the highest-priority strategy (structured > fulltext > vector). If still tied, original row order within the strategy is preserved.
- What happens when all 3 strategies return their maximum 50 rows each? Up to 150 rows enter fusion. After ctid-based deduplication, the actual count depends on overlap. All fused rows are included in the response (the response generator handles display truncation as needed).
- What happens when index_metadata is stale (indexes recorded as 'created' but actually dropped from PostgreSQL)? The strategy dispatch plan uses the metadata as-is. If the generated SQL references a dropped index, the strategy execution will fail with a PostgreSQL error, triggering graceful degradation (FR-012). The other strategies' results are still returned.
- What happens when two strategies return the same ctid but with different data values for the same column? This should not occur because data tables are immutable after ingestion and strategies execute within the same request. If it does occur (e.g., due to a concurrent VACUUM or system anomaly), the data from the first strategy in priority order (structured > fulltext > vector) is kept.
- What happens when the user has no datasets at all? The system returns the existing "no datasets found" response before reaching the multi-strategy pipeline. This is unchanged from current behavior.
- What happens when the connection pool is exhausted during parallel strategy execution? The `pool.connection()` call blocks until a connection becomes available (within the pool timeout). If the pool timeout expires before a connection is available, the affected strategy fails and graceful degradation (FR-012) applies.

## Requirements

### Functional Requirements

- **FR-001**: System MUST dispatch applicable query strategies in parallel using thread-based concurrency. The three strategy types are: structured (always applicable when B-tree indexes exist), fulltext (applicable when GIN/FTS indexes exist on target columns), and vector (applicable when HNSW/vector indexes exist on target columns). These three are the exhaustive set of strategies; no other strategy types exist.
- **FR-002**: System MUST generate a structured SQL query using B-tree indexes for every non-aggregation query (the structured strategy is always the baseline). For aggregation queries (see FR-019), only the structured strategy is dispatched.
- **FR-003**: System MUST generate a full-text search query using tsvector operators (@@, plainto_tsquery, ts_rank) when FTS indexes exist on columns identified by the hybrid search phase (column discovery results).
- **FR-004**: System MUST generate a vector similarity query using cosine distance (<=> operator) when vector indexes exist on columns identified by the hybrid search phase (column discovery results).
- **FR-005**: System MUST determine applicable strategies by inspecting the `index_metadata` table (from 003-index-aware-sql) for the target datasets before dispatch. A strategy is applicable only when at least one target dataset has the required index capability (`filtering` for structured, `full_text_search` for fulltext, `vector_similarity` for vector) in `created` status.
- **FR-006**: System MUST execute all dispatched strategies concurrently and collect results when all complete or a per-strategy timeout expires. When the user cancels a query, all in-flight strategy threads MUST be signaled to stop via `threading.Event`.
- **FR-007**: System MUST merge results from all strategies into a single composite result set. The merged column set is the union of user data columns across all strategy results, excluding system columns (`ctid`, columns prefixed with `_ts_`, `_emb_`, and computed columns like `rank`, `similarity`, `relevance`). When strategies return different column sets, missing values for a column are set to NULL.
- **FR-008**: System MUST deduplicate rows that appear in multiple strategy results by including PostgreSQL's `ctid` (physical row identifier) in each strategy's SELECT. Rows with matching `ctid` values across strategies are collapsed into a single entry in the fused result. When merging duplicate rows, the data columns from the first strategy (in priority order: structured, fulltext, vector) are kept. If a strategy's result is missing the `ctid` column, that strategy's results are excluded from fusion and treated as a failed strategy (graceful degradation per FR-012).
- **FR-009**: System MUST compute a composite relevance score using Reciprocal Rank Fusion (RRF): for each row, score = sum(1 / (k + rank_in_strategy)) across all strategies that returned it, where k is a constant (default 60) and rank_in_strategy is the 1-indexed position of the row in that strategy's result list. Rows absent from a strategy receive no score contribution from that strategy (they are simply not included in the sum). When two rows have identical RRF scores (tie), they are ordered by the row's position in the highest-priority strategy (structured > fulltext > vector).
- **FR-010**: System MUST order the fused result set by composite relevance score (descending), with ties broken per FR-009.
- **FR-011**: System MUST apply a per-strategy row limit (default 50) before fusion to bound memory usage. The maximum total fused row count after deduplication is bounded by 3 × 50 = 150 rows in the worst case (no overlap). No additional post-fusion limit is applied; the response generator handles display truncation.
- **FR-012**: System MUST complete successfully even if one or more strategies fail — results from successful strategies are still returned (graceful degradation). This includes: strategy SQL execution errors, strategy timeout, missing ctid in results (FR-008), and vector embedding generation failures at execution time.
- **FR-013**: System MUST format the fused result set into a single unified HTML response. The `ctid` column MUST be excluded from user-visible output (it is an internal deduplication key only).
- **FR-014**: System MUST include a strategy attribution summary in the HTML response when multiple strategies contributed results. The attribution is a single line above the data table in the format: "Results from {strategy1} ({N1} rows), {strategy2} ({N2} rows)[, and {strategy3} ({N3} rows)]." where strategy names are human-readable ("structured query", "full-text search", "semantic search").
- **FR-015**: System MUST omit strategy attribution when only one strategy contributed (preserving current single-query UX).
- **FR-016**: System MUST generate all applicable strategy SQL statements in a single LLM call. The prompt instructs the agent to output labeled SQL blocks wrapped in delimiters (`---STRATEGY: {name}---` / `---END STRATEGY---`). The LLM interprets user intent to extract appropriate search terms for FTS and semantic concepts for vector queries. For cross-dataset queries where datasets have different index profiles, the prompt specifies per-strategy which tables and columns are available. If the LLM output is completely unparseable (no valid strategy blocks extracted), the system retries the LLM call once. If the retry also fails, the system falls back to single-strategy structured SQL generation using the existing (pre-feature) prompt.
- **FR-017**: System MUST handle the case where dataset_ids is None (all datasets) by querying index metadata for all user datasets.
- **FR-018**: System MUST log which strategies were dispatched, their individual execution times, and row counts for observability using structured logging (the existing `log_event()` pattern with event name, user, and extras dict). Log events: `strategy_dispatch` (strategies planned), `strategy_execution_complete` (per-strategy result), `fusion_complete` (fused row count, dedup count).
- **FR-019**: System MUST detect aggregation intent and dispatch only the structured SQL strategy for such queries, skipping FTS and vector strategies. Detection uses keyword matching against the query text: presence of "count", "sum", "total", "average", "avg", "minimum", "min", "maximum", "max", "how many", or "what is the total/average/sum" (case-insensitive). This is a heuristic; false positives (e.g., "how many categories of wireless chargers" where user wants a list) are acceptable because the structured strategy still produces a valid result — the user may need to rephrase for multi-strategy results.
- **FR-020**: System MUST gracefully handle malformed LLM output for multi-strategy SQL generation. If a strategy block has invalid delimiters, an unrecognized strategy name, or empty SQL, that specific block is skipped and the remaining valid blocks are processed. If only one valid block is extracted, the system proceeds with single-strategy execution.
- **FR-021**: When only the structured strategy is applicable (no FTS or vector indexes exist), the system MUST bypass the multi-strategy prompt and fusion pipeline entirely, using the existing single-strategy SQL generation flow. This produces a standard result (not wrapped in FusedResult) identical to pre-feature behavior.
- **FR-022**: System MUST store the multi-strategy SQL output (all strategy blocks concatenated with their delimiters) in the existing `generated_sql` field of the Query model for auditability. The `result_count` field reflects the fused (post-deduplication) row count.
- **FR-023**: System MUST report query progress during multi-strategy execution using the existing progress tracking mechanism. Progress messages include: "Generating multi-strategy SQL...", "Executing {N} strategies in parallel...", "Fusing results from {N} strategies...", "Generating response...". Per-strategy completion is not reported individually to avoid UI complexity.

### Non-Functional Requirements

- **NFR-001**: Total query latency (measured as p95 wall-clock time from query submission to HTML response delivery) MUST NOT increase by more than 30% compared to the current single-query approach, measured on the same dataset with the same query. Test conditions: dataset with 10K+ rows, all three index types present, non-aggregation query.
- **NFR-002**: Each individual strategy query MUST respect a per-strategy timeout (default 30 seconds), measured as wall-clock time from SQL dispatch to result retrieval (excluding SQL generation time, which is shared across strategies in the single LLM call). The per-strategy timeout is independent of the overall 300-second query timeout; both are enforced, and the stricter limit applies. When 3 strategies each take up to 30s, the parallel execution still completes within ~30s total wall-clock time (not 90s) because strategies run concurrently.
- **NFR-003**: The system MUST use thread-based parallelism (ThreadPoolExecutor) — no async/await patterns.
- **NFR-004**: The fusion process (RRF scoring + deduplication) MUST operate in memory with bounded allocation. With 3 strategies × 50 rows = 150 input rows maximum, the fusion memory footprint is negligible relative to the overall query processing memory. No streaming or disk-based fusion is required.
- **NFR-005**: The new services (ResultFusionService, StrategyDispatcherService) MUST be stateless and thread-safe. They hold no mutable shared state; all data flows through method parameters and return values. Multiple concurrent queries can safely use the same service instances.

### Key Entities

- **QueryStrategy**: Represents one query approach (structured, full-text, vector). Has a type, applicability check, SQL generator, and result set.
- **StrategyResult**: The output of a single strategy execution — rows, column names, row count, execution time, and strategy type.
- **FusedResult**: The merged output of all strategy results — deduplicated rows with composite relevance scores, strategy attribution metadata, and final ordering.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Queries against datasets with multiple index types return results from all applicable strategies. Measured by: submitting the same query with multi-strategy enabled vs. single-strategy and comparing distinct row counts in the result set. Multi-strategy should return >= the rows of any single strategy alone.
- **SC-002**: Parallel strategy execution completes within 130% of the single-strategy baseline latency (p95), measured on the same dataset with the same query text. Baseline: time for single structured SQL strategy. Test: time for multi-strategy (dispatch + parallel execution + fusion).
- **SC-003**: Users receive a single unified HTML response regardless of how many strategies contributed — the multi-strategy nature is transparent unless the user looks at the attribution summary.
- **SC-004**: When one strategy fails or times out, the user still receives results from the remaining strategies within the overall timeout window.
- **SC-005**: Duplicate rows across strategies are collapsed — the fused result set contains no rows with the same `ctid` value. Verified by checking `len(set(ctids)) == len(ctids)` on the fused result.

## Clarifications

### Session 2026-03-03

- Q: Should each strategy's SQL be generated by a separate LLM call, or a single call producing multiple queries? → A: Single LLM call producing multiple labeled SQL statements (one per applicable strategy). The LLM is needed for all strategies because it must interpret user intent to extract search terms for FTS and semantic concepts for vector queries.
- Q: How should aggregation queries (COUNT, AVG, SUM) be handled when FTS/vector return raw rows? → A: Aggregation queries use structured strategy only — skip FTS/vector when query intent is aggregation. A future conversational query refinement feature (separate spec) could let the LLM ask the user to disambiguate intent.
- Q: What scoring formula should be used for composite relevance in result fusion? → A: Reciprocal Rank Fusion (RRF) with k=60. Score = sum(1/(k + rank)) across strategies. Rank-based, no score normalization needed.
- Q: How should rows be identified for deduplication across strategies when CSV tables lack a primary key? → A: Include PostgreSQL `ctid` in each strategy's SELECT. All strategies query the same underlying table, so `ctid` reliably identifies the same physical row.

## Assumptions

- The existing hybrid search phase (column discovery) continues to run before SQL generation and its results are passed to the multi-strategy SQL generation prompt. This feature changes what happens after column discovery succeeds: instead of generating one SQL query, it generates multiple strategy-specific queries.
- The CrewAI SQL generation agent is invoked once per query and produces multiple labeled SQL statements (one per applicable strategy) in a single LLM call. This keeps API cost constant regardless of how many strategies are dispatched.
- The current 300-second overall query timeout remains unchanged. Individual strategy timeouts (30 seconds each) are a subset of this.
- Index metadata from the 003-index-aware-sql feature (`index_metadata` table, `build_index_context`) is available and up-to-date at query time. **Hard prerequisite**: The `index_metadata` table must exist in the user's schema. If it does not exist (e.g., user schema created before 003 was deployed), the system falls back to single-strategy structured SQL only (no FTS or vector strategies available).
- The existing parameterized query execution pattern (QueryExecutionService) can be reused for each strategy's SQL execution. Each strategy thread acquires its own database connection from the pool and calls `SET search_path TO {username}_schema` independently, which is safe because `SET search_path` is connection-scoped (not session-global).
- Data tables are immutable after CSV ingestion — no UPDATE, DELETE, or VACUUM FULL operations occur between strategy executions within a single query request. This guarantees `ctid` stability for deduplication. If a future feature introduces row-level mutations, the deduplication strategy must be revisited.
- The psycopg connection pool is configured with `max_size >= 5` (minimum 3 for parallel strategy execution + headroom for other concurrent operations). This is a deployment requirement.
- This feature has no transition concerns for in-flight queries at deployment time. Queries already in progress use the existing single-strategy code path. New queries after deployment use the multi-strategy path. No migration or state changes are required.

## Future Considerations

- **Conversational Query Refinement**: A chat-session interface where the LLM can ask the user clarifying questions before generating SQL (e.g., "Did you want a summary or a list of matching rows?"). This would improve result quality for ambiguous queries. Tracked as a separate future feature.
