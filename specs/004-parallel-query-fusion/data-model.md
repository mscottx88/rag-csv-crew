# Data Model: Parallel Query Fusion

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03

## New Entities

This feature introduces no new database tables. All new entities are runtime Pydantic models used during query processing. The existing `index_metadata` table (from 003-index-aware-sql) is read at query time to determine strategy applicability.

### Pydantic Models

#### StrategyType (Enum)

```python
class StrategyType(StrEnum):
    """Query strategy types for parallel dispatch."""
    STRUCTURED = "structured"
    FULLTEXT = "fulltext"
    VECTOR = "vector"
```

#### StrategySQL

Represents a single strategy's generated SQL and parameters, extracted from the multi-strategy LLM output. Validates non-emptiness of SQL only; SQL syntax validation is deferred to PostgreSQL at execution time (invalid SQL triggers graceful degradation per FR-012).

```python
class StrategySQL(BaseModel):
    """SQL generated for a single query strategy."""
    strategy_type: StrategyType
    sql: str = Field(..., min_length=1, description="The SQL query string with %s placeholders (syntax validated at execution)")
    parameters: list[Any] = Field(default_factory=list, description="Query parameters for %s placeholders")

    model_config = ConfigDict(frozen=True)
```

#### StrategyResult

The output of executing a single strategy's SQL.

```python
class StrategyResult(BaseModel):
    """Result from executing a single query strategy."""
    strategy_type: StrategyType
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    error: str | None = Field(default=None, description="Error message if strategy failed")

    model_config = ConfigDict(from_attributes=True)

    @property
    def succeeded(self) -> bool:
        """Whether the strategy executed successfully."""
        return self.error is None
```

#### StrategyAttribution

Metadata about a single strategy's contribution to the fused result.

```python
class StrategyAttribution(BaseModel):
    """Metadata about a strategy's contribution to the fused result."""
    strategy_type: StrategyType
    row_count: int = Field(ge=0)
    execution_time_ms: float = Field(ge=0.0)
    succeeded: bool

    model_config = ConfigDict(frozen=True)
```

#### FusedRow

A single row in the fused result set, with RRF score and source strategy tracking. When a row (same ctid) appears in multiple strategies, the `data` columns are taken from the first strategy in priority order: structured > fulltext > vector. The `ctid` field is for internal deduplication only and MUST be excluded from user-visible output (FR-013).

```python
class FusedRow(BaseModel):
    """A single row in the fused result set."""
    ctid: str = Field(..., description="PostgreSQL physical tuple identifier (internal, not user-visible)")
    data: dict[str, Any] = Field(..., description="Column name → value mapping (user data columns only, excluding _ts_/_emb_/ctid/rank/similarity)")
    rrf_score: float = Field(ge=0.0, description="Reciprocal Rank Fusion composite score")
    source_strategies: list[StrategyType] = Field(
        ..., min_length=1, description="Which strategies found this row"
    )

    model_config = ConfigDict(frozen=True)
```

#### FusedResult

The merged output of all strategy results. `total_row_count` is always equal to `len(rows)` — no post-fusion filtering is applied.

```python
class FusedResult(BaseModel):
    """Merged result from all query strategies."""
    rows: list[FusedRow] = Field(default_factory=list, description="Fused rows ordered by RRF score desc")
    columns: list[str] = Field(default_factory=list, description="Union of user data column names across strategies (excludes ctid, _ts_*, _emb_*, rank, similarity)")
    total_row_count: int = Field(default=0, ge=0, description="Number of unique rows after dedup (always == len(rows))")
    attributions: list[StrategyAttribution] = Field(
        default_factory=list, description="Per-strategy contribution metadata"
    )
    rrf_k: int = Field(default=60, description="RRF constant used for scoring")

    model_config = ConfigDict(from_attributes=True)

    @property
    def strategy_count(self) -> int:
        """Number of strategies that contributed results."""
        return sum(1 for a in self.attributions if a.succeeded and a.row_count > 0)

    @property
    def is_multi_strategy(self) -> bool:
        """Whether multiple strategies contributed results."""
        return self.strategy_count > 1
```

