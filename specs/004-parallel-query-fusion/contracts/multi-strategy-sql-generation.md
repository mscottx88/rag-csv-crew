# Contract: Multi-Strategy SQL Generation

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03
**Module**: `backend/src/crew/tasks.py`, `backend/src/services/text_to_sql.py`

## Modified Function: create_sql_generation_task

### Current Signature (from 003-index-aware-sql)

```python
def create_sql_generation_task(
    agent: Agent,
    query_text: str,
    dataset_ids: list[UUID] | None,
    cross_references: list[dict[str, Any]] | None = None,
    search_results: dict[str, Any] | None = None,
    schema_context: str | None = None,
    index_context: str | None = None,
) -> Task:
```

### New Parameter

```python
def create_sql_generation_task(
    agent: Agent,
    query_text: str,
    dataset_ids: list[UUID] | None,
    cross_references: list[dict[str, Any]] | None = None,
    search_results: dict[str, Any] | None = None,
    schema_context: str | None = None,
    index_context: str | None = None,
    strategy_dispatch: StrategyDispatchPlan | None = None,  # NEW
) -> Task:
```

### Prompt Modification

When `strategy_dispatch` is provided with more than one strategy, the task description is augmented with multi-strategy instructions:

```text
MULTI-STRATEGY SQL GENERATION
================================================================================
Generate SEPARATE SQL queries for each of the following strategies.
Each query MUST include 'ctid' as the first column in the SELECT list.
Each query MUST end with LIMIT 50.

Wrap each query in the following delimiters:

---STRATEGY: structured---
<your structured SQL here>
---END STRATEGY---

---STRATEGY: fulltext---
<your full-text search SQL here>
---END STRATEGY---

---STRATEGY: vector---
<your vector similarity SQL here>
---END STRATEGY---

STRATEGY GUIDELINES:
- structured: Use standard WHERE, JOIN, GROUP BY, ORDER BY with B-tree indexes.
  Always include ctid as the first SELECT column.
- fulltext: Use plainto_tsquery, @@, ts_rank operators on _ts_ columns.
  Always include ctid as the first SELECT column.
  The search terms should reflect the user's query intent.
- vector: Use <=> cosine distance operator on _emb_ columns with %s::vector placeholder.
  Always include ctid as the first SELECT column.
  The query concept for embedding should reflect the user's semantic intent.

If the user's question is an AGGREGATION (COUNT, SUM, AVG, MIN, MAX, GROUP BY),
generate ONLY the structured strategy. Do NOT generate fulltext or vector strategies
for aggregation queries.
================================================================================
```

### Output Parsing

The `TextToSQLService` parses the multi-strategy output using regex:

```python
import re

_STRATEGY_PATTERN: re.Pattern[str] = re.compile(
    r"---STRATEGY:\s*(\w+)\s*---\s*\n(.*?)\n\s*---END STRATEGY---",
    re.DOTALL,
)

def parse_multi_strategy_sql(raw_output: str) -> list[StrategySQL]:
    """Parse labeled SQL blocks from LLM output."""
    matches: list[tuple[str, str]] = _STRATEGY_PATTERN.findall(raw_output)
    strategies: list[StrategySQL] = []
    for strategy_name, sql_block in matches:
        cleaned_sql: str = _clean_sql(sql_block.strip())
        params: list[Any] = _extract_query_parameters(cleaned_sql, query_text)
        strategies.append(StrategySQL(
            strategy_type=StrategyType(strategy_name),
            sql=cleaned_sql,
            parameters=params,
        ))
    return strategies
```

### Malformed Output Handling (FR-020)

When parsing produces partial results:
- **Invalid strategy name**: Block is skipped (e.g., `---STRATEGY: unknown---` is ignored).
- **Empty SQL in block**: Block is skipped.
- **Missing delimiters**: Only properly delimited blocks are extracted; surrounding text is ignored.
- **Fewer blocks than requested**: Proceed with whatever valid blocks were extracted.
- **Zero valid blocks**: Trigger retry (see below).

### Retry and Fallback (FR-016)

If the first LLM call produces zero parseable strategy blocks:
1. **Retry once** with the same prompt.
2. If the retry also produces zero valid blocks, **fall back** to the existing single-strategy SQL generation (pre-feature prompt) for structured SQL only.
3. Log the failure for observability (FR-018).

### Single-Strategy Fallback (FR-021)

When `strategy_dispatch` is None or contains only one strategy (structured), the current single-strategy prompt and output format is preserved. No delimiter parsing is needed — the output is treated as a single SQL statement exactly as today. The multi-strategy prompt and fusion pipeline are bypassed entirely.

## New Function: TextToSQLService.generate_multi_strategy_sql

### Signature

```python
def generate_multi_strategy_sql(
    self,
    query_text: str,
    username: str,
    dataset_ids: list[UUID] | None,
    search_results: dict[str, Any],
    strategy_dispatch: StrategyDispatchPlan,
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> list[StrategySQL]:
    """Generate SQL for multiple query strategies in a single LLM call.

    Args:
        query_text: The user's natural language query.
        username: For schema isolation.
        dataset_ids: Target datasets (None = all user datasets).
        search_results: Column discovery results from hybrid search.
        strategy_dispatch: Which strategies to generate SQL for.
        progress_callback: Optional progress reporting callback.

    Returns:
        List of StrategySQL objects, one per generated strategy.
        May be fewer than requested if the LLM omits a strategy
        or if parsing fails for a block (graceful degradation).
    """
```

### Caller: queries.py Integration

```python
# In _execute_sql_query or equivalent:
dispatch_plan: StrategyDispatchPlan = strategy_dispatcher.plan_strategies(
    username=username,
    dataset_ids=dataset_ids,
    pool=pool,
)

if len(dispatch_plan.strategies) > 1:
    strategy_sqls: list[StrategySQL] = text_to_sql.generate_multi_strategy_sql(
        query_text=query_text,
        username=username,
        dataset_ids=dataset_ids,
        search_results=search_results,
        strategy_dispatch=dispatch_plan,
        progress_callback=tracker.update,
    )
    # Execute all strategies in parallel
    strategy_results: list[StrategyResult] = query_execution.execute_strategies_parallel(
        strategies=strategy_sqls,
        username=username,
        timeout_seconds=30,
    )
    # Fuse results
    fused: FusedResult = result_fusion.fuse(strategy_results)
else:
    # Single-strategy path (existing flow)
    ...
```
