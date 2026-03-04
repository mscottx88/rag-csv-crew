"""Unit tests for parallel query fusion Pydantic models.

Tests StrategyType enum, StrategySQL, StrategyResult, StrategyAttribution,
FusedRow, FusedResult, and StrategyDispatchPlan validation rules per
specs/004-parallel-query-fusion/data-model.md.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from typing import Any

from pydantic import ValidationError
import pytest

from backend.src.models.fusion import (
    FusedResult,
    FusedRow,
    StrategyAttribution,
    StrategyDispatchPlan,
    StrategyResult,
    StrategySQL,
    StrategyType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attribution(
    strategy_type: StrategyType = StrategyType.STRUCTURED,
    row_count: int = 5,
    execution_time_ms: float = 10.0,
    succeeded: bool = True,
) -> StrategyAttribution:
    """Create a StrategyAttribution for testing."""
    return StrategyAttribution(
        strategy_type=strategy_type,
        row_count=row_count,
        execution_time_ms=execution_time_ms,
        succeeded=succeeded,
    )


def _make_fused_row(
    ctid: str = "(0,1)",
    data: dict[str, Any] | None = None,
    rrf_score: float = 0.5,
    source_strategies: list[StrategyType] | None = None,
) -> FusedRow:
    """Create a FusedRow for testing."""
    return FusedRow(
        ctid=ctid,
        data=data if data is not None else {"name": "Alice"},
        rrf_score=rrf_score,
        source_strategies=(
            source_strategies if source_strategies is not None else [StrategyType.STRUCTURED]
        ),
    )


# ---------------------------------------------------------------------------
# StrategyType enum
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStrategyType:
    """Test StrategyType StrEnum values and membership."""

    def test_structured_value(self) -> None:
        """Test STRUCTURED has value 'structured'."""
        assert StrategyType.STRUCTURED.value == "structured"

    def test_fulltext_value(self) -> None:
        """Test FULLTEXT has value 'fulltext'."""
        assert StrategyType.FULLTEXT.value == "fulltext"

    def test_vector_value(self) -> None:
        """Test VECTOR has value 'vector'."""
        assert StrategyType.VECTOR.value == "vector"

    def test_exactly_three_members(self) -> None:
        """Test StrategyType has exactly three members."""
        members: list[str] = [m.value for m in StrategyType]
        assert members == ["structured", "fulltext", "vector"]

    def test_is_str_subclass(self) -> None:
        """Test StrategyType values are str-compatible (StrEnum)."""
        value: str = StrategyType.STRUCTURED
        assert isinstance(value, str)


# ---------------------------------------------------------------------------
# StrategySQL
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStrategySQL:
    """Test StrategySQL model validation and frozen config."""

    def test_valid_strategy_sql(self) -> None:
        """Test creating a valid StrategySQL instance."""
        sql_obj: StrategySQL = StrategySQL(
            strategy_type=StrategyType.STRUCTURED,
            sql="SELECT * FROM t WHERE id = %s",
            parameters=[42],
        )
        assert sql_obj.strategy_type == StrategyType.STRUCTURED
        assert sql_obj.sql == "SELECT * FROM t WHERE id = %s"
        assert sql_obj.parameters == [42]

    def test_parameters_default_empty_list(self) -> None:
        """Test that parameters defaults to an empty list."""
        sql_obj: StrategySQL = StrategySQL(
            strategy_type=StrategyType.FULLTEXT,
            sql="SELECT 1",
        )
        assert sql_obj.parameters == []

    def test_sql_min_length_rejects_empty(self) -> None:
        """Test that sql field rejects empty string (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            StrategySQL(
                strategy_type=StrategyType.STRUCTURED,
                sql="",
            )
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "string_too_short" for e in errors)

    def test_sql_required(self) -> None:
        """Test that sql field is required."""
        with pytest.raises(ValidationError):
            StrategySQL(
                strategy_type=StrategyType.STRUCTURED,
            )  # type: ignore[call-arg]

    def test_strategy_type_required(self) -> None:
        """Test that strategy_type field is required."""
        with pytest.raises(ValidationError):
            StrategySQL(
                sql="SELECT 1",
            )  # type: ignore[call-arg]

    def test_frozen_prevents_mutation(self) -> None:
        """Test that frozen config prevents attribute assignment."""
        sql_obj: StrategySQL = StrategySQL(
            strategy_type=StrategyType.VECTOR,
            sql="SELECT 1",
        )
        with pytest.raises(ValidationError):
            sql_obj.sql = "SELECT 2"

    def test_strategy_type_invalid_value(self) -> None:
        """Test that invalid strategy_type is rejected."""
        with pytest.raises(ValidationError):
            StrategySQL(
                strategy_type="invalid",  # type: ignore[arg-type]
                sql="SELECT 1",
            )

    def test_multiple_parameters(self) -> None:
        """Test StrategySQL with multiple parameters."""
        params: list[Any] = ["search term", 100, 0.5]
        sql_obj: StrategySQL = StrategySQL(
            strategy_type=StrategyType.FULLTEXT,
            sql="SELECT * FROM t WHERE col @@ %s LIMIT %s",
            parameters=params,
        )
        assert sql_obj.parameters == params
        assert len(sql_obj.parameters) == 3


