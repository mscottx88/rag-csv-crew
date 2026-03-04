"""Unit tests for clarification request generation (T108-TEST).

Tests the clarification request generation system that suggests multiple
interpretations when query confidence is below threshold.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

import pytest

from backend.src.services.response_generator import ResponseGenerator


@pytest.mark.unit
class TestClarificationGeneration:
    """Unit tests for clarification request generation (T108)."""

    def test_clarification_generated_on_low_confidence(self) -> None:
        """Test clarification request generated when confidence below 60%.

        Validates:
        - Low confidence triggers clarification
        - Multiple interpretations suggested
        - User-friendly message format

        Success Criteria (T108):
        - Clarification triggered at <60% confidence
        - Multiple options presented
        """
        generator: ResponseGenerator = ResponseGenerator()

        # Ambiguous results (multiple similar scores)
        ambiguous_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.52},
                {"column_name": "income", "combined_score": 0.51},
                {"column_name": "earnings", "combined_score": 0.50},
            ]
        }

        response: dict[str, Any] = generator.generate_html_response(
            query_text="show me financial data",
            query_results=ambiguous_results,
            _query_id="test-query-id",
        )

        # Verify clarification generated
        html_content: str = response["html_content"]
        assert "clarification" in html_content.lower() or "did you mean" in html_content.lower()

        # Verify multiple options presented
        assert "revenue" in html_content
        assert "income" in html_content
        assert "earnings" in html_content

    def test_clarification_includes_top_n_alternatives(self) -> None:
        """Test clarification includes top N alternative interpretations.

        Validates:
        - Default: show top 3-5 alternatives
        - Alternatives ranked by score
        - Each alternative is clickable/selectable

        Success Criteria (T108):
        - 3-5 alternatives suggested
        - Ordered by relevance
        """
        generator: ResponseGenerator = ResponseGenerator()

        # Many ambiguous results
        ambiguous_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": f"column_{i}", "combined_score": 0.5 - i * 0.01} for i in range(10)
            ]
        }

        clarification: dict[str, Any] = generator.generate_clarification_request(
            query_text="show data", search_results=ambiguous_results
        )

        # Verify limited number of alternatives (3-5)
        alternatives: list[dict[str, Any]] = clarification["alternatives"]
        assert 3 <= len(alternatives) <= 5

        # Verify ordered by score (descending)
        for i in range(len(alternatives) - 1):
            assert alternatives[i]["score"] >= alternatives[i + 1]["score"]

    def test_clarification_html_formatting(self) -> None:
        """Test clarification request has user-friendly HTML format.

        Validates:
        - Clear heading explaining ambiguity
        - Bulleted list of alternatives
        - Each alternative shows column and dataset
        - Semantic HTML5 structure

        Success Criteria (T108):
        - HTML is well-formatted
        - Clear user guidance
        """
        generator: ResponseGenerator = ResponseGenerator()

        ambiguous_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "dataset_id": "sales.csv", "combined_score": 0.55},
                {"column_name": "income", "dataset_id": "finance.csv", "combined_score": 0.54},
            ]
        }

        response: dict[str, Any] = generator.generate_html_response(
            query_text="financial data", query_results=ambiguous_results, _query_id="test-query-id"
        )

        html_content: str = response["html_content"]

        # Verify HTML structure
        assert "<article>" in html_content or "<div>" in html_content
        assert "<ul>" in html_content or "<ol>" in html_content
        assert "<li>" in html_content

        # Verify content includes column names and datasets
        assert "revenue" in html_content
        assert "income" in html_content
        assert "sales.csv" in html_content or "sales" in html_content
        assert "finance.csv" in html_content or "finance" in html_content

    def test_clarification_plain_text_alternative(self) -> None:
        """Test clarification includes plain text for accessibility.

        Validates:
        - Plain text version generated
        - All alternatives listed
        - Readable without HTML

        Success Criteria (T108):
        - Plain text version available
        - Accessible formatting
        """
        generator: ResponseGenerator = ResponseGenerator()

        ambiguous_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "dataset_id": "ds1", "combined_score": 0.55},
                {"column_name": "income", "dataset_id": "ds2", "combined_score": 0.54},
            ]
        }

        response: dict[str, Any] = generator.generate_html_response(
            query_text="financial data", query_results=ambiguous_results, _query_id="test-query-id"
        )

        plain_text: str = response["plain_text"]

        # Verify plain text includes alternatives
        assert "revenue" in plain_text
        assert "income" in plain_text
        assert "clarification" in plain_text.lower() or "did you mean" in plain_text.lower()

    def test_clarification_suggests_refinement_strategies(self) -> None:
        """Test clarification suggests ways to refine the query.

        Validates:
        - Suggestions for more specific queries
        - Examples of refined queries
        - Helpful guidance for user

        Success Criteria (T108):
        - Refinement strategies included
        - Examples provided
        """
        generator: ResponseGenerator = ResponseGenerator()

        ambiguous_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.52},
                {"column_name": "income", "combined_score": 0.51},
            ]
        }

        clarification: dict[str, Any] = generator.generate_clarification_request(
            query_text="show me money", search_results=ambiguous_results
        )

        # Verify refinement suggestions
        assert "suggestions" in clarification or "refinement" in str(clarification).lower()

        # May include example queries
        if "example_queries" in clarification:
            examples: list[str] = clarification["example_queries"]
            assert len(examples) > 0

    def test_no_clarification_on_high_confidence(self) -> None:
        """Test no clarification generated when confidence above threshold.

        Validates:
        - High confidence (>60%) skips clarification
        - Direct answer provided instead
        - No unnecessary clarification prompts

        Success Criteria (T108):
        - High confidence => no clarification
        - Normal response generated
        """
        generator: ResponseGenerator = ResponseGenerator()

        # Clear high-confidence result
        clear_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.95},
                {"column_name": "sales", "combined_score": 0.45},
            ]
        }

        response: dict[str, Any] = generator.generate_html_response(
            query_text="show revenue", query_results=clear_results, _query_id="test-query-id"
        )

        html_content: str = response["html_content"]

        # Should NOT contain clarification
        assert "clarification" not in html_content.lower()
        assert "did you mean" not in html_content.lower()

    def test_clarification_shows_column_context(self) -> None:
        """Test clarification includes column metadata for context.

        Validates:
        - Column description or sample values shown
        - Dataset name included
        - Helps user distinguish options

        Success Criteria (T108):
        - Context information provided
        - Distinguishes similar columns
        """
        generator: ResponseGenerator = ResponseGenerator()

        ambiguous_results: dict[str, Any] = {
            "fused_results": [
                {
                    "column_name": "revenue",
                    "dataset_id": "sales.csv",
                    "combined_score": 0.55,
                    "description": "Total sales revenue",
                },
                {
                    "column_name": "revenue",
                    "dataset_id": "finance.csv",
                    "combined_score": 0.54,
                    "description": "Accounting revenue",
                },
            ]
        }

        response: dict[str, Any] = generator.generate_html_response(
            query_text="revenue", query_results=ambiguous_results, _query_id="test-query-id"
        )

        html_content: str = response["html_content"]

        # Verify context helps distinguish
        assert "sales.csv" in html_content
        assert "finance.csv" in html_content

        # May include descriptions
        if "description" in str(ambiguous_results["fused_results"][0]):
            assert "sales revenue" in html_content.lower() or "accounting" in html_content.lower()

    def test_clarification_empty_results_message(self) -> None:
        """Test clarification for empty results provides helpful message.

        Validates:
        - Empty results => "no matches found" message
        - Suggestions for alternative searches
        - Helpful guidance, not just error

        Success Criteria (T108):
        - Empty results handled gracefully
        - User guidance provided
        """
        generator: ResponseGenerator = ResponseGenerator()

        empty_results: dict[str, Any] = {"fused_results": []}

        response: dict[str, Any] = generator.generate_html_response(
            query_text="nonexistent_column_xyz",
            query_results=empty_results,
            _query_id="test-query-id",
        )

        html_content: str = response["html_content"]
        plain_text: str = response["plain_text"]

        # Verify helpful message
        assert "no matches" in html_content.lower() or "not found" in html_content.lower()
        assert "no matches" in plain_text.lower() or "not found" in plain_text.lower()

        # May include suggestions
        assert "try" in html_content.lower() or "suggestion" in html_content.lower()

    def test_clarification_configurable_threshold(self) -> None:
        """Test clarification threshold is configurable.

        Validates:
        - Default 60% threshold per FR-038
        - Can be adjusted for different use cases
        - Stricter thresholds (e.g., 70%) trigger more clarifications

        Success Criteria (T108):
        - Threshold parameter accepted
        - Behavior changes with different thresholds
        """
        generator: ResponseGenerator = ResponseGenerator()

        marginal_results: dict[str, Any] = {
            "fused_results": [{"column_name": "revenue", "combined_score": 0.65}]
        }

        # Default threshold (60%)
        response_60: dict[str, Any] = generator.generate_html_response(
            query_text="revenue",
            query_results=marginal_results,
            _query_id="test-query-id",
            confidence_threshold=0.6,
        )

        # Stricter threshold (70%)
        response_70: dict[str, Any] = generator.generate_html_response(
            query_text="revenue",
            query_results=marginal_results,
            _query_id="test-query-id",
            confidence_threshold=0.7,
        )

        # At 60%, should not trigger clarification
        assert "clarification" not in response_60["html_content"].lower()

        # At 70%, should trigger clarification
        assert "clarification" in response_70["html_content"].lower()
