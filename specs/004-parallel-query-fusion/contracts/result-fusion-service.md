# Contract: Result Fusion Service

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03
**Module**: `backend/src/services/result_fusion.py`

## New Class: ResultFusionService

### Constructor

```python
class ResultFusionService:
    """Fuses results from multiple query strategies using Reciprocal Rank Fusion."""

    def __init__(self, rrf_k: int = 60) -> None:
        """Initialize with RRF constant k.

        Args:
            rrf_k: Constant for RRF scoring formula. Default 60 per spec.
        """
```

### Method: fuse

```python
def fuse(self, strategy_results: list[StrategyResult]) -> FusedResult:
    """Merge results from multiple strategies into a single fused result.

    Steps:
    1. Filter to successful strategies only (FR-012 graceful degradation)
    2. Compute RRF scores for each unique row (identified by ctid)
    3. Deduplicate rows — keep first occurrence's data columns
    4. Sort by RRF score descending (FR-010)
    5. Build strategy attribution metadata (FR-014, FR-015)

    Args:
        strategy_results: Results from each executed strategy.

    Returns:
        FusedResult with deduplicated rows, RRF scores, and attributions.
        If all strategies failed, returns empty FusedResult.
    """
```

### Method: compute_rrf_scores

```python
def compute_rrf_scores(
    self,
    strategy_results: list[StrategyResult],
) -> dict[str, float]:
    """Compute RRF scores for all rows across strategies.

    For each row identified by ctid:
        score = sum(1 / (k + rank)) across strategies that returned it
    where rank is 1-indexed position in the strategy's result list.

    Args:
        strategy_results: Successful strategy results only.

    Returns:
        Dictionary mapping ctid → RRF score.
    """
```

### Method: deduplicate_rows

```python
def deduplicate_rows(
    self,
    strategy_results: list[StrategyResult],
    rrf_scores: dict[str, float],
) -> list[FusedRow]:
    """Deduplicate rows by ctid and create FusedRow objects.

    When a row (same ctid) appears in multiple strategies:
    - Data columns are taken from the first occurrence
    - source_strategies lists all strategies that found it
    - rrf_score is the pre-computed RRF score

    Rows are sorted by rrf_score descending.

    Args:
        strategy_results: Successful strategy results.
        rrf_scores: Pre-computed ctid → RRF score mapping.

    Returns:
        List of FusedRow objects, sorted by rrf_score descending.
    """
```

## RRF Scoring Examples

### Example 1: Two strategies, overlapping rows

```
Structured results:  [Row_A (rank 1), Row_B (rank 2), Row_C (rank 3)]
Fulltext results:    [Row_B (rank 1), Row_C (rank 2), Row_D (rank 3)]

RRF scores (k=60):
  Row_A: 1/(60+1) = 0.01639
  Row_B: 1/(60+2) + 1/(60+1) = 0.01613 + 0.01639 = 0.03252  ← highest (found by both)
  Row_C: 1/(60+3) + 1/(60+2) = 0.01587 + 0.01613 = 0.03200
  Row_D: 1/(60+3) = 0.01587

Final ordering: [Row_B, Row_C, Row_A, Row_D]
```

### Example 2: Three strategies, one row found by all

```
Structured: [Row_X (rank 1)]
Fulltext:   [Row_X (rank 1), Row_Y (rank 2)]
Vector:     [Row_Y (rank 1), Row_X (rank 2)]

RRF scores:
  Row_X: 1/61 + 1/61 + 1/62 = 0.01639 + 0.01639 + 0.01613 = 0.04891
  Row_Y: 1/62 + 1/61 = 0.01613 + 0.01639 = 0.03252

Final ordering: [Row_X, Row_Y]
```

### Example 3: Single strategy (no fusion needed)

```
Structured: [Row_A, Row_B, Row_C]

RRF scores (degenerate case):
  Row_A: 1/61 = 0.01639
  Row_B: 1/62 = 0.01613
  Row_C: 1/63 = 0.01587

Final ordering: [Row_A, Row_B, Row_C]  (preserves original order)
```

## Edge Cases

- **All strategies fail**: Return empty `FusedResult` with all attributions showing `succeeded=False`.
- **One strategy returns empty**: Its attribution shows `row_count=0, succeeded=True`. Other strategies' results are fused normally.
- **ctid column missing from results**: Log warning for that strategy, skip it during fusion (treated as failed). This can happen if the LLM ignores the ctid instruction.
- **Duplicate ctids within a single strategy**: Should not happen (PostgreSQL guarantees unique ctids per table). If it does, keep first occurrence.