# ---------------------------------------------------------------------------
# StrategyResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStrategyResult:
    """Test StrategyResult model validation, defaults, and properties."""

    def test_valid_strategy_result(self) -> None:
        """Test creating a valid StrategyResult with all fields."""
        rows: list[dict[str, Any]] = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        result: StrategyResult = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
            rows=rows,
            columns=["id", "name"],
            row_count=2,
            execution_time_ms=15.3,
        )
        assert result.strategy_type == StrategyType.STRUCTURED
        assert result.rows == rows
        assert result.columns == ["id", "name"]
        assert result.row_count == 2
        assert result.execution_time_ms == 15.3
        assert result.error is None

    def test_defaults(self) -> None:
        """Test that all optional fields have correct defaults."""
        result: StrategyResult = StrategyResult(
            strategy_type=StrategyType.FULLTEXT,
        )
        assert result.rows == []
        assert result.columns == []
        assert result.row_count == 0
        assert result.execution_time_ms == 0.0
        assert result.error is None

    def test_succeeded_true_when_no_error(self) -> None:
        """Test succeeded property returns True when error is None."""
        result: StrategyResult = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
        )
        assert result.succeeded is True

    def test_succeeded_false_when_error(self) -> None:
        """Test succeeded property returns False when error is set."""
        result: StrategyResult = StrategyResult(
            strategy_type=StrategyType.STRUCTURED,
            error="relation does not exist",
        )
        assert result.succeeded is False

    def test_succeeded_false_with_empty_string_error(self) -> None:
        """Test succeeded returns False when error is empty string."""
        result: StrategyResult = StrategyResult(
            strategy_type=StrategyType.VECTOR,
            error="",
        )
        # Empty string is not None, so succeeded should be False
        assert result.succeeded is False

    def test_row_count_ge_zero(self) -> None:
        """Test that row_count rejects negative values (ge=0)."""
        with pytest.raises(ValidationError) as exc_info:
            StrategyResult(
                strategy_type=StrategyType.STRUCTURED,
                row_count=-1,
            )
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_execution_time_ms_ge_zero(self) -> None:
        """Test that execution_time_ms rejects negative values."""
        with pytest.raises(ValidationError) as exc_info:
            StrategyResult(
                strategy_type=StrategyType.STRUCTURED,
                execution_time_ms=-0.1,
            )
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_from_attributes_config(self) -> None:
        """Test that from_attributes is True in model config."""
        config: Any = StrategyResult.model_config
        assert config.get("from_attributes") is True

    def test_strategy_type_required(self) -> None:
        """Test that strategy_type is required."""
        with pytest.raises(ValidationError):
            StrategyResult()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# StrategyAttribution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStrategyAttribution:
    """Test StrategyAttribution model validation and frozen config."""

    def test_valid_attribution(self) -> None:
        """Test creating a valid StrategyAttribution."""
        attr: StrategyAttribution = _make_attribution()
        assert attr.strategy_type == StrategyType.STRUCTURED
        assert attr.row_count == 5
        assert attr.execution_time_ms == 10.0
        assert attr.succeeded is True

    def test_frozen_prevents_mutation(self) -> None:
        """Test that frozen config prevents attribute changes."""
        attr: StrategyAttribution = _make_attribution()
        with pytest.raises(ValidationError):
            attr.row_count = 10

    def test_row_count_ge_zero(self) -> None:
        """Test that row_count rejects negative values (ge=0)."""
        with pytest.raises(ValidationError) as exc_info:
            StrategyAttribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=-1,
                execution_time_ms=5.0,
                succeeded=True,
            )
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_row_count_zero_allowed(self) -> None:
        """Test that row_count=0 is valid (ge=0)."""
        attr: StrategyAttribution = _make_attribution(row_count=0)
        assert attr.row_count == 0

    def test_execution_time_ms_ge_zero(self) -> None:
        """Test that execution_time_ms rejects negative values."""
        with pytest.raises(ValidationError) as exc_info:
            StrategyAttribution(
                strategy_type=StrategyType.FULLTEXT,
                row_count=0,
                execution_time_ms=-0.01,
                succeeded=False,
            )
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_execution_time_ms_zero_allowed(self) -> None:
        """Test that execution_time_ms=0.0 is valid."""
        attr: StrategyAttribution = _make_attribution(
            execution_time_ms=0.0,
        )
        assert attr.execution_time_ms == 0.0

    def test_succeeded_false(self) -> None:
        """Test attribution with succeeded=False."""
        attr: StrategyAttribution = _make_attribution(
            succeeded=False,
        )
        assert attr.succeeded is False

    def test_all_fields_required(self) -> None:
        """Test that all fields are required (no defaults)."""
        with pytest.raises(ValidationError):
            StrategyAttribution(
                strategy_type=StrategyType.VECTOR,
            )  # type: ignore[call-arg]

    def test_all_strategy_types(self) -> None:
        """Test attribution with each strategy type."""
        for st in StrategyType:
            attr: StrategyAttribution = _make_attribution(
                strategy_type=st,
            )
            assert attr.strategy_type == st


