# Research: Parallel Query Fusion

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03
**Purpose**: Resolve technical unknowns and document design decisions for implementation

## R1: Current SQL Generation Pipeline Architecture

**Decision**: Modify the existing single-strategy SQL generation flow to produce multiple labeled SQL blocks in a single LLM call, then dispatch each strategy's SQL for parallel execution.

**Rationale**: The current pipeline follows this flow:
1. `POST /queries` → spawns background thread (`_process_query_background`)
2. Hybrid search (3-way parallel in `HybridSearchService.search()` via ThreadPoolExecutor)
3. Confidence evaluation + data value search boost
4. SQL generation via CrewAI (`TextToSQLService.generate_sql()`) — single SQL output
5. Query execution (`QueryExecutionService.execute_query()`) — single SQL with timeout
6. HTML response generation via CrewAI (`ResponseGenerator.generate_html_response()`)

The modification point is between steps 3 and 6. Instead of generating one SQL statement, the CrewAI task will produce multiple labeled SQL blocks. Each block is executed in parallel, and results are fused before HTML generation.

**Alternatives Considered**:
- Three separate LLM calls (one per strategy): Rejected — triples API cost with no quality benefit. The LLM can reason about all strategies at once, and a single call ensures consistent interpretation of user intent across strategies.
- Sequential strategy execution: Rejected — adds latency proportional to the number of strategies. Parallel execution via ThreadPoolExecutor keeps wall-clock time near the single-strategy baseline.

**Key Interfaces to Modify**:

| File | Current Role | Modification |
|---|---|---|
| `backend/src/crew/tasks.py` | Generates single SQL via CrewAI task | New prompt producing labeled multi-strategy SQL blocks |
| `backend/src/services/text_to_sql.py` | Orchestrates single SQL generation | Parse multi-strategy output, return per-strategy SQL |
| `backend/src/services/query_execution.py` | Executes single SQL with timeout | New `execute_strategies_parallel()` method |
| `backend/src/api/queries.py` | Single-strategy flow in `_execute_sql_query()` | Route to multi-strategy flow when applicable |
| `backend/src/services/response_generator.py` | Generates HTML from single result set | Accept fused result set with strategy attribution |

## R2: Reciprocal Rank Fusion (RRF) Algorithm

**Decision**: Use RRF with k=60 for composite scoring. Score formula: `score(d) = sum(1/(k + rank_i(d)))` where `rank_i(d)` is the 1-indexed position of document `d` in strategy `i`'s result list.

**Rationale**: RRF (Cormack, Clarke & Butt, 2009) is a rank-based fusion method that:
- Requires no score normalization — each strategy can use a different scale (SQL row order, ts_rank float, cosine distance float)
- Is robust to outlier scores — only the position matters
- Penalizes low-ranked items naturally — 1/(60+1) = 0.0164 for rank 1, 1/(60+50) = 0.0091 for rank 50
- Rewards consensus — a row found by 3 strategies at rank 10 each gets 3 × 1/70 = 0.0429, outranking a row found by 1 strategy at rank 1 (0.0164)

**Implementation Pattern**:
```python
def compute_rrf_scores(
    strategy_results: dict[str, list[dict[str, Any]]],
    k: int = 60,
) -> dict[str, float]:
    """Compute RRF scores for all rows across strategies."""
    scores: dict[str, float] = {}  # ctid → RRF score
    for strategy_name, rows in strategy_results.items():
        for rank_zero, row in enumerate(rows):
            ctid: str = row["ctid"]
            rank: int = rank_zero + 1  # 1-indexed
            scores[ctid] = scores.get(ctid, 0.0) + 1.0 / (k + rank)
    return scores
```

**k=60 Choice**: The original RRF paper uses k=60 as the default. Smaller k (e.g., 10) amplifies rank differences at the top; larger k (e.g., 100) smooths them. k=60 provides a good balance between rewarding high ranks and accumulating cross-strategy evidence.

