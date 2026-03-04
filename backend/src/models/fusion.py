"""Fusion models for parallel query strategy dispatch and result merging.

Defines Pydantic models for multi-strategy query execution:
- StrategyType: Enum for query strategy types
- StrategySQL: Generated SQL for a single strategy
- StrategyResult: Execution result from a single strategy
- StrategyAttribution: Per-strategy contribution metadata
- FusedRow: Single row in fused result set with RRF score
- FusedResult: Merged result from all strategies
- StrategyDispatchPlan: Plan for which strategies to dispatch

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- Thread-based operations only (no async/await)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategyType(StrEnum):
    """Query strategy types for parallel dispatch.

    Values:
        STRUCTURED: SQL-based structured query (B-tree indexes)
        FULLTEXT: Full-text search via tsvector/tsquery (GIN indexes)
        VECTOR: Vector similarity search via embeddings (HNSW indexes)
    """

    STRUCTURED = "structured"
    FULLTEXT = "fulltext"
    VECTOR = "vector"


class StrategySQL(BaseModel):
    """SQL generated for a single query strategy.

    Represents the SQL query string and parameters produced by
    a strategy-specific SQL generation agent.

    Attributes:
        strategy_type: Which strategy generated this SQL
        sql: The SQL query string with %s placeholders
        parameters: Query parameters for %s placeholders
    """

    strategy_type: StrategyType
    sql: str = Field(
        ...,
        min_length=1,
        description="The SQL query string with %s placeholders",
    )
    parameters: list[Any] = Field(
        default_factory=list,
        description="Query parameters for %s placeholders",
    )

    model_config = ConfigDict(frozen=True)


class StrategyResult(BaseModel):
    """Result from executing a single query strategy.

    Contains the rows returned by a strategy's SQL execution,
    along with timing and error metadata.

    Attributes:
        strategy_type: Which strategy produced this result
        rows: List of row dictionaries (column name to value)
        columns: Column names in result set
        row_count: Number of rows returned
        execution_time_ms: Time taken to execute in milliseconds
        error: Error message if strategy failed, None on success
    """

    strategy_type: StrategyType
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    error: str | None = Field(
        default=None,
        description="Error message if strategy failed",
    )

    model_config = ConfigDict(from_attributes=True)

    @property
    def succeeded(self) -> bool:
        """Whether the strategy executed successfully."""
        return self.error is None


class StrategyAttribution(BaseModel):
    """Metadata about a strategy's contribution to the fused result.

    Tracks per-strategy statistics for result attribution
    and observability.

    Attributes:
        strategy_type: Which strategy this attribution describes
        row_count: Number of rows contributed by this strategy
        execution_time_ms: Time taken by this strategy
        succeeded: Whether the strategy executed without error
    """

    strategy_type: StrategyType
    row_count: int = Field(ge=0)
    execution_time_ms: float = Field(ge=0.0)
    succeeded: bool

    model_config = ConfigDict(frozen=True)


class FusedRow(BaseModel):
    """A single row in the fused result set.

    Represents a deduplicated row identified by its PostgreSQL
    physical tuple identifier, scored via Reciprocal Rank Fusion.

    Attributes:
        ctid: PostgreSQL physical tuple identifier (internal)
        data: Column name to value mapping (user data only)
        rrf_score: Reciprocal Rank Fusion composite score
        source_strategies: Which strategies found this row
    """

    ctid: str = Field(
        ...,
        description=("PostgreSQL physical tuple identifier (internal)"),
    )
    data: dict[str, Any] = Field(
        ...,
        description="Column name to value mapping (user data only)",
    )
    rrf_score: float = Field(
        ge=0.0,
        description="Reciprocal Rank Fusion composite score",
    )
    source_strategies: list[StrategyType] = Field(
        ...,
        min_length=1,
        description="Which strategies found this row",
    )

    model_config = ConfigDict(frozen=True)


class FusedResult(BaseModel):
    """Merged result from all query strategies.

    Contains the deduplicated, RRF-scored rows from all
    executed strategies, along with attribution metadata.

    Attributes:
        rows: Fused rows ordered by RRF score descending
        columns: Union of user data column names (excludes
            ctid, _ts_*, _emb_*, rank, similarity)
        total_row_count: Number of unique rows after dedup
        attributions: Per-strategy contribution metadata
        rrf_k: RRF constant used for scoring
    """

    rows: list[FusedRow] = Field(
        default_factory=list,
        description="Fused rows ordered by RRF score desc",
    )
    columns: list[str] = Field(
        default_factory=list,
        description=(
            "Union of user data column names" " (excludes ctid, _ts_*, _emb_*, rank, similarity)"
        ),
    )
    total_row_count: int = Field(
        default=0,
        ge=0,
        description="Number of unique rows after dedup",
    )
    attributions: list[StrategyAttribution] = Field(
        default_factory=list,
        description="Per-strategy contribution metadata",
    )
    rrf_k: int = Field(
        default=60,
        description="RRF constant used for scoring",
    )

    model_config = ConfigDict(from_attributes=True)

    @property
    def strategy_count(self) -> int:
        """Number of strategies that contributed results."""
        return sum(1 for a in self.attributions if a.succeeded and a.row_count > 0)

    @property
    def is_multi_strategy(self) -> bool:
        """Whether multiple strategies contributed results."""
        return self.strategy_count > 1


class StrategyDispatchPlan(BaseModel):
    """Plan for which strategies to dispatch based on index availability.

    Determines which query strategies should be executed in parallel,
    ensuring STRUCTURED is always present and first (FR-002).

    Attributes:
        strategies: Ordered list of strategies to dispatch
        is_aggregation: Whether aggregation intent was detected
        available_indexes: Per-table mapping of available
            index capabilities
    """

    strategies: list[StrategyType] = Field(..., min_length=1)
    is_aggregation: bool = Field(
        default=False,
        description="Whether aggregation intent detected",
    )
    available_indexes: dict[str, list[str]] = Field(
        default_factory=dict,
        description=("Per-table mapping of available index capabilities"),
    )

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_structured_always_first(
        self,
    ) -> "StrategyDispatchPlan":
        """Ensure STRUCTURED is always present and first."""
        if not self.strategies or self.strategies[0] != StrategyType.STRUCTURED:
            raise ValueError("STRUCTURED must be the first strategy (FR-002)")
        return self
