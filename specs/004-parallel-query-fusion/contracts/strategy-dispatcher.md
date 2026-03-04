# Contract: Strategy Dispatcher Service

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03
**Module**: `backend/src/services/strategy_dispatcher.py`

## New Class: StrategyDispatcherService

### Constructor

```python
class StrategyDispatcherService:
    """Determines which query strategies are applicable based on index metadata."""

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize with connection pool for index metadata queries."""
```

### Method: plan_strategies

```python
def plan_strategies(
    self,
    username: str,
    dataset_ids: list[UUID] | None,
    is_aggregation: bool = False,
) -> StrategyDispatchPlan:
    """Determine which strategies to dispatch based on index availability.

    Args:
        username: For schema-isolated index metadata queries.
        dataset_ids: Target datasets. None = all user datasets.
        is_aggregation: Whether the query has aggregation intent.

    Returns:
        StrategyDispatchPlan with applicable strategies.

    Strategy selection rules:
        - structured: ALWAYS included (B-tree indexes always exist)
        - fulltext: Included when any target dataset has `full_text_search` capability
        - vector: Included when any target dataset has `vector_similarity` capability
        - If is_aggregation=True: Only structured is included (FR-019)
    """
```

### Method: detect_aggregation_intent

```python
@staticmethod
def detect_aggregation_intent(query_text: str) -> bool:
    """Detect whether the user's query implies aggregation.

    Looks for keywords: count, sum, average, avg, total, minimum, min,
    maximum, max, how many, what is the total, what is the average.

    Args:
        query_text: The user's natural language query.

    Returns:
        True if aggregation intent is detected.
    """
```

### Implementation Notes

Index metadata is queried using the existing `index_metadata` table (from 003-index-aware-sql):

```python
with self._pool.connection() as conn:
    with conn.cursor() as cur:
        if dataset_ids is not None:
            cur.execute(
                sql.SQL(
                    "SELECT DISTINCT capability FROM {schema}.index_metadata "
                    "WHERE dataset_id = ANY(%s) AND status = 'created'"
                ).format(schema=sql.Identifier(f"{username}_schema")),
                (list(dataset_ids),),
            )
        else:
            cur.execute(
                sql.SQL(
                    "SELECT DISTINCT capability FROM {schema}.index_metadata "
                    "WHERE status = 'created'"
                ).format(schema=sql.Identifier(f"{username}_schema")),
            )
        capabilities: set[str] = {row[0] for row in cur.fetchall()}
```

### Return Value Examples

**All indexes available, non-aggregation query:**
```python
StrategyDispatchPlan(
    strategies=[StrategyType.STRUCTURED, StrategyType.FULLTEXT, StrategyType.VECTOR],
    is_aggregation=False,
    available_indexes={"products_data": ["filtering", "full_text_search", "vector_similarity"]},
)
```

**Only B-tree indexes, non-aggregation query:**
```python
StrategyDispatchPlan(
    strategies=[StrategyType.STRUCTURED],
    is_aggregation=False,
    available_indexes={"products_data": ["filtering"]},
)
```

**All indexes available, aggregation query:**
```python
StrategyDispatchPlan(
    strategies=[StrategyType.STRUCTURED],
    is_aggregation=True,
    available_indexes={"products_data": ["filtering", "full_text_search", "vector_similarity"]},
)
```
