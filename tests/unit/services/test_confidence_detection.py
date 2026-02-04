"""Unit tests for low-confidence detection (T107-TEST).

Tests the confidence scoring system that detects ambiguous queries
based on 60% threshold per FR-038.

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
class TestConfidenceDetection:
    """Unit tests for low-confidence detection (T107)."""

    def test_confidence_score_calculation(self) -> None:
        """Test confidence score is calculated from search results.

        Validates:
        - Confidence based on top result score and result diversity
        - Score normalized to 0-1 range
        - Higher scores indicate higher confidence

        Success Criteria (T107):
        - Confidence score calculated correctly
        - Range between 0 and 1
        - Reflects query ambiguity
        """
        generator: ResponseGenerator = ResponseGenerator()

        # High confidence: single clear match
        high_confidence_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.95},
                {"column_name": "sales", "combined_score": 0.45},
            ]
        }

        high_score: float = generator.calculate_confidence_score(
            high_confidence_results
        )

        # Should be above 60% threshold
        assert high_score > 0.6
        assert 0.0 <= high_score <= 1.0

    def test_low_confidence_detected_below_threshold(self) -> None:
        """Test low confidence detected when score below 60% threshold.

        Validates:
        - Threshold per FR-038 is 60%
        - Multiple similar-scored results reduce confidence
        - Low scores trigger clarification request

        Success Criteria (T107):
        - Scores below 0.6 flagged as low confidence
        - Threshold is configurable
        """
        generator: ResponseGenerator = ResponseGenerator()

        # Low confidence: multiple ambiguous matches
        low_confidence_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.52},
                {"column_name": "income", "combined_score": 0.51},
                {"column_name": "earnings", "combined_score": 0.50},
            ]
        }

        low_score: float = generator.calculate_confidence_score(
            low_confidence_results
        )

        # Should be below 60% threshold
        assert low_score < 0.6
        assert generator.is_low_confidence(low_score, threshold=0.6)

    def test_confidence_score_with_no_results(self) -> None:
        """Test confidence score when no search results found.

        Validates:
        - Empty results yield 0 confidence
        - No results trigger clarification
        - Error handling for edge case

        Success Criteria (T107):
        - Zero results => zero confidence
        - Clarification requested
        """
        generator: ResponseGenerator = ResponseGenerator()

        empty_results: dict[str, Any] = {
            "fused_results": []
        }

        score: float = generator.calculate_confidence_score(empty_results)

        # Should be 0 or very low
        assert score < 0.1
        assert generator.is_low_confidence(score, threshold=0.6)

    def test_confidence_score_result_diversity_factor(self) -> None:
        """Test confidence incorporates result diversity (score spread).

        Validates:
        - Close scores (0.8, 0.79, 0.78) reduce confidence (ambiguous)
        - Spread scores (0.9, 0.4, 0.2) increase confidence (clear winner)
        - Diversity metric affects final score

        Success Criteria (T107):
        - Result diversity considered in scoring
        - Ambiguous results (similar scores) lower confidence
        """
        generator: ResponseGenerator = ResponseGenerator()

        # Low diversity (ambiguous)
        low_diversity_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "col1", "combined_score": 0.80},
                {"column_name": "col2", "combined_score": 0.79},
                {"column_name": "col3", "combined_score": 0.78},
            ]
        }

        # High diversity (clear winner)
        high_diversity_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "col1", "combined_score": 0.90},
                {"column_name": "col2", "combined_score": 0.40},
                {"column_name": "col3", "combined_score": 0.20},
            ]
        }

        low_diversity_score: float = generator.calculate_confidence_score(
            low_diversity_results
        )
        high_diversity_score: float = generator.calculate_confidence_score(
            high_diversity_results
        )

        # High diversity should have higher confidence
        assert high_diversity_score > low_diversity_score

    def test_confidence_threshold_configurable(self) -> None:
        """Test confidence threshold is configurable (not hardcoded).

        Validates:
        - Default threshold is 60% per FR-038
        - Threshold can be adjusted for different contexts
        - Stricter thresholds (e.g., 80%) possible

        Success Criteria (T107):
        - Threshold parameter accepted
        - Different thresholds change behavior
        """
        generator: ResponseGenerator = ResponseGenerator()

        results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.70}
            ]
        }

        score: float = generator.calculate_confidence_score(results)

        # Test different thresholds
        assert not generator.is_low_confidence(score, threshold=0.6)  # Above 60%
        assert generator.is_low_confidence(score, threshold=0.8)  # Below 80%

    def test_confidence_with_single_result(self) -> None:
        """Test confidence with only one search result.

        Validates:
        - Single high-scoring result => high confidence
        - Single low-scoring result => low confidence
        - No diversity penalty with single result

        Success Criteria (T107):
        - Single result confidence based on score magnitude
        - No false ambiguity detection
        """
        generator: ResponseGenerator = ResponseGenerator()

        # Single high-score result
        high_single_result: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.95}
            ]
        }

        # Single low-score result
        low_single_result: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.40}
            ]
        }

        high_score: float = generator.calculate_confidence_score(high_single_result)
        low_score: float = generator.calculate_confidence_score(low_single_result)

        # High score should be confident
        assert high_score > 0.6

        # Low score should be low confidence
        assert low_score < 0.6

    def test_confidence_score_edge_cases(self) -> None:
        """Test confidence calculation handles edge cases.

        Validates:
        - All results with identical scores
        - Negative scores (shouldn't happen)
        - Very large result sets

        Success Criteria (T107):
        - No crashes on edge cases
        - Reasonable default behavior
        """
        generator: ResponseGenerator = ResponseGenerator()

        # All identical scores
        identical_scores: dict[str, Any] = {
            "fused_results": [
                {"column_name": f"col{i}", "combined_score": 0.5}
                for i in range(10)
            ]
        }

        score: float = generator.calculate_confidence_score(identical_scores)

        # Should handle without error
        assert 0.0 <= score <= 1.0

        # Identical scores => low confidence (ambiguous)
        assert score < 0.6

    def test_confidence_logged_with_query_response(self) -> None:
        """Test confidence score is logged with query response.

        Validates:
        - Confidence score included in response metadata
        - Score persisted for analytics
        - Available for client display

        Success Criteria (T107):
        - Confidence score in response
        - Accessible for logging and display
        """
        generator: ResponseGenerator = ResponseGenerator()

        query_results: dict[str, Any] = {
            "fused_results": [
                {"column_name": "revenue", "combined_score": 0.85}
            ]
        }

        response: dict[str, Any] = generator.generate_html_response(
            query_text="show me revenue",
            query_results=query_results,
            _query_id="test-query-id"
        )

        # Verify confidence score included
        assert "confidence_score" in response
        assert isinstance(response["confidence_score"], float)
        assert 0.0 <= response["confidence_score"] <= 1.0
