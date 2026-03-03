# Quickstart: Parallel Query Fusion

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03

## What This Feature Does

When a user asks a question, the system now:

1. **Inspects index metadata** to determine which query strategies are available (B-tree, FTS, vector)
2. **Generates multiple SQL queries** in a single LLM call — one per applicable strategy
3. **Executes all strategies in parallel** using ThreadPoolExecutor
4. **Fuses results** using Reciprocal Rank Fusion (RRF) — deduplicates rows, scores by cross-strategy relevance
5. **Returns a single unified HTML response** with optional strategy attribution

## User-Visible Changes

### Before (current behavior)

User asks: "Find products related to wireless charging"

System generates **one** SQL query:
```sql
SELECT * FROM products_data
WHERE _ts_description @@ plainto_tsquery('english', 'wireless charging')
ORDER BY ts_rank(_ts_description, plainto_tsquery('english', 'wireless charging')) DESC
LIMIT 100
```

Only uses one search strategy. May miss rows that are semantically related but don't contain exact keywords.

### After (with this feature)

User asks: "Find products related to wireless charging"

System generates **three** SQL queries in parallel:

**Structured:**
```sql
SELECT ctid, * FROM products_data
WHERE category ILIKE '%wireless%' OR name ILIKE '%charging%'
ORDER BY name LIMIT 50
```

**Full-text search:**
```sql
SELECT ctid, *, ts_rank(_ts_description, plainto_tsquery('english', 'wireless charging')) AS rank
FROM products_data
WHERE _ts_description @@ plainto_tsquery('english', 'wireless charging')
ORDER BY rank DESC LIMIT 50
```

**Vector similarity:**
```sql
SELECT ctid, *, 1 - (_emb_description <=> %s::vector) AS similarity
FROM products_data
ORDER BY _emb_description <=> %s::vector LIMIT 50
```

Results are fused: rows found by multiple strategies get boosted scores. The user sees a single HTML table with the most relevant rows first, plus a brief note: "Results from structured query (12 rows), full-text search (18 rows), and semantic search (15 rows)."

### Aggregation Queries (unchanged behavior)

User asks: "What is the average price of products?"

System detects aggregation intent and dispatches **only** the structured strategy:
```sql
SELECT AVG(price) FROM products_data
```

No FTS or vector strategies — they return row-level results that can't be fused with aggregates.

## Developer Workflow

### Running Tests

```bash
# Unit tests for fusion models
pytest tests/unit/models/test_fusion_models.py -v

# Unit tests for result fusion service
pytest tests/unit/services/test_result_fusion.py -v

# Unit tests for strategy dispatcher
pytest tests/unit/services/test_strategy_dispatcher.py -v

# Integration tests (requires PostgreSQL + pgvector running)
pytest tests/integration/test_parallel_query.py -v

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
| `backend/src/models/fusion.py` | NEW — Pydantic models: StrategyType, StrategySQL, StrategyResult, FusedResult, FusedRow |
| `backend/src/services/strategy_dispatcher.py` | NEW — Strategy selection based on index metadata |
| `backend/src/services/result_fusion.py` | NEW — RRF scoring, ctid dedup, result merging |
| `backend/src/services/query_execution.py` | MODIFIED — Added execute_strategies_parallel() |
| `backend/src/services/text_to_sql.py` | MODIFIED — Multi-strategy SQL generation orchestration |
| `backend/src/crew/tasks.py` | MODIFIED — Multi-strategy prompt with labeled SQL blocks |
| `backend/src/api/queries.py` | MODIFIED — Integrated multi-strategy flow |
| `backend/src/services/response_generator.py` | MODIFIED — Accepts FusedResult with attribution |

### Configuration

| Setting | Default | Description |
|---|---|---|
| RRF k constant | 60 | Controls rank sensitivity in fusion scoring |
| Per-strategy row limit | 50 | Maximum rows returned by each strategy before fusion |
| Per-strategy timeout | 30 seconds | Timeout for individual strategy execution |
| ThreadPoolExecutor workers | 3 | One worker per strategy (structured, FTS, vector) |

### Verifying Multi-Strategy Execution

After submitting a query, check the query's agent_logs or progress_timeline for strategy execution details:

```python
# In the response metadata (logged per FR-018):
{
    "strategies_dispatched": ["structured", "fulltext", "vector"],
    "strategy_results": {
        "structured": {"row_count": 12, "execution_time_ms": 45, "succeeded": True},
        "fulltext": {"row_count": 18, "execution_time_ms": 62, "succeeded": True},
        "vector": {"row_count": 15, "execution_time_ms": 180, "succeeded": True},
    },
    "fused_result": {"total_rows": 28, "deduplicated_from": 45},
}
```