**Alternatives Considered**:
- Weighted score normalization (min-max per strategy, then weighted sum): Rejected — requires knowing score ranges upfront, sensitive to outliers, and the three strategies use incompatible scales (ordinal position vs. ts_rank float vs. cosine distance).
- CombSUM/CombMNZ: Rejected — requires score normalization. CombMNZ (multiply by count of strategies) is appealing but still needs normalized scores.

## R3: PostgreSQL ctid for Row Deduplication

**Decision**: Include `ctid` (PostgreSQL physical tuple identifier) in every strategy's SELECT list. Use `ctid` as the deduplication key when fusing results across strategies.

**Rationale**: CSV-ingested tables have no primary key column. The `_row_id` column (added during ingestion) is a serial integer but is not guaranteed to appear in all query projections. `ctid` is a system column always available on every table, representing the physical (block, tuple) position of the row. When all strategies query the same table in the same transaction (or with no concurrent writes), `ctid` uniquely identifies each row.

**Stability Guarantee**: `ctid` is stable when:
- No `VACUUM FULL` or `CLUSTER` runs between queries (our context: all strategies execute within seconds of each other)
- No `UPDATE` or `DELETE` modifies the row between queries (our context: data tables are read-only after ingestion)
- The table is not partitioned (our context: data tables are simple heap tables)

All three conditions hold for our use case: data tables are immutable after CSV ingestion, and strategy queries run in rapid succession within the same request.

**ctid Format**: `(block_number, tuple_index)` — e.g., `(0,1)`, `(0,2)`, `(5,12)`. In Python, PostgreSQL returns `ctid` as a string, which can be used directly as a dictionary key for deduplication.

**Implementation Note**: The SQL prompt must instruct the LLM to include `ctid` in every SELECT. For deduplication, the fusion service groups rows by `ctid` string value and keeps the first occurrence's data columns while accumulating RRF scores from all occurrences.

**Alternatives Considered**:
- Use `_row_id` for deduplication: Rejected — requires every strategy's SQL to include `_row_id` in its SELECT, which adds a constraint on SQL generation. `ctid` is a system column always present without explicit inclusion in the column list. **Update**: Actually `ctid` also needs explicit inclusion in SELECT. Using `_row_id` would also work, but `ctid` was chosen per spec clarification to handle edge cases where `_row_id` might not be selected.
- Hash all non-system columns for identity: Rejected — expensive for wide tables and fragile if column types don't hash cleanly.

## R4: Multi-Strategy SQL Prompt Design

**Decision**: The CrewAI SQL generation task prompt will instruct the LLM to produce multiple labeled SQL blocks, one per applicable strategy, wrapped in delimiters for reliable parsing.

**Rationale**: A single LLM call is more cost-effective and produces more consistent results than multiple calls. The prompt structure gives the LLM clear instructions about which strategies are available (based on index metadata) and what query pattern each strategy should use.

**Prompt Output Format**:
```text
---STRATEGY: structured---
SELECT ctid, col1, col2 FROM table WHERE condition ORDER BY col1 LIMIT 50
---END STRATEGY---

---STRATEGY: fulltext---
SELECT ctid, col1, col2, ts_rank(_ts_col, plainto_tsquery('english', %s)) AS rank
FROM table WHERE _ts_col @@ plainto_tsquery('english', %s) ORDER BY rank DESC LIMIT 50
---END STRATEGY---

---STRATEGY: vector---
SELECT ctid, col1, col2, 1 - (_emb_col <=> %s::vector) AS similarity
FROM table ORDER BY _emb_col <=> %s::vector LIMIT 50
---END STRATEGY---
```

**Parsing Strategy**: Use regex to extract blocks between `---STRATEGY: {name}---` and `---END STRATEGY---`. Each block is cleaned (markdown removal) and parameter-extracted independently. If a block is malformed, that strategy is skipped (graceful degradation per FR-012).

