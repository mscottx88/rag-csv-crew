"""HTML response generator service using CrewAI.

Generates readable HTML5 responses from SQL query results using CrewAI
Result Analyst agent per FR-008.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import re
from typing import Any
from uuid import UUID

from crewai import Crew

from backend.src.crew.agents import create_result_analyst_agent
from backend.src.crew.tasks import create_html_formatting_task


class ResponseGenerator:
    """Service for generating HTML responses from query results."""

    def generate_html_response(
        self, query_text: str, query_results: dict[str, Any], _query_id: UUID
    ) -> dict[str, Any]:
        """Generate HTML response from SQL query results.

        Args:
            query_text: Original user question
            query_results: Query results with rows, columns, row_count

        Returns:
            Dictionary with html_content, plain_text, confidence_score

        Note: _query_id parameter is reserved for future use but currently unused.

        Constitutional Compliance:
        - Uses CrewAI synchronously (not async)
        - Thread-based execution
        """
        # Create Result Analyst agent
        analyst_agent: Any = create_result_analyst_agent()

        # Create HTML formatting task
        task: Any = create_html_formatting_task(
            agent=analyst_agent, query_text=query_text, query_results=query_results
        )

        # Create crew and execute
        crew: Crew = Crew(agents=[analyst_agent], tasks=[task], verbose=False)

        # Execute crew (synchronous)
        result: Any = crew.kickoff()

        # Extract HTML content from result
        html_content: str = str(result.raw) if hasattr(result, "raw") else str(result)

        # Generate plain text version by stripping HTML tags
        plain_text: str = self._html_to_plain_text(html_content)

        # Calculate confidence score (simple heuristic for now)
        confidence_score: float = self._calculate_confidence(query_results)

        return {
            "html_content": html_content,
            "plain_text": plain_text,
            "confidence_score": confidence_score,
        }

    def _html_to_plain_text(self, html: str) -> str:
        """Convert HTML to plain text.

        Args:
            html: HTML content string

        Returns:
            Plain text version with tags removed
        """
        # Remove HTML tags
        text: str = re.sub(r"<[^>]+>", " ", html)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Trim
        return text.strip()

    def _calculate_confidence(self, query_results: dict[str, Any]) -> float:
        """Calculate confidence score for query results.

        Args:
            query_results: Query results dictionary

        Returns:
            Confidence score between 0.0 and 1.0

        Heuristic:
        - High confidence (0.9) if results are present
        - Medium confidence (0.6) if no results (ambiguous query)
        - Lower confidence for very large result sets (may be too broad)
        """
        row_count: int = query_results.get("row_count", 0)

        if row_count == 0:
            return 0.6  # Medium confidence - query may be too specific or ambiguous

        if row_count > 1000:
            return 0.7  # Query may be too broad

        return 0.9  # High confidence - reasonable result set