# ---------------------------------------------------------------------------
# FusedRow
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFusedRow:
    """Test FusedRow model validation and frozen config."""

    def test_valid_fused_row(self) -> None:
        """Test creating a valid FusedRow."""
        row: FusedRow = _make_fused_row()
        assert row.ctid == "(0,1)"
        assert row.data == {"name": "Alice"}
        assert row.rrf_score == 0.5
        assert row.source_strategies == [StrategyType.STRUCTURED]

    def test_frozen_prevents_mutation(self) -> None:
        """Test that frozen config prevents attribute changes."""
        row: FusedRow = _make_fused_row()
        with pytest.raises(ValidationError):
            row.rrf_score = 1.0

    def test_ctid_required(self) -> None:
        """Test that ctid is a required field."""
        with pytest.raises(ValidationError):
            FusedRow(
                data={"name": "Alice"},
                rrf_score=0.5,
                source_strategies=[StrategyType.STRUCTURED],
            )  # type: ignore[call-arg]

    def test_data_required(self) -> None:
        """Test that data is a required field."""
        with pytest.raises(ValidationError):
            FusedRow(
                ctid="(0,1)",
                rrf_score=0.5,
                source_strategies=[StrategyType.STRUCTURED],
            )  # type: ignore[call-arg]

    def test_rrf_score_ge_zero(self) -> None:
        """Test that rrf_score rejects negative values (ge=0.0)."""
        with pytest.raises(ValidationError) as exc_info:
            _make_fused_row(rrf_score=-0.01)
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_rrf_score_zero_allowed(self) -> None:
        """Test that rrf_score=0.0 is valid."""
        row: FusedRow = _make_fused_row(rrf_score=0.0)
        assert row.rrf_score == 0.0

    def test_source_strategies_min_length(self) -> None:
        """Test source_strategies rejects empty list (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            _make_fused_row(source_strategies=[])
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "too_short" for e in errors)

    def test_source_strategies_required(self) -> None:
        """Test that source_strategies is a required field."""
        with pytest.raises(ValidationError):
            FusedRow(
                ctid="(0,1)",
                data={"name": "Alice"},
                rrf_score=0.5,
            )  # type: ignore[call-arg]

    def test_multiple_source_strategies(self) -> None:
        """Test FusedRow with multiple source strategies."""
        strategies: list[StrategyType] = [
            StrategyType.STRUCTURED,
            StrategyType.FULLTEXT,
            StrategyType.VECTOR,
        ]
        row: FusedRow = _make_fused_row(
            source_strategies=strategies,
        )
        assert len(row.source_strategies) == 3
        assert StrategyType.VECTOR in row.source_strategies

    def test_data_empty_dict_allowed(self) -> None:
        """Test that data can be an empty dict."""
        row: FusedRow = _make_fused_row(data={})
        assert row.data == {}

    def test_data_complex_values(self) -> None:
        """Test FusedRow with various data value types."""
        data: dict[str, Any] = {
            "name": "Alice",
            "age": 30,
            "salary": 75000.50,
            "active": True,
            "notes": None,
        }
        row: FusedRow = _make_fused_row(data=data)
        assert row.data["age"] == 30
        assert row.data["salary"] == 75000.50
        assert row.data["active"] is True
        assert row.data["notes"] is None


# ---------------------------------------------------------------------------
# FusedResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFusedResult:
    """Test FusedResult model, defaults, and computed properties."""

    def test_defaults(self) -> None:
        """Test that all optional fields have correct defaults."""
        result: FusedResult = FusedResult()
        assert result.rows == []
        assert result.columns == []
        assert result.total_row_count == 0
        assert result.attributions == []
        assert result.rrf_k == 60

    def test_valid_fused_result_with_data(self) -> None:
        """Test creating a FusedResult with rows and attributions."""
        row: FusedRow = _make_fused_row()
        attr: StrategyAttribution = _make_attribution()
        result: FusedResult = FusedResult(
            rows=[row],
            columns=["name"],
            total_row_count=1,
            attributions=[attr],
            rrf_k=60,
        )
        assert len(result.rows) == 1
        assert result.rows[0].ctid == "(0,1)"
        assert result.columns == ["name"]
        assert result.total_row_count == 1
        assert len(result.attributions) == 1

    def test_from_attributes_config(self) -> None:
        """Test that from_attributes is True in model config."""
        config: Any = FusedResult.model_config
        assert config.get("from_attributes") is True

    def test_total_row_count_ge_zero(self) -> None:
        """Test total_row_count rejects negative values (ge=0)."""
        with pytest.raises(ValidationError) as exc_info:
            FusedResult(total_row_count=-1)
        errors: list[Any] = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_rrf_k_default(self) -> None:
        """Test that rrf_k defaults to 60."""
        result: FusedResult = FusedResult()
        assert result.rrf_k == 60

    def test_rrf_k_custom(self) -> None:
        """Test that rrf_k can be overridden."""
        result: FusedResult = FusedResult(rrf_k=30)
        assert result.rrf_k == 30

    # -- strategy_count property --

    def test_strategy_count_zero_no_attributions(self) -> None:
        """Test strategy_count is 0 when no attributions."""
        result: FusedResult = FusedResult()
        assert result.strategy_count == 0

    def test_strategy_count_one_succeeded(self) -> None:
        """Test strategy_count is 1 with single succeeded attribution."""
        attr: StrategyAttribution = _make_attribution(
            row_count=3,
            succeeded=True,
        )
        result: FusedResult = FusedResult(attributions=[attr])
        assert result.strategy_count == 1

    def test_strategy_count_excludes_failed(self) -> None:
        """Test strategy_count excludes failed attributions."""
        attrs: list[StrategyAttribution] = [
            _make_attribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=5,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.FULLTEXT,
                row_count=3,
                succeeded=False,
            ),
        ]
        result: FusedResult = FusedResult(attributions=attrs)
        assert result.strategy_count == 1

    def test_strategy_count_excludes_zero_rows(self) -> None:
        """Test strategy_count excludes attributions with row_count=0."""
        attrs: list[StrategyAttribution] = [
            _make_attribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=5,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.VECTOR,
                row_count=0,
                succeeded=True,
            ),
        ]
        result: FusedResult = FusedResult(attributions=attrs)
        assert result.strategy_count == 1

    def test_strategy_count_multiple(self) -> None:
        """Test strategy_count with multiple contributing strategies."""
        attrs: list[StrategyAttribution] = [
            _make_attribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=5,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.FULLTEXT,
                row_count=3,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.VECTOR,
                row_count=2,
                succeeded=True,
            ),
        ]
        result: FusedResult = FusedResult(attributions=attrs)
        assert result.strategy_count == 3

    # -- is_multi_strategy property --

    def test_is_multi_strategy_false_no_attributions(self) -> None:
        """Test is_multi_strategy is False with no attributions."""
        result: FusedResult = FusedResult()
        assert result.is_multi_strategy is False

    def test_is_multi_strategy_false_single(self) -> None:
        """Test is_multi_strategy is False with one contributing."""
        attr: StrategyAttribution = _make_attribution(
            row_count=5,
            succeeded=True,
        )
        result: FusedResult = FusedResult(attributions=[attr])
        assert result.is_multi_strategy is False

    def test_is_multi_strategy_true(self) -> None:
        """Test is_multi_strategy True with two+ contributing."""
        attrs: list[StrategyAttribution] = [
            _make_attribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=5,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.FULLTEXT,
                row_count=3,
                succeeded=True,
            ),
        ]
        result: FusedResult = FusedResult(attributions=attrs)
        assert result.is_multi_strategy is True

    def test_is_multi_strategy_false_when_only_one_succeeds(
        self,
    ) -> None:
        """Test is_multi_strategy False when only one succeeds."""
        attrs: list[StrategyAttribution] = [
            _make_attribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=5,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.FULLTEXT,
                row_count=0,
                succeeded=True,
            ),
            _make_attribution(
                strategy_type=StrategyType.VECTOR,
                row_count=2,
                succeeded=False,
            ),
        ]
        result: FusedResult = FusedResult(attributions=attrs)
        assert result.is_multi_strategy is False


# ---------------------------------------------------------------------------
# StrategyDispatchPlan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStrategyDispatchPlan:
    """Test StrategyDispatchPlan validation and model_validator."""

    def test_valid_structured_only(self) -> None:
        """Test plan with only STRUCTURED strategy."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[StrategyType.STRUCTURED],
        )
        assert plan.strategies == [StrategyType.STRUCTURED]
        assert plan.is_aggregation is False
        assert plan.available_indexes == {}

    def test_valid_multi_strategy(self) -> None:
        """Test plan with STRUCTURED + FULLTEXT + VECTOR."""
        strategies: list[StrategyType] = [
            StrategyType.STRUCTURED,
            StrategyType.FULLTEXT,
            StrategyType.VECTOR,
        ]
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=strategies,
            is_aggregation=False,
            available_indexes={
                "products": ["filtering", "full_text_search"],
            },
        )
        assert len(plan.strategies) == 3
        assert plan.strategies[0] == StrategyType.STRUCTURED
        assert plan.available_indexes["products"] == [
            "filtering",
            "full_text_search",
        ]

    def test_frozen_prevents_mutation(self) -> None:
        """Test that frozen config prevents attribute changes."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[StrategyType.STRUCTURED],
        )
        with pytest.raises(ValidationError):
            plan.is_aggregation = True

    def test_structured_must_be_first_rejects_fulltext_first(
        self,
    ) -> None:
        """Test validator rejects FULLTEXT as first strategy."""
        with pytest.raises(ValidationError, match="FR-002"):
            StrategyDispatchPlan(
                strategies=[StrategyType.FULLTEXT],
            )

    def test_structured_must_be_first_rejects_vector_first(
        self,
    ) -> None:
        """Test validator rejects VECTOR as first strategy."""
        with pytest.raises(ValidationError, match="FR-002"):
            StrategyDispatchPlan(
                strategies=[
                    StrategyType.VECTOR,
                    StrategyType.STRUCTURED,
                ],
            )

    def test_strategies_min_length_rejects_empty(self) -> None:
        """Test strategies rejects empty list (min_length=1)."""
        with pytest.raises(ValidationError):
            StrategyDispatchPlan(strategies=[])

    def test_strategies_required(self) -> None:
        """Test that strategies field is required."""
        with pytest.raises(ValidationError):
            StrategyDispatchPlan()  # type: ignore[call-arg]

    def test_is_aggregation_default_false(self) -> None:
        """Test that is_aggregation defaults to False."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[StrategyType.STRUCTURED],
        )
        assert plan.is_aggregation is False

    def test_is_aggregation_true(self) -> None:
        """Test plan with is_aggregation set to True."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[StrategyType.STRUCTURED],
            is_aggregation=True,
        )
        assert plan.is_aggregation is True

    def test_available_indexes_default_empty(self) -> None:
        """Test that available_indexes defaults to empty dict."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[StrategyType.STRUCTURED],
        )
        assert plan.available_indexes == {}

    def test_available_indexes_populated(self) -> None:
        """Test plan with populated available_indexes."""
        indexes: dict[str, list[str]] = {
            "orders": ["filtering"],
            "products": [
                "filtering",
                "full_text_search",
                "vector_similarity",
            ],
        }
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[
                StrategyType.STRUCTURED,
                StrategyType.FULLTEXT,
            ],
            available_indexes=indexes,
        )
        assert "orders" in plan.available_indexes
        assert len(plan.available_indexes["products"]) == 3

    def test_structured_with_fulltext(self) -> None:
        """Test valid plan with STRUCTURED then FULLTEXT."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[
                StrategyType.STRUCTURED,
                StrategyType.FULLTEXT,
            ],
        )
        assert plan.strategies[0] == StrategyType.STRUCTURED
        assert plan.strategies[1] == StrategyType.FULLTEXT

    def test_structured_with_vector(self) -> None:
        """Test valid plan with STRUCTURED then VECTOR."""
        plan: StrategyDispatchPlan = StrategyDispatchPlan(
            strategies=[
                StrategyType.STRUCTURED,
                StrategyType.VECTOR,
            ],
        )
        assert plan.strategies[0] == StrategyType.STRUCTURED
        assert plan.strategies[1] == StrategyType.VECTOR

    def test_validator_error_message_contains_fr002(self) -> None:
        """Test that validator error mentions FR-002."""
        with pytest.raises(ValidationError, match="FR-002"):
            StrategyDispatchPlan(
                strategies=[
                    StrategyType.FULLTEXT,
                    StrategyType.STRUCTURED,
                ],
            )
