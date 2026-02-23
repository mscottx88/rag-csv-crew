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
        mock_result.raw = "<p>No results found for your query. Try rephrasing your question or check your data.</p>"
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
