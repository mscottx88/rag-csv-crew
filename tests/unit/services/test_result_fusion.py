"""Unit tests for ResultFusionService (T014).

Tests Reciprocal Rank Fusion scoring, row deduplication, system column
exclusion, and end-to-end fusion across parallel query strategies.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from typing import Any

import pytest

from backend.src.models.fusion import (
    FusedResult,
    FusedRow,
    StrategyAttribution,
    StrategyResult,
    StrategyType,
)
from backend.src.services.result_fusion import ResultFusionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_strategy_result(
    strategy_type: StrategyType,
    rows: list[dict[str, Any]],
    columns: list[str] | None = None,
    execution_time_ms: float = 5.0,
    error: str | None = None,
) -> StrategyResult:
    """Create a StrategyResult for testing."""
    resolved_columns: list[str] = (
        columns if columns is not None else (list(rows[0].keys()) if rows else [])
    )
    return StrategyResult(
        strategy_type=strategy_type,
        rows=rows,
        columns=resolved_columns,
        row_count=len(rows),
        execution_time_ms=execution_time_ms,
        error=error,
    )


def _make_failed_result(
    strategy_type: StrategyType,
    error: str = "execution error",
) -> StrategyResult:
    """Create a failed StrategyResult for testing."""
    return StrategyResult(
        strategy_type=strategy_type,
        rows=[],
        columns=[],
        row_count=0,
        execution_time_ms=0.0,
        error=error,
    )


# ---------------------------------------------------------------------------
# compute_rrf_scores tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeRrfScores:
    """Tests for ResultFusionService.compute_rrf_scores."""

    def test_single_strategy_three_rows(self) -> None:
        """Single strategy with 3 rows scores 1/(k+rank).

        Row at rank 1 -> 1/61, rank 2 -> 1/62, rank 3 -> 1/63.
        """
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice"},
                {"ctid": "(0,2)", "name": "Bob"},
                {"ctid": "(0,3)", "name": "Charlie"},
            ],
        )
        scores: dict[str, float] = service.compute_rrf_scores([result])

        assert scores["(0,1)"] == pytest.approx(1.0 / 61.0)
        assert scores["(0,2)"] == pytest.approx(1.0 / 62.0)
        assert scores["(0,3)"] == pytest.approx(1.0 / 63.0)

    def test_two_strategies_overlapping_rows(self) -> None:
        """Two strategies with overlapping rows accumulate scores.

        Strategy 1: Row_A(rank1), Row_B(rank2), Row_C(rank3)
        Strategy 2: Row_B(rank1), Row_C(rank2), Row_D(rank3)

        Row_B: 1/62 + 1/61 = 0.03252...
        Row_C: 1/63 + 1/62 = 0.03200...
        """
        service: ResultFusionService = ResultFusionService()
        strategy1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "A"},
                {"ctid": "(0,2)", "name": "B"},
                {"ctid": "(0,3)", "name": "C"},
            ],
        )
        strategy2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {"ctid": "(0,2)", "name": "B"},
                {"ctid": "(0,3)", "name": "C"},
                {"ctid": "(0,4)", "name": "D"},
            ],
        )
        scores: dict[str, float] = service.compute_rrf_scores(
            [strategy1, strategy2],
        )

        expected_b: float = 1.0 / 62.0 + 1.0 / 61.0
        expected_c: float = 1.0 / 63.0 + 1.0 / 62.0
        assert scores["(0,2)"] == pytest.approx(expected_b)
        assert scores["(0,3)"] == pytest.approx(expected_c)
        # Row_A only in strategy 1 at rank 1
        assert scores["(0,1)"] == pytest.approx(1.0 / 61.0)
        # Row_D only in strategy 2 at rank 3
        assert scores["(0,4)"] == pytest.approx(1.0 / 63.0)

    def test_three_strategies_one_row_in_all(self) -> None:
        """Row found by all three strategies accumulates all RRF scores.

        Row_X at rank 1 in strategies 1 and 2, rank 2 in strategy 3.
        Score: 1/61 + 1/61 + 1/62 = 0.04891...
        """
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "val": "X"}],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[{"ctid": "(0,1)", "val": "X"}],
        )
        s3: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[
                {"ctid": "(0,9)", "val": "Y"},
                {"ctid": "(0,1)", "val": "X"},
            ],
        )
        scores: dict[str, float] = service.compute_rrf_scores(
            [s1, s2, s3],
        )

        expected: float = 1.0 / 61.0 + 1.0 / 61.0 + 1.0 / 62.0
        assert scores["(0,1)"] == pytest.approx(expected)
        assert expected == pytest.approx(0.04891, abs=1e-4)

    def test_default_k_is_60(self) -> None:
        """Default RRF k parameter is 60."""
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "test"}],
        )
        scores: dict[str, float] = service.compute_rrf_scores([result])

        # With k=60, rank-1 score is 1/(60+1) = 1/61
        assert scores["(0,1)"] == pytest.approx(1.0 / 61.0)

    def test_custom_k_value(self) -> None:
        """Custom k value changes RRF score computation."""
        service: ResultFusionService = ResultFusionService(rrf_k=10)
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "test"}],
        )
        scores: dict[str, float] = service.compute_rrf_scores([result])

        # With k=10, rank-1 score is 1/(10+1) = 1/11
        assert scores["(0,1)"] == pytest.approx(1.0 / 11.0)

    def test_empty_strategy_results(self) -> None:
        """Empty strategy results list returns empty scores dict."""
        service: ResultFusionService = ResultFusionService()
        scores: dict[str, float] = service.compute_rrf_scores([])

        assert not scores

    def test_strategy_with_no_rows(self) -> None:
        """Strategy with zero rows contributes nothing to scores."""
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[],
        )
        scores: dict[str, float] = service.compute_rrf_scores([result])

        assert not scores

    def test_rank_is_one_indexed(self) -> None:
        """Verify rank is 1-indexed (first row is rank 1, not rank 0).

        If rank were 0-indexed, score would be 1/(60+0) = 1/60.
        With 1-indexed rank, score is 1/(60+1) = 1/61.
        """
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "first"}],
        )
        scores: dict[str, float] = service.compute_rrf_scores([result])

        # Must NOT be 1/60 (0-indexed); must be 1/61 (1-indexed)
        assert scores["(0,1)"] != pytest.approx(1.0 / 60.0)
        assert scores["(0,1)"] == pytest.approx(1.0 / 61.0)


# ---------------------------------------------------------------------------
# deduplicate_rows tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeduplicateRows:
    """Tests for ResultFusionService.deduplicate_rows."""

    def test_no_overlapping_ctids_all_preserved(self) -> None:
        """Rows with unique ctids are all preserved."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[{"ctid": "(0,2)", "name": "Bob"}],
        )
        rrf_scores: dict[str, float] = {
            "(0,1)": 1.0 / 61.0,
            "(0,2)": 1.0 / 61.0,
        }
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [s1, s2],
            rrf_scores,
        )

        assert len(fused_rows) == 2
        ctids: set[str] = {row.ctid for row in fused_rows}
        assert ctids == {"(0,1)", "(0,2)"}

    def test_same_ctid_keeps_higher_priority_data(self) -> None:
        """Same ctid in two strategies keeps data from higher priority.

        Priority: structured > fulltext > vector.
        """
        service: ResultFusionService = ResultFusionService()
        s_structured: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice-structured"},
            ],
        )
        s_fulltext: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {"ctid": "(0,1)", "name": "Alice-fulltext", "rank": 0.9},
            ],
        )
        rrf_scores: dict[str, float] = {
            "(0,1)": 1.0 / 61.0 + 1.0 / 61.0,
        }
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [s_structured, s_fulltext],
            rrf_scores,
        )

        assert len(fused_rows) == 1
        assert fused_rows[0].data["name"] == "Alice-structured"

    def test_fulltext_beats_vector_priority(self) -> None:
        """Fulltext has higher priority than vector for data."""
        service: ResultFusionService = ResultFusionService()
        s_fulltext: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {"ctid": "(0,1)", "name": "from-fulltext"},
            ],
        )
        s_vector: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[
                {"ctid": "(0,1)", "name": "from-vector"},
            ],
        )
        rrf_scores: dict[str, float] = {
            "(0,1)": 1.0 / 61.0 + 1.0 / 61.0,
        }
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [s_fulltext, s_vector],
            rrf_scores,
        )

        assert len(fused_rows) == 1
        assert fused_rows[0].data["name"] == "from-fulltext"

    def test_source_strategies_accumulates(self) -> None:
        """source_strategies accumulates all strategies for shared ctid."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        s3: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        rrf_scores: dict[str, float] = {
            "(0,1)": 1.0 / 61.0 * 2 + 1.0 / 61.0,
        }
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [s1, s2, s3],
            rrf_scores,
        )

        assert len(fused_rows) == 1
        strategies: list[StrategyType] = list(
            fused_rows[0].source_strategies,
        )
        assert StrategyType.STRUCTURED in strategies
        assert StrategyType.FULLTEXT in strategies
        assert StrategyType.VECTOR in strategies

    def test_rows_sorted_by_rrf_score_descending(self) -> None:
        """Fused rows are sorted by rrf_score in descending order."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Low"},
                {"ctid": "(0,2)", "name": "Mid"},
            ],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {"ctid": "(0,2)", "name": "Mid"},
                {"ctid": "(0,3)", "name": "High"},
            ],
        )
        # (0,3) only in s2 at rank 2: 1/62
        # (0,1) only in s1 at rank 1: 1/61
        # (0,2) in s1 at rank 2 + s2 at rank 1: 1/62 + 1/61
        rrf_scores: dict[str, float] = {
            "(0,1)": 1.0 / 61.0,
            "(0,2)": 1.0 / 62.0 + 1.0 / 61.0,
            "(0,3)": 1.0 / 62.0,
        }
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [s1, s2],
            rrf_scores,
        )

        assert len(fused_rows) == 3
        assert fused_rows[0].ctid == "(0,2)"  # highest score
        assert fused_rows[0].rrf_score > fused_rows[1].rrf_score
        assert fused_rows[1].rrf_score >= fused_rows[2].rrf_score

    def test_system_columns_excluded_from_data(self) -> None:
        """System columns are excluded from FusedRow data (FR-007).

        Excluded: ctid, _ts_*, _emb_*, rank, similarity.
        """
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {
                    "ctid": "(0,1)",
                    "name": "Alice",
                    "age": 30,
                    "_ts_name": "alice:1",
                    "_emb_name": [0.1, 0.2],
                    "rank": 0.95,
                    "similarity": 0.88,
                },
            ],
            columns=[
                "ctid",
                "name",
                "age",
                "_ts_name",
                "_emb_name",
                "rank",
                "similarity",
            ],
        )
        rrf_scores: dict[str, float] = {"(0,1)": 1.0 / 61.0}
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [result],
            rrf_scores,
        )

        assert len(fused_rows) == 1
        data: dict[str, Any] = fused_rows[0].data
        # User columns kept
        assert "name" in data
        assert data["name"] == "Alice"
        assert "age" in data
        assert data["age"] == 30
        # System columns excluded
        assert "ctid" not in data
        assert "_ts_name" not in data
        assert "_emb_name" not in data
        assert "rank" not in data
        assert "similarity" not in data

    def test_system_columns_with_various_prefixes(self) -> None:
        """All _ts_ and _emb_ prefixed columns are excluded."""
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {
                    "ctid": "(0,1)",
                    "product": "Widget",
                    "_ts_product": "widget:1",
                    "_ts_description": "a:2 widget:1",
                    "_emb_product": [0.5, 0.6],
                    "_emb_desc": [0.7, 0.8],
                },
            ],
        )
        rrf_scores: dict[str, float] = {"(0,1)": 1.0 / 61.0}
        fused_rows: list[FusedRow] = service.deduplicate_rows(
            [result],
            rrf_scores,
        )

        data: dict[str, Any] = fused_rows[0].data
        assert "product" in data
        assert "_ts_product" not in data
        assert "_ts_description" not in data
        assert "_emb_product" not in data
        assert "_emb_desc" not in data