**Aggregation Detection**: The prompt includes instructions to detect aggregation intent (COUNT, SUM, AVG, MIN, MAX, GROUP BY). When detected, only the `structured` block is produced and the others are omitted. This prevents meaningless fusion of aggregate values with row-level results.

## R5: Parallel Strategy Execution Pattern

**Decision**: Use `ThreadPoolExecutor` with `concurrent.futures.wait()` and per-strategy timeouts to execute all strategy SQL statements in parallel. Model after the existing `HybridSearchService.search()` pattern.

**Rationale**: The existing codebase already uses ThreadPoolExecutor for parallel execution (hybrid search with 3 workers, query execution with 1 worker + timeout). The parallel strategy execution follows the same constitutional pattern.

**Implementation Pattern**:
```python
from concurrent.futures import ThreadPoolExecutor, Future, wait, FIRST_EXCEPTION

with ThreadPoolExecutor(max_workers=len(strategies)) as executor:
    futures: dict[str, Future[StrategyResult]] = {
        strategy.name: executor.submit(
            execute_strategy, strategy, username, timeout_seconds, cancel_event
        )
        for strategy in strategies
    }

    done, not_done = wait(
        futures.values(),
        timeout=timeout_seconds,
        return_when=ALL_COMPLETED,
    )

    results: list[StrategyResult] = []
    for name, future in futures.items():
        if future.done() and not future.cancelled():
            try:
                results.append(future.result())
            except Exception:
                logger.warning("Strategy %s failed", name)
```

**Graceful Degradation**: If one strategy times out or raises an exception, the remaining strategies' results are still collected and fused. The system logs which strategies failed for observability.

## R6: Strategy Selection Logic

**Decision**: Before generating SQL, query `index_metadata` for all target datasets to determine which strategies are applicable. A strategy is dispatched only if the required indexes exist.

**Strategy Applicability Rules**:

| Strategy | Required Index | Required Capability |
|---|---|---|
| Structured (always) | B-tree | `filtering` |
| Full-text search | GIN | `full_text_search` |
| Vector similarity | HNSW | `vector_similarity` |

**Rationale**: The `index_metadata` table (from 003-index-aware-sql) already records every index with its capability. The selection logic queries this table to determine which strategies can produce results for the target datasets, avoiding wasted LLM reasoning and SQL execution for strategies that would fail.

**Cross-Dataset Handling**: When multiple datasets are targeted and they have different index profiles, each strategy is scoped to the datasets where its required indexes exist. The LLM prompt specifies per-strategy which tables/columns are available.

## R7: HTML Response Enhancement

**Decision**: When multiple strategies contribute results, add a brief attribution summary to the HTML response. When only one strategy contributes, the response looks identical to today's output.

**Rationale**: Users should see a single unified result table, not separate tables per strategy. The attribution summary (e.g., "Results found via structured query (23 rows), full-text search (18 rows), and semantic search (12 rows)") provides transparency without cluttering the output.

**Implementation**: The `ResponseGenerator.generate_html_response()` receives the fused result set along with strategy metadata. The CrewAI Result Analyst agent's prompt is enhanced to include the attribution data, and it generates the HTML accordingly.

## R8: Existing Concurrency Model Compatibility

**Decision**: All new code uses synchronous patterns with `ThreadPoolExecutor`, `threading.Event`, and `threading.Lock`. No async/await patterns.

**Rationale**: Constitutional requirement (Principle VI). The existing codebase already demonstrates the ThreadPoolExecutor pattern in `HybridSearchService.search()` (3 workers) and `QueryExecutionService.execute_query()` (1 worker + timeout + cancellation). The new parallel strategy execution follows these established patterns exactly.

**Connection Pool Considerations**: Each strategy execution needs its own database connection. The existing `psycopg_pool.ConnectionPool` handles this — each `with pool.connection() as conn:` acquires a separate connection from the pool. With 3 strategies executing in parallel, the pool needs at least 3 available connections. The current pool configuration (min_size=2, max_size=10) is sufficient.
