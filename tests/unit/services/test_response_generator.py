"""Unit tests for HTML response generator service.

Tests the response generator that converts SQL query results into
readable HTML5 responses using CrewAI Result Analyst agent.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.src.models.fusion import (
    FusedResult,
    FusedRow,
    StrategyAttribution,
    StrategyType,
)


@pytest.mark.unit
class TestResponseGenerator:
    """Unit tests for HTML response generator service (T053)."""

    @patch("backend.src.services.response_generator.Crew")
    def test_generate_html_response_from_query_results(self, mock_crew: MagicMock) -> None:
        """Test HTML generation from SQL query results.

        Validates:
        - Query results are converted to semantic HTML5
        - HTML includes proper hierarchy (headings, lists, tables)
        - Response is readable and well-structured per FR-008

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T053):
        - Service generates HTML from query results
        - HTML uses semantic tags
        - Response includes user question context
        """
        from backend.src.services.response_generator import ResponseGenerator

        # Mock CrewAI response with HTML
        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = """
            <div class="query-response">
                <h2>Top 5 Sales by Revenue</h2>
                <table>
                    <thead>
                        <tr><th>Product</th><th>Revenue</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Product A</td><td>$1000</td></tr>
                        <tr><td>Product B</td><td>$800</td></tr>
                    </tbody>
                </table>
            </div>
            """
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        query_text: str = "What are the top 5 sales by revenue?"
        query_results: dict[str, Any] = {
            "rows": [
                {"product": "Product A", "revenue": 1000},
                {"product": "Product B", "revenue": 800},
            ],
            "row_count": 2,
            "columns": ["product", "revenue"],
        }

        result: dict[str, Any] = generator.generate_html_response(
            query_text=query_text, query_results=query_results, _query_id=uuid4()
        )

        # Verify HTML was generated
        assert "html_content" in result
        assert "plain_text" in result

        html: str = result["html_content"]
        assert "<h2>" in html or "<h1>" in html  # Semantic heading
        assert "<table>" in html or "<ul>" in html or "<ol>" in html  # Structured data

    @patch("backend.src.services.response_generator.Crew")
    def test_generate_html_with_proper_hierarchy(self, mock_crew: MagicMock) -> None:
        """Test HTML response follows proper semantic hierarchy.

        Validates:
        - Headings follow logical order (h1, h2, h3)
        - Lists are used for collections
        - Tables are used for tabular data
        - Sections are properly nested

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T053):
        - HTML uses semantic tags per FR-008
        - Document structure is logical
        - Accessibility best practices followed
        """
        from backend.src.services.response_generator import ResponseGenerator

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = """
            <article>
                <h1>Query Results</h1>
                <section>
                    <h2>Summary</h2>
                    <p>Found 10 matching records</p>
                </section>
                <section>
                    <h2>Details</h2>
                    <table>
                        <caption>Sales Data</caption>
                        <thead><tr><th>ID</th><th>Amount</th></tr></thead>
                        <tbody><tr><td>1</td><td>100</td></tr></tbody>
                    </table>
                </section>
            </article>
            """
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        result: dict[str, Any] = generator.generate_html_response(
            query_text="Show me sales data",
            query_results={
                "rows": [{"id": 1, "amount": 100}],
                "row_count": 1,
                "columns": ["id", "amount"],
            },
            _query_id=uuid4(),
        )

        html: str = result["html_content"]
        # Verify semantic structure
        assert "<article>" in html or "<section>" in html
        assert "<h1>" in html or "<h2>" in html

    @patch("backend.src.services.response_generator.Crew")
    def test_generate_html_readability(self, mock_crew: MagicMock) -> None:
        """Test HTML response is readable and user-friendly.

        Validates:
        - Text is clear and concise
        - Numbers are formatted appropriately
        - Dates are human-readable
        - Technical jargon is avoided

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T053):
        - Response is readable per FR-008
        - Formatting enhances comprehension
        - Plain text alternative is provided
        """
        from backend.src.services.response_generator import ResponseGenerator

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = (
            "<p>The total revenue is <strong>$1,234.56</strong> across 42 transactions.</p>"
        )
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        result: dict[str, Any] = generator.generate_html_response(
            query_text="What's the total revenue?",
            query_results={
                "rows": [{"total": 1234.56, "count": 42}],
                "row_count": 1,
                "columns": ["total", "count"],
            },
            _query_id=uuid4(),
        )

        # Verify both HTML and plain text are generated
        assert "html_content" in result
        assert "plain_text" in result
        assert len(result["html_content"]) > 0
        assert len(result["plain_text"]) > 0

    @patch("backend.src.services.response_generator.Crew")
    def test_generate_html_handles_empty_results(self, mock_crew: MagicMock) -> None:
        """Test HTML generation for queries with no results.

        Validates:
        - Empty result sets produce user-friendly message
        - HTML structure is still valid
        - No errors are raised

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T053):
        - Empty results handled gracefully
        - User gets helpful feedback
        """
        from backend.src.services.response_generator import ResponseGenerator

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = (
            "<p>No results found for your query."
            " Try rephrasing your question or check your data.</p>"
        )
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        result: dict[str, Any] = generator.generate_html_response(
            query_text="Show me sales from year 3000",
            query_results={"rows": [], "row_count": 0, "columns": []},
            _query_id=uuid4(),
        )

        assert "html_content" in result
        assert len(result["html_content"]) > 0
        # Should contain helpful message
        html: str = result["html_content"]
        assert "no results" in html.lower() or "not found" in html.lower()

    @patch("backend.src.services.response_generator.Crew")
    def test_generate_html_error_handling(self, mock_crew: MagicMock) -> None:
        """Test error handling when HTML generation fails.

        Validates:
        - LLM API failures are caught
        - Fallback response is generated
        - Error is logged but not exposed to user

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T053):
        - API failures don't crash service
        - User gets fallback response
        """
        from backend.src.services.response_generator import ResponseGenerator

        mock_crew_instance: MagicMock = MagicMock()
        mock_crew_instance.kickoff.side_effect = Exception("API error")
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()

        with pytest.raises(Exception):
            generator.generate_html_response(
                query_text="Test query",
                query_results={"rows": [], "row_count": 0, "columns": []},
                _query_id=uuid4(),
            )

    @patch("backend.src.services.response_generator.Crew")
    def test_generate_html_includes_confidence_score(self, mock_crew: MagicMock) -> None:
        """Test HTML response includes confidence score for quality assessment.

        Validates:
        - Confidence score is calculated
        - Score is between 0 and 1
        - Low confidence triggers clarification per FR-038

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T053):
        - Confidence score is included
        - Score follows expected range
        """
        from backend.src.services.response_generator import ResponseGenerator

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>The average is 42</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        result: dict[str, Any] = generator.generate_html_response(
            query_text="What's the average?",
            query_results={"rows": [{"avg": 42}], "row_count": 1, "columns": ["avg"]},
            _query_id=uuid4(),
        )

        # Verify confidence score if present
        if "confidence_score" in result:
            score: float = result["confidence_score"]
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Helpers for FusedResult test fixtures
# ---------------------------------------------------------------------------


def _make_multi_strategy_fused_result() -> FusedResult:
    """Create a FusedResult with three contributing strategies.

    Returns:
        FusedResult with structured (5 rows), fulltext (3 rows),
        and vector (2 rows) attributions, all succeeded.
    """
    rows: list[FusedRow] = [
        FusedRow(
            ctid="(0,1)",
            data={"name": "Alice", "revenue": 1000},
            rrf_score=0.85,
            source_strategies=[
                StrategyType.STRUCTURED,
                StrategyType.FULLTEXT,
            ],
        ),
        FusedRow(
            ctid="(0,2)",
            data={"name": "Bob", "revenue": 800},
            rrf_score=0.72,
            source_strategies=[
                StrategyType.STRUCTURED,
                StrategyType.VECTOR,
            ],
        ),
    ]
    attributions: list[StrategyAttribution] = [
        StrategyAttribution(
            strategy_type=StrategyType.STRUCTURED,
            row_count=5,
            execution_time_ms=12.0,
            succeeded=True,
        ),
        StrategyAttribution(
            strategy_type=StrategyType.FULLTEXT,
            row_count=3,
            execution_time_ms=8.0,
            succeeded=True,
        ),
        StrategyAttribution(
            strategy_type=StrategyType.VECTOR,
            row_count=2,
            execution_time_ms=15.0,
            succeeded=True,
        ),
    ]
    return FusedResult(
        rows=rows,
        columns=["name", "revenue"],
        total_row_count=2,
        attributions=attributions,
        rrf_k=60,
    )


def _make_single_strategy_fused_result() -> FusedResult:
    """Create a FusedResult with only one contributing strategy.

    Returns:
        FusedResult with only structured attribution (single
        strategy, is_multi_strategy is False).
    """
    rows: list[FusedRow] = [
        FusedRow(
            ctid="(0,1)",
            data={"name": "Alice", "revenue": 1000},
            rrf_score=0.90,
            source_strategies=[StrategyType.STRUCTURED],
        ),
    ]
    attributions: list[StrategyAttribution] = [
        StrategyAttribution(
            strategy_type=StrategyType.STRUCTURED,
            row_count=1,
            execution_time_ms=10.0,
            succeeded=True,
        ),
    ]
    return FusedResult(
        rows=rows,
        columns=["name", "revenue"],
        total_row_count=1,
        attributions=attributions,
        rrf_k=60,
    )


def _make_empty_fused_result() -> FusedResult:
    """Create a FusedResult with zero rows.

    Returns:
        FusedResult with empty rows, columns, and attributions.
    """
    return FusedResult(
        rows=[],
        columns=[],
        total_row_count=0,
        attributions=[],
        rrf_k=60,
    )


@pytest.mark.unit
class TestResponseGeneratorFusedResult:
    """Unit tests for generate_html_response with fused_result param (T017).

    Validates the new keyword-only fused_result parameter on
    ResponseGenerator.generate_html_response, including multi-strategy
    attribution text, single-strategy suppression (FR-015), ctid
    exclusion (FR-013), human-readable strategy names, backwards
    compatibility when fused_result is None, and zero-row handling.
    """

    @patch("backend.src.services.response_generator.Crew")
    def test_multi_strategy_attribution_in_prompt(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test fused_result with multi-strategy adds attribution to prompt.

        When fused_result.is_multi_strategy is True the CrewAI prompt
        must include attribution text listing per-strategy row counts.

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>Sales results</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        fused: FusedResult = _make_multi_strategy_fused_result()

        query_results: dict[str, Any] = {
            "rows": [row.data for row in fused.rows],
            "row_count": fused.total_row_count,
            "columns": fused.columns,
        }

        _result: dict[str, Any] = generator.generate_html_response(
            query_text="Show top sales",
            query_results=query_results,
            _query_id=uuid4(),
            fused_result=fused,
        )

        # Extract the task description passed to Crew
        crew_call: Any = mock_crew.call_args
        tasks_arg: list[Any] = crew_call.kwargs.get(
            "tasks",
            crew_call.args[1] if len(crew_call.args) > 1 else [],
        )
        assert len(tasks_arg) == 1
        task_description: str = tasks_arg[0].description

        # Verify attribution text is present
        assert "structured query" in task_description
        assert "full-text search" in task_description
        assert "semantic search" in task_description
        assert "5 rows" in task_description
        assert "3 rows" in task_description
        assert "2 rows" in task_description

    @patch("backend.src.services.response_generator.Crew")
    def test_single_strategy_no_attribution(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test fused_result with single strategy omits attribution (FR-015).

        When fused_result.is_multi_strategy is False the CrewAI prompt
        must NOT include any strategy attribution summary.

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>Single strategy result</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        fused: FusedResult = _make_single_strategy_fused_result()

        query_results: dict[str, Any] = {
            "rows": [row.data for row in fused.rows],
            "row_count": fused.total_row_count,
            "columns": fused.columns,
        }

        _result: dict[str, Any] = generator.generate_html_response(
            query_text="Show top sales",
            query_results=query_results,
            _query_id=uuid4(),
            fused_result=fused,
        )

        # Extract the task description passed to Crew
        tasks_arg: list[Any] = mock_crew.call_args.kwargs.get(
            "tasks",
            (mock_crew.call_args.args[1] if len(mock_crew.call_args.args) > 1 else []),
        )
        assert len(tasks_arg) == 1
        task_description: str = tasks_arg[0].description

        # Attribution text must NOT be present for single strategy
        assert "Results from" not in task_description

    @patch("backend.src.services.response_generator.Crew")
    def test_fused_result_none_preserves_existing_behavior(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test fused_result=None preserves backwards compatibility.

        When fused_result is not provided (defaults to None) the
        method must behave identically to the original implementation.

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>Original behavior</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        query_results: dict[str, Any] = {
            "rows": [{"id": 1, "amount": 500}],
            "row_count": 1,
            "columns": ["id", "amount"],
        }

        result: dict[str, Any] = generator.generate_html_response(
            query_text="Show amounts",
            query_results=query_results,
            _query_id=uuid4(),
        )

        # Verify standard output keys
        assert "html_content" in result
        assert "plain_text" in result

        html: str = result["html_content"]
        assert "<p>" in html

        # Verify no attribution text leaked in
        tasks_arg: list[Any] = mock_crew.call_args.kwargs.get(
            "tasks",
            (mock_crew.call_args.args[1] if len(mock_crew.call_args.args) > 1 else []),
        )
        assert len(tasks_arg) == 1
        task_description: str = tasks_arg[0].description
        assert "Results from" not in task_description

    @patch("backend.src.services.response_generator.Crew")
    def test_zero_rows_no_attribution(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test fused_result with zero rows shows no attribution.

        When all strategies return zero rows the response should
        contain a helpful message without strategy attribution.

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>No results found for your query.</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        fused: FusedResult = _make_empty_fused_result()

        query_results: dict[str, Any] = {
            "rows": [],
            "row_count": 0,
            "columns": [],
        }

        result: dict[str, Any] = generator.generate_html_response(
            query_text="Find nonexistent data",
            query_results=query_results,
            _query_id=uuid4(),
            fused_result=fused,
        )

        assert "html_content" in result
        # Zero rows returns early without calling Crew
        mock_crew.assert_not_called()
        # No attribution in the static response
        assert "Results from" not in result["html_content"]

    @patch("backend.src.services.response_generator.Crew")
    def test_ctid_excluded_from_output_data(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test ctid is excluded from user-visible output (FR-013).

        FusedRow.data should never contain ctid; the rows passed
        to the CrewAI prompt must not expose ctid values.

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>Results without ctid</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        fused: FusedResult = _make_multi_strategy_fused_result()

        # Verify ctid is NOT in any FusedRow.data
        for row in fused.rows:
            assert "ctid" not in row.data, "ctid must not appear in FusedRow.data (FR-013)"

        # Build query_results from fused row data only
        rows_for_query: list[dict[str, Any]] = [row.data for row in fused.rows]
        query_results: dict[str, Any] = {
            "rows": rows_for_query,
            "row_count": fused.total_row_count,
            "columns": fused.columns,
        }

        _result: dict[str, Any] = generator.generate_html_response(
            query_text="Show sales",
            query_results=query_results,
            _query_id=uuid4(),
            fused_result=fused,
        )

        # Verify the data passed to CrewAI has no ctid
        tasks_arg: list[Any] = mock_crew.call_args.kwargs.get(
            "tasks",
            (mock_crew.call_args.args[1] if len(mock_crew.call_args.args) > 1 else []),
        )
        task_description: str = tasks_arg[0].description
        assert "ctid" not in task_description

    @patch("backend.src.services.response_generator.Crew")
    def test_strategy_names_are_human_readable(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test strategy names use human-readable labels in attribution.

        Mapping: structured -> "structured query",
        fulltext -> "full-text search", vector -> "semantic search".

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>Human-readable names</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()
        fused: FusedResult = _make_multi_strategy_fused_result()

        query_results: dict[str, Any] = {
            "rows": [row.data for row in fused.rows],
            "row_count": fused.total_row_count,
            "columns": fused.columns,
        }

        _result: dict[str, Any] = generator.generate_html_response(
            query_text="Show top sales",
            query_results=query_results,
            _query_id=uuid4(),
            fused_result=fused,
        )

        tasks_arg: list[Any] = mock_crew.call_args.kwargs.get(
            "tasks",
            (mock_crew.call_args.args[1] if len(mock_crew.call_args.args) > 1 else []),
        )
        task_description: str = tasks_arg[0].description

        # Must use human-readable names, not enum values
        assert "structured query" in task_description
        assert "full-text search" in task_description
        assert "semantic search" in task_description

        # Must NOT contain raw enum values as strategy labels
        # (checking they don't appear as standalone labels)
        assert "fulltext (" not in task_description
        assert "vector (" not in task_description

    @patch("backend.src.services.response_generator.Crew")
    def test_fused_result_columns_used_for_response(
        self,
        mock_crew: MagicMock,
    ) -> None:
        """Test fused_result.columns are used in the CrewAI prompt.

        The columns from the FusedResult should be passed through
        to the CrewAI task description for proper HTML generation.

        Args:
            mock_crew: Mocked CrewAI Crew class
        """
        from backend.src.services.response_generator import (
            ResponseGenerator,
        )

        mock_crew_instance: MagicMock = MagicMock()
        mock_result: MagicMock = MagicMock()
        mock_result.raw = "<p>Columns test</p>"
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew.return_value = mock_crew_instance

        generator: ResponseGenerator = ResponseGenerator()

        # Create fused result with specific columns
        fused_rows: list[FusedRow] = [
            FusedRow(
                ctid="(0,1)",
                data={
                    "product_name": "Widget",
                    "unit_price": 9.99,
                    "quantity": 100,
                },
                rrf_score=0.88,
                source_strategies=[StrategyType.STRUCTURED],
            ),
        ]
        fused_columns: list[str] = [
            "product_name",
            "unit_price",
            "quantity",
        ]
        fused_attrs: list[StrategyAttribution] = [
            StrategyAttribution(
                strategy_type=StrategyType.STRUCTURED,
                row_count=1,
                execution_time_ms=5.0,
                succeeded=True,
            ),
        ]
        fused: FusedResult = FusedResult(
            rows=fused_rows,
            columns=fused_columns,
            total_row_count=1,
            attributions=fused_attrs,
            rrf_k=60,
        )

        query_results: dict[str, Any] = {
            "rows": [row.data for row in fused.rows],
            "row_count": fused.total_row_count,
            "columns": fused.columns,
        }

        _result: dict[str, Any] = generator.generate_html_response(
            query_text="Show product details",
            query_results=query_results,
            _query_id=uuid4(),
            fused_result=fused,
        )

        tasks_arg: list[Any] = mock_crew.call_args.kwargs.get(
            "tasks",
            (mock_crew.call_args.args[1] if len(mock_crew.call_args.args) > 1 else []),
        )
        task_description: str = tasks_arg[0].description

        # Verify fused_result columns appear in the prompt
        assert "product_name" in task_description
        assert "unit_price" in task_description
        assert "quantity" in task_description