# ---------------------------------------------------------------------------
# fuse (end-to-end) tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFuse:
    """Tests for ResultFusionService.fuse end-to-end."""

    def test_two_strategies_overlapping_results(self) -> None:
        """Two strategies with overlapping rows produce correct fusion."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice", "age": 30},
                {"ctid": "(0,2)", "name": "Bob", "age": 25},
            ],
            execution_time_ms=10.0,
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {"ctid": "(0,2)", "name": "Bob", "age": 25},
                {"ctid": "(0,3)", "name": "Charlie", "age": 35},
            ],
            execution_time_ms=8.0,
        )
        result: FusedResult = service.fuse([s1, s2])

        # 3 unique ctids
        assert result.total_row_count == 3
        assert len(result.rows) == 3
        # (0,2) found by both should have highest score
        top_row: FusedRow = result.rows[0]
        assert top_row.ctid == "(0,2)"
        assert StrategyType.STRUCTURED in top_row.source_strategies
        assert StrategyType.FULLTEXT in top_row.source_strategies
        # rrf_k should match service default
        assert result.rrf_k == 60

    def test_all_strategies_fail_empty_result(self) -> None:
        """When all strategies fail, fuse returns empty FusedResult."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_failed_result(
            StrategyType.STRUCTURED,
            "timeout",
        )
        s2: StrategyResult = _make_failed_result(
            StrategyType.FULLTEXT,
            "syntax error",
        )
        result: FusedResult = service.fuse([s1, s2])

        assert result.total_row_count == 0
        assert result.rows == []
        assert result.columns == []
        # Attributions should still be built
        assert len(result.attributions) == 2
        failed_flags: list[bool] = [a.succeeded for a in result.attributions]
        assert all(not s for s in failed_flags)

    def test_one_strategy_fails_others_fused(self) -> None:
        """Failed strategy is filtered out; remaining strategies fused."""
        service: ResultFusionService = ResultFusionService()
        s_ok: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice"},
            ],
            execution_time_ms=5.0,
        )
        s_fail: StrategyResult = _make_failed_result(
            StrategyType.FULLTEXT,
            "index not found",
        )
        result: FusedResult = service.fuse([s_ok, s_fail])

        assert result.total_row_count == 1
        assert len(result.rows) == 1
        assert result.rows[0].data["name"] == "Alice"
        # Attributions for both present
        assert len(result.attributions) == 2
        structured_attr: StrategyAttribution = next(
            a for a in result.attributions if a.strategy_type == StrategyType.STRUCTURED
        )
        fulltext_attr: StrategyAttribution = next(
            a for a in result.attributions if a.strategy_type == StrategyType.FULLTEXT
        )
        assert structured_attr.succeeded is True
        assert fulltext_attr.succeeded is False

    def test_one_strategy_empty_attribution_correct(self) -> None:
        """Strategy returning zero rows has 0 rows but succeeded=True."""
        service: ResultFusionService = ResultFusionService()
        s_with_rows: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
            execution_time_ms=5.0,
        )
        s_empty: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[],
            execution_time_ms=3.0,
        )
        result: FusedResult = service.fuse([s_with_rows, s_empty])

        assert result.total_row_count == 1
        vector_attr: StrategyAttribution = next(
            a for a in result.attributions if a.strategy_type == StrategyType.VECTOR
        )
        assert vector_attr.row_count == 0
        assert vector_attr.succeeded is True

    def test_missing_ctid_column_strategy_skipped(self) -> None:
        """Strategy with rows missing ctid is treated as failed."""
        service: ResultFusionService = ResultFusionService()
        s_ok: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        s_no_ctid: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[{"name": "Bob", "age": 25}],
            columns=["name", "age"],
        )
        result: FusedResult = service.fuse([s_ok, s_no_ctid])

        assert result.total_row_count == 1
        assert result.rows[0].data["name"] == "Alice"

    def test_single_strategy_passthrough(self) -> None:
        """Single strategy result passes through without dedup."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice"},
                {"ctid": "(0,2)", "name": "Bob"},
            ],
            execution_time_ms=12.0,
        )
        result: FusedResult = service.fuse([s1])

        assert result.total_row_count == 2
        assert len(result.rows) == 2
        assert result.rows[0].rrf_score > result.rows[1].rrf_score
        assert len(result.rows[0].source_strategies) == 1
        assert result.rows[0].source_strategies[0] == (StrategyType.STRUCTURED)

    def test_attributions_correctly_built(self) -> None:
        """Each strategy gets an attribution with correct metadata."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice"},
                {"ctid": "(0,2)", "name": "Bob"},
            ],
            execution_time_ms=15.0,
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[
                {"ctid": "(0,3)", "name": "Charlie"},
            ],
            execution_time_ms=25.0,
        )
        result: FusedResult = service.fuse([s1, s2])

        assert len(result.attributions) == 2
        attr_structured: StrategyAttribution = next(
            a for a in result.attributions if a.strategy_type == StrategyType.STRUCTURED
        )
        attr_vector: StrategyAttribution = next(
            a for a in result.attributions if a.strategy_type == StrategyType.VECTOR
        )
        assert attr_structured.row_count == 2
        assert attr_structured.execution_time_ms == 15.0
        assert attr_structured.succeeded is True
        assert attr_vector.row_count == 1
        assert attr_vector.execution_time_ms == 25.0
        assert attr_vector.succeeded is True

    def test_columns_union_of_user_data(self) -> None:
        """FusedResult.columns is union of user data columns.

        System columns (ctid, _ts_*, _emb_*, rank, similarity) excluded.
        """
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {
                    "ctid": "(0,1)",
                    "name": "Alice",
                    "age": 30,
                    "_ts_name": "alice:1",
                },
            ],
            columns=["ctid", "name", "age", "_ts_name"],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {
                    "ctid": "(0,2)",
                    "name": "Bob",
                    "salary": 50000,
                    "rank": 0.85,
                },
            ],
            columns=["ctid", "name", "salary", "rank"],
        )
        result: FusedResult = service.fuse([s1, s2])

        columns_set: set[str] = set(result.columns)
        # User columns from both strategies
        assert "name" in columns_set
        assert "age" in columns_set
        assert "salary" in columns_set
        # System columns excluded
        assert "ctid" not in columns_set
        assert "_ts_name" not in columns_set
        assert "rank" not in columns_set

    def test_fuse_empty_input(self) -> None:
        """Fuse with empty input list returns empty FusedResult."""
        service: ResultFusionService = ResultFusionService()
        result: FusedResult = service.fuse([])

        assert result.total_row_count == 0
        assert result.rows == []
        assert result.columns == []
        assert result.attributions == []

    def test_fuse_preserves_rrf_k_in_result(self) -> None:
        """FusedResult.rrf_k matches the service configuration."""
        service: ResultFusionService = ResultFusionService(rrf_k=30)
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        result: FusedResult = service.fuse([s1])

        assert result.rrf_k == 30

    def test_fuse_scores_match_compute_rrf(self) -> None:
        """Fused row scores match standalone compute_rrf_scores."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice"},
                {"ctid": "(0,2)", "name": "Bob"},
            ],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[
                {"ctid": "(0,2)", "name": "Bob"},
            ],
        )
        # Compute expected scores independently
        expected_scores: dict[str, float] = service.compute_rrf_scores([s1, s2])
        result: FusedResult = service.fuse([s1, s2])

        for row in result.rows:
            assert row.rrf_score == pytest.approx(
                expected_scores[row.ctid],
            )


# ---------------------------------------------------------------------------
# Tie-breaking test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTieBreaking:
    """Tests for RRF tie-breaking behavior."""

    def test_identical_rrf_scores_ordered_by_priority(self) -> None:
        """Two rows with identical RRF scores ordered by priority.

        When scores are tied, rows from higher-priority strategies
        (structured > fulltext > vector) appear first.
        """
        service: ResultFusionService = ResultFusionService()
        # Row in vector only at rank 1
        s_vector: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[{"ctid": "(0,1)", "name": "VectorRow"}],
        )
        # Row in structured only at rank 1 (same score: 1/61)
        s_structured: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,2)", "name": "StructuredRow"}],
        )
        result: FusedResult = service.fuse([s_structured, s_vector])

        # Both have identical RRF score 1/61
        assert result.rows[0].rrf_score == pytest.approx(
            result.rows[1].rrf_score,
        )
        # Structured-sourced row should come first
        assert result.rows[0].ctid == "(0,2)"
        assert result.rows[0].data["name"] == "StructuredRow"
        assert result.rows[1].ctid == "(0,1)"
        assert result.rows[1].data["name"] == "VectorRow"

    def test_tie_breaking_fulltext_before_vector(self) -> None:
        """Fulltext-sourced row breaks tie before vector-sourced row."""
        service: ResultFusionService = ResultFusionService()
        s_fulltext: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=[{"ctid": "(0,1)", "name": "FulltextRow"}],
        )
        s_vector: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[{"ctid": "(0,2)", "name": "VectorRow"}],
        )
        result: FusedResult = service.fuse([s_fulltext, s_vector])

        assert result.rows[0].rrf_score == pytest.approx(
            result.rows[1].rrf_score,
        )
        assert result.rows[0].ctid == "(0,1)"
        assert result.rows[0].data["name"] == "FulltextRow"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for ResultFusionService."""

    def test_large_number_of_rows(self) -> None:
        """Service handles a strategy with many rows correctly."""
        service: ResultFusionService = ResultFusionService()
        rows: list[dict[str, Any]] = [{"ctid": f"(0,{i})", "val": i} for i in range(1, 101)]
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=rows,
        )
        fused: FusedResult = service.fuse([result])

        assert fused.total_row_count == 100
        # First row has highest RRF score (rank 1)
        assert fused.rows[0].ctid == "(0,1)"
        assert fused.rows[0].rrf_score == pytest.approx(1.0 / 61.0)
        # Last row has lowest RRF score (rank 100)
        assert fused.rows[99].ctid == "(0,100)"
        assert fused.rows[99].rrf_score == pytest.approx(
            1.0 / 160.0,
        )

    def test_all_three_strategies_full_overlap(self) -> None:
        """All three strategies return identical rows."""
        service: ResultFusionService = ResultFusionService()
        shared_rows: list[dict[str, Any]] = [
            {"ctid": "(0,1)", "name": "Alice"},
            {"ctid": "(0,2)", "name": "Bob"},
        ]
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=shared_rows,
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.FULLTEXT,
            rows=shared_rows,
        )
        s3: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=shared_rows,
        )
        result: FusedResult = service.fuse([s1, s2, s3])

        # Only 2 unique rows after dedup
        assert result.total_row_count == 2
        # Each row found by all 3 strategies
        for row in result.rows:
            assert len(row.source_strategies) == 3
        # Data comes from structured (highest priority)
        assert result.rows[0].data["name"] == "Alice"

    def test_row_data_only_system_columns_yields_empty_data(
        self,
    ) -> None:
        """Row with only system columns yields empty data dict."""
        service: ResultFusionService = ResultFusionService()
        result: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {
                    "ctid": "(0,1)",
                    "_ts_col": "val",
                    "_emb_col": [0.1],
                    "rank": 1.0,
                    "similarity": 0.9,
                },
            ],
            columns=[
                "ctid",
                "_ts_col",
                "_emb_col",
                "rank",
                "similarity",
            ],
        )
        fused: FusedResult = service.fuse([result])

        assert fused.total_row_count == 1
        assert fused.rows[0].data == {}

    def test_mixed_columns_across_strategies(self) -> None:
        """Different strategies return different user columns."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[
                {"ctid": "(0,1)", "name": "Alice", "dept": "Eng"},
            ],
            columns=["ctid", "name", "dept"],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.VECTOR,
            rows=[
                {"ctid": "(0,2)", "name": "Bob", "salary": 90000},
            ],
            columns=["ctid", "name", "salary"],
        )
        result: FusedResult = service.fuse([s1, s2])

        columns_set: set[str] = set(result.columns)
        assert columns_set == {"name", "dept", "salary"}

    def test_duplicate_strategy_types_handled(self) -> None:
        """Two results with the same strategy type are handled."""
        service: ResultFusionService = ResultFusionService()
        s1: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,1)", "name": "Alice"}],
        )
        s2: StrategyResult = _make_strategy_result(
            strategy_type=StrategyType.STRUCTURED,
            rows=[{"ctid": "(0,2)", "name": "Bob"}],
        )
        result: FusedResult = service.fuse([s1, s2])

        assert result.total_row_count == 2
