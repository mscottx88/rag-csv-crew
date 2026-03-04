# Contract: Parallel Query Execution

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03
**Module**: `backend/src/services/query_execution.py`

## Modified Class: QueryExecutionService

### New Method: execute_strategies_parallel

```python
def execute_strategies_parallel(
    self,
    strategies: list[StrategySQL],
    username: str,
    timeout_seconds: int = 30,
    cancel_event: Event | None = None,
) -> list[StrategyResult]:
    """Execute multiple strategy SQL queries in parallel.

    Each strategy is executed in its own thread with its own database
    connection (acquired from the connection pool). A per-strategy
    timeout is enforced via concurrent.futures.wait().

    Args:
        strategies: List of StrategySQL objects to execute.
        username: For schema isolation (SET search_path).
        timeout_seconds: Per-strategy timeout in seconds (FR-025, NFR-002).
        cancel_event: Optional event for external cancellation.

    Returns:
        List of StrategyResult objects, one per input strategy.
        Failed strategies have error field set; succeeded strategies
        have rows, columns, and row_count populated.
        Order matches input strategies list.
    """
```

### Implementation Pattern

```python
from concurrent.futures import ThreadPoolExecutor, Future, wait, ALL_COMPLETED

def execute_strategies_parallel(
    self,
    strategies: list[StrategySQL],
    username: str,
    timeout_seconds: int = 30,
    cancel_event: Event | None = None,
) -> list[StrategyResult]:
    """Execute multiple strategy SQL queries in parallel."""
    if not strategies:
        return []

    with ThreadPoolExecutor(max_workers=len(strategies)) as executor:
        futures: dict[StrategyType, Future[StrategyResult]] = {}
        for strategy in strategies:
            future: Future[StrategyResult] = executor.submit(
                self._execute_single_strategy,
                strategy=strategy,
                username=username,
                timeout_seconds=timeout_seconds,
                cancel_event=cancel_event,
            )
            futures[strategy.strategy_type] = future

        done, not_done = wait(
            futures.values(),
            timeout=timeout_seconds + 5,  # grace period
            return_when=ALL_COMPLETED,
        )

    results: list[StrategyResult] = []
    for strategy in strategies:
        future = futures[strategy.strategy_type]
        if future.done() and not future.cancelled():
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(StrategyResult(
                    strategy_type=strategy.strategy_type,
                    error=str(exc),
                ))
        else:
            results.append(StrategyResult(
                strategy_type=strategy.strategy_type,
                error="Strategy timed out",
            ))

    return results
```

### Internal Method: _execute_single_strategy

```python
def _execute_single_strategy(
    self,
    strategy: StrategySQL,
    username: str,
    timeout_seconds: int,
    cancel_event: Event | None,
) -> StrategyResult:
    """Execute a single strategy's SQL with timeout and cancellation.

    Reuses the existing execute_query() logic:
    1. Acquire connection from pool
    2. SET search_path TO {username}_schema
    3. Execute SQL with parameters
    4. Return results as StrategyResult

    For vector strategies, detects %s::vector placeholder and generates
    embedding at execution time using VectorSearchService.
    """
```

### Existing Method: execute_query (unchanged)

The existing `execute_query()` method continues to work for the single-strategy path. The new `execute_strategies_parallel()` method is additive.

### Connection Pool Considerations

Each parallel strategy execution acquires its own connection from the `psycopg_pool.ConnectionPool`. With up to 3 strategies running in parallel, the pool needs at least 3 available connections. The current pool configuration (min_size=2, max_size=10) is sufficient. If the pool is temporarily exhausted, `pool.connection()` will block until a connection becomes available (within pool timeout).

### Vector Parameter Resolution

When a strategy's SQL contains `%s::vector`, the execution layer must:

1. Detect the `::vector` cast in the SQL
2. Call `VectorSearchService.generate_embedding(query_text)` to produce the embedding vector
3. Replace the `%s` parameter with the embedding value

This follows the existing pattern for single-strategy vector queries. Each thread resolves its own vector parameter independently.

### Observability (FR-018)

Each `StrategyResult` includes `execution_time_ms`. The caller logs:

```python
for result in strategy_results:
    log_event(
        logger=logger,
        level="info",
        event="strategy_execution_complete",
        user=username,
        extra={
            "strategy": result.strategy_type,
            "execution_time_ms": result.execution_time_ms,
            "row_count": result.row_count,
            "succeeded": result.succeeded,
            "error": result.error,
        },
    )
```
