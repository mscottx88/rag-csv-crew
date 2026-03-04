"""Result fusion service using Reciprocal Rank Fusion (RRF).

Merges results from multiple query strategies into a single composite
result set using RRF scoring (k=60) with ctid-based deduplication.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import re
from typing import Any

from backend.src.models.fusion import (
    FusedResult,
    FusedRow,
    StrategyAttribution,
    StrategyResult,
    StrategyType,
)
from backend.src.utils.logging import get_structured_logger

logger = get_structured_logger(__name__)

# System columns to exclude from user-visible data (FR-007)
_SYSTEM_COLUMN_PATTERN: re.Pattern[str] = re.compile(r"^(ctid|rank|similarity|_ts_.*|_emb_.*)$")

# Strategy priority order for data retention during dedup
_STRATEGY_PRIORITY: dict[StrategyType, int] = {
    StrategyType.STRUCTURED: 0,
    StrategyType.FULLTEXT: 1,
    StrategyType.VECTOR: 2,
}


class ResultFusionService:
    """Fuses results from multiple query strategies using RRF.

    Implements Reciprocal Rank Fusion (Cormack, Clarke & Butt, 2009)
    with ctid-based deduplication for merging parallel query results.
    """

    def __init__(self, rrf_k: int = 60) -> None:
        """Initialize with RRF constant k.

        Args:
            rrf_k: Constant for RRF scoring formula. Default 60 per spec.
        """
        self._rrf_k: int = rrf_k

    def fuse(self, strategy_results: list[StrategyResult]) -> FusedResult:
        """Merge results from multiple strategies into a single result.

        Steps:
        1. Filter to successful strategies only (FR-012)
        2. Skip strategies missing ctid column
        3. Compute RRF scores for each unique row
        4. Deduplicate rows by ctid
        5. Sort by RRF score descending (FR-010)
        6. Build strategy attribution metadata

        Args:
            strategy_results: Results from each executed strategy.

        Returns:
            FusedResult with deduplicated rows, RRF scores,
            and attributions. Empty FusedResult if all fail.
        """
        # Build attributions for all strategies (including failed)
        attributions: list[StrategyAttribution] = [
            StrategyAttribution(
                strategy_type=sr.strategy_type,
                row_count=sr.row_count,
                execution_time_ms=sr.execution_time_ms,
                succeeded=sr.succeeded,
            )
            for sr in strategy_results
        ]

        # Filter to successful strategies with ctid column
        valid_results: list[StrategyResult] = []
        for sr in strategy_results:
            if not sr.succeeded:
                continue
            if sr.row_count == 0:
                continue
            if "ctid" not in sr.columns:
                logger.warning(
                    "Strategy %s missing ctid column, skipping",
                    sr.strategy_type.value,
                )
                continue
            valid_results.append(sr)

        if not valid_results:
            return FusedResult(
                rows=[],
                columns=[],
                total_row_count=0,
                attributions=attributions,
                rrf_k=self._rrf_k,
            )

        # Compute RRF scores
        rrf_scores: dict[str, float] = self.compute_rrf_scores(valid_results)

        # Deduplicate and build FusedRows
        fused_rows: list[FusedRow] = self.deduplicate_rows(valid_results, rrf_scores)

        # Collect union of user data columns (FR-007)
        all_columns: set[str] = set()
        for sr in valid_results:
            for col in sr.columns:
                if not _SYSTEM_COLUMN_PATTERN.match(col):
                    all_columns.add(col)

        columns_sorted: list[str] = sorted(all_columns)

        return FusedResult(
            rows=fused_rows,
            columns=columns_sorted,
            total_row_count=len(fused_rows),
            attributions=attributions,
            rrf_k=self._rrf_k,
        )

    def compute_rrf_scores(
        self,
        strategy_results: list[StrategyResult],
    ) -> dict[str, float]:
        """Compute RRF scores for all rows across strategies.

        For each row identified by ctid:
            score = sum(1 / (k + rank)) across strategies
        where rank is 1-indexed position in strategy's result list.

        Args:
            strategy_results: Successful strategy results only.

        Returns:
            Dictionary mapping ctid to RRF score.
        """
        scores: dict[str, float] = {}

        for sr in strategy_results:
            for rank_zero, row in enumerate(sr.rows):
                ctid: str = str(row.get("ctid", ""))
                if not ctid:
                    continue
                rank: int = rank_zero + 1  # 1-indexed
                rrf_contribution: float = 1.0 / (self._rrf_k + rank)
                scores[ctid] = scores.get(ctid, 0.0) + rrf_contribution

        return scores

    # pylint: disable=too-many-locals
    # JUSTIFICATION: Deduplication requires tracking: seen_data, seen_strategies,
    # seen_priority_rank per ctid, plus iteration vars (sr, priority, rank_zero,
    # row, ctid, filtered_data) and output construction (fused_rows, score,
    # strategies). Splitting would fragment the dedup logic.
    def deduplicate_rows(
        self,
        strategy_results: list[StrategyResult],
        rrf_scores: dict[str, float],
    ) -> list[FusedRow]:
        """Deduplicate rows by ctid and create FusedRow objects.

        When a row (same ctid) appears in multiple strategies:
        - Data columns taken from first strategy in priority order
          (structured > fulltext > vector)
        - source_strategies lists all strategies that found it
        - rrf_score is the pre-computed RRF score

        Args:
            strategy_results: Successful strategy results.
            rrf_scores: Pre-computed ctid to RRF score mapping.

        Returns:
            List of FusedRow objects, sorted by rrf_score descending.
            Ties broken by position in highest-priority strategy.
        """
        # Sort results by priority order
        sorted_results: list[StrategyResult] = sorted(
            strategy_results,
            key=lambda sr: _STRATEGY_PRIORITY.get(sr.strategy_type, 99),
        )

        # Track seen ctids and their data/strategies
        seen_data: dict[str, dict[str, Any]] = {}
        seen_strategies: dict[str, list[StrategyType]] = {}
        # Track rank in highest-priority strategy for tie-breaking
        seen_priority_rank: dict[str, tuple[int, int]] = {}

        for sr in sorted_results:
            priority: int = _STRATEGY_PRIORITY.get(sr.strategy_type, 99)
            for rank_zero, row in enumerate(sr.rows):
                ctid: str = str(row.get("ctid", ""))
                if not ctid:
                    continue

                if ctid not in seen_data:
                    # First occurrence — keep this data
                    filtered_data: dict[str, Any] = {
                        k: v for k, v in row.items() if not _SYSTEM_COLUMN_PATTERN.match(k)
                    }
                    seen_data[ctid] = filtered_data
                    seen_strategies[ctid] = [sr.strategy_type]
                    seen_priority_rank[ctid] = (
                        priority,
                        rank_zero,
                    )
                else:
                    # Already seen — accumulate strategy
                    seen_strategies[ctid].append(sr.strategy_type)

        # Build FusedRow objects
        fused_rows: list[FusedRow] = []
        for ctid, data in seen_data.items():
            score: float = rrf_scores.get(ctid, 0.0)
            strategies: list[StrategyType] = seen_strategies[ctid]
            fused_rows.append(
                FusedRow(
                    ctid=ctid,
                    data=data,
                    rrf_score=score,
                    source_strategies=strategies,
                )
            )

        # Sort by RRF score descending, then by priority rank for ties
        fused_rows.sort(
            key=lambda r: (
                -r.rrf_score,
                seen_priority_rank.get(r.ctid, (99, 99)),
            )
        )

        return fused_rows

    # pylint: enable=too-many-locals