#### StrategyDispatchPlan

Describes which strategies to dispatch for a query, based on index availability. The `strategies` list always contains `STRUCTURED` as the first element (FR-002 baseline guarantee). Additional strategies (FULLTEXT, VECTOR) are appended based on index availability.

```python
class StrategyDispatchPlan(BaseModel):
    """Plan for which strategies to dispatch based on index availability."""
    strategies: list[StrategyType] = Field(..., min_length=1)
    is_aggregation: bool = Field(default=False, description="Whether aggregation intent was detected")
    available_indexes: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Per-table mapping of available index capabilities"
    )

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_structured_always_first(self) -> "StrategyDispatchPlan":
        """Ensure STRUCTURED is always present and first."""
        if not self.strategies or self.strategies[0] != StrategyType.STRUCTURED:
            raise ValueError("STRUCTURED must be the first strategy (FR-002)")
        return self
```

## Field Definitions Summary

### StrategyResult Fields

| Field | Type | Constraints | Description |
|---|---|---|---|
| strategy_type | StrategyType | required | Which strategy produced this result |
| rows | list[dict[str, Any]] | default [] | Row data including ctid |
| columns | list[str] | default [] | Column names in the result set |
| row_count | int | >= 0 | Number of rows returned |
| execution_time_ms | float | >= 0.0 | Wall-clock execution time |
| error | str \| None | nullable | Error message if strategy failed |

### FusedResult Fields

| Field | Type | Constraints | Description |
|---|---|---|---|
| rows | list[FusedRow] | default [] | Deduplicated rows ordered by RRF score |
| columns | list[str] | default [] | Union of all strategy column names |
| total_row_count | int | >= 0 | Count of unique rows after dedup |
| attributions | list[StrategyAttribution] | default [] | Per-strategy metadata |
| rrf_k | int | default 60 | RRF constant k |

### FusedRow Fields

| Field | Type | Constraints | Description |
|---|---|---|---|
| ctid | str | required | PostgreSQL tuple ID for dedup |
| data | dict[str, Any] | required | Column → value mapping |
| rrf_score | float | >= 0.0 | Composite RRF score |
| source_strategies | list[StrategyType] | min 1 | Strategies that returned this row |

## Relationships

```text
StrategyDispatchPlan
    │
    │ determines which strategies to generate SQL for
    │
    ▼
StrategySQL (1 per dispatched strategy)
    │
    │ each SQL executed in parallel
    │
    ▼
StrategyResult (1 per executed strategy)
    │
    │ all results fused via RRF
    │
    ▼
FusedResult
    ├── FusedRow[] (deduplicated, scored, ordered)
    └── StrategyAttribution[] (per-strategy metadata)
```

## Data Flow

```text
Query Request
    │
    ▼
Index Metadata Query (existing index_metadata table)
    │
    ▼
StrategyDispatchPlan (which strategies are applicable)
    │
    ▼
CrewAI SQL Generation (single LLM call)
    │
    ▼
list[StrategySQL] (parsed from labeled output blocks)
    │
    ▼
Parallel Execution (ThreadPoolExecutor)
    │
    ▼
list[StrategyResult] (one per strategy)
    │
    ▼
Result Fusion (RRF scoring + ctid dedup)
    │
    ▼
FusedResult (unified, scored, attributed)
    │
    ▼
HTML Response Generation (existing ResponseGenerator)
```

## Existing Entities Used (Not Modified)

- **index_metadata** (from 003): Read at query time to determine strategy applicability. Fields used: `dataset_id`, `capability`, `status`, `generated_column_name`.
- **DataColumnIndexProfile** (from 003): Used by `build_index_context()` to determine FTS and vector availability per column.
- **Query** / **Response** models: Existing models store query results. The `generated_sql` field will store the multi-strategy SQL (all blocks concatenated). The `result_count` field reflects the fused row count.
