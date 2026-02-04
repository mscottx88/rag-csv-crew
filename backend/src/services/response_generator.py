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

    def calculate_confidence_score(self, search_results: dict[str, Any]) -> float:
        """Calculate confidence score from hybrid search results.

        Analyzes the fused search results to determine query clarity based on:
        1. Top result score (50% weight) - How well does the best match score?
        2. Result diversity (50% weight) - How different are top scores?

        Args:
            search_results: Hybrid search results dict with fused_results list

        Returns:
            Confidence score between 0.0 and 1.0

        Heuristic:
            - High diversity (clear winner) = high confidence
            - Low diversity (ambiguous) = low confidence
            - Empty results = zero confidence
        """
        fused_results: list[dict[str, Any]] = search_results.get("fused_results", [])

        # No results => zero confidence
        if len(fused_results) == 0:
            return 0.0

        # Single result => confidence based on score alone
        if len(fused_results) == 1:
            top_score: float = fused_results[0].get("combined_score", 0.0)
            return min(top_score, 1.0)

        # Multiple results => combine top score with diversity
        top_score = fused_results[0].get("combined_score", 0.0)
        second_score: float = fused_results[1].get("combined_score", 0.0)

        # Diversity: difference between top two scores
        # Large gap = clear winner = high confidence
        # Small gap = ambiguous = low confidence
        diversity: float = max(0.0, top_score - second_score)

        # Combined confidence: 50% top score + 50% diversity
        confidence: float = (top_score * 0.5) + (diversity * 0.5)

        # Clamp to [0, 1] range
        return max(0.0, min(confidence, 1.0))

    def is_low_confidence(self, score: float, threshold: float = 0.6) -> bool:
        """Check if confidence score is below threshold.

        Args:
            score: Confidence score to check (0.0 to 1.0)
            threshold: Confidence threshold (default: 0.6 per FR-038)

        Returns:
            True if score is below threshold (low confidence)
        """
        return score < threshold

    def generate_clarification_request(
        self, query_text: str, search_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate clarification request with alternative column suggestions.

        When confidence is low, provides top 3-5 alternative columns for user
        to choose from, helping disambiguate their query.

        Args:
            query_text: Original user query text
            search_results: Hybrid search results with fused_results

        Returns:
            Dictionary with:
                - clarification_needed: bool (always True)
                - query_text: str (original query)
                - alternatives: list of top column suggestions
                - confidence_score: float
                - html_content: formatted HTML clarification message
        """
        fused_results: list[dict[str, Any]] = search_results.get("fused_results", [])
        confidence_score: float = self.calculate_confidence_score(search_results)

        # Handle empty results case
        if len(fused_results) == 0:
            html_content_empty: str = f"""<article>
<header>
<h1>No Matches Found</h1>
<p>Your query: <strong>{query_text}</strong></p>
<p>Unfortunately, I couldn't find any columns matching your query.</p>
</header>
<section>
<h2>Suggestions:</h2>
<ul>
<li>Try using different keywords or synonyms</li>
<li>Check if the column exists in your uploaded datasets</li>
<li>Try a more general search term</li>
</ul>
</section>
<footer>
<p><em>Confidence score: 0.00</em></p>
</footer>
</article>"""
            return {
                "clarification_needed": True,
                "query_text": query_text,
                "alternatives": [],
                "confidence_score": 0.0,
                "html_content": html_content_empty,
                "suggestions": ["Try different keywords", "Check dataset", "Use broader terms"],
            }

        # Take top 3-5 results as alternatives (or fewer if not enough results)
        num_alternatives: int = min(5, max(3, len(fused_results)))
        alternatives: list[dict[str, Any]] = []

        # Normalize alternatives to include "score" field for backwards compatibility
        for result in fused_results[:num_alternatives]:
            alt: dict[str, Any] = result.copy()
            # Add "score" as alias for "combined_score" if not present
            if "score" not in alt and "combined_score" in alt:
                alt["score"] = alt["combined_score"]
            alternatives.append(alt)

        # Generate HTML clarification message
        html_parts: list[str] = [
            "<article>",
            "<header>",
            f"<h1>Clarification Needed</h1>",
            f"<p>Your query: <strong>{query_text}</strong></p>",
            f"<p>I found multiple possible matches. Did you mean one of these columns?</p>",
            "</header>",
            "<section>",
            "<ul>",
        ]

        for alt in alternatives:
            column_name: str = alt.get("column_name", "unknown")
            dataset_id: str = alt.get("dataset_id", "unknown")
            score: float = alt.get("combined_score", 0.0)
            description: str | None = alt.get("description")

            # Build HTML for this alternative
            if dataset_id != "unknown":
                html_item: str = f'<li><strong>{column_name}</strong> (dataset: {dataset_id}, relevance: {score:.2f})'
            else:
                html_item = f'<li><strong>{column_name}</strong> (relevance: {score:.2f})'

            # Add description if available
            if description:
                html_item += f'<br><em>{description}</em>'

            html_item += '</li>'
            html_parts.append(html_item)

        html_parts.extend([
            "</ul>",
            "</section>",
            "<section>",
            "<h2>Refinement Suggestions:</h2>",
            "<ul>",
            "<li>Specify the dataset name to narrow results</li>",
            "<li>Use more specific column names</li>",
            "<li>Include additional context in your query</li>",
            "</ul>",
            "</section>",
            "<footer>",
            f"<p><em>Confidence score: {confidence_score:.2f}</em></p>",
            "</footer>",
            "</article>",
        ])

        html_content: str = "\n".join(html_parts)

        # Generate refinement suggestions
        suggestions: list[str] = [
            "Specify dataset name",
            "Use more specific terms",
            "Include additional context"
        ]

        return {
            "clarification_needed": True,
            "query_text": query_text,
            "alternatives": alternatives,
            "confidence_score": confidence_score,
            "html_content": html_content,
            "suggestions": suggestions,
        }

    def generate_html_response(
        self,
        query_text: str,
        query_results: dict[str, Any],
        _query_id: UUID | str,
        confidence_threshold: float = 0.6
    ) -> dict[str, Any]:
        """Generate HTML response from SQL query results or hybrid search results.

        Args:
            query_text: Original user question
            query_results: Either SQL query results OR hybrid search results with fused_results
            _query_id: Query ID (UUID or string, currently unused)
            confidence_threshold: Confidence threshold for clarification (default: 0.6)

        Returns:
            Dictionary with html_content, plain_text, confidence_score
            OR clarification request if confidence is low

        Note: _query_id parameter is reserved for future use but currently unused.

        Constitutional Compliance:
        - Uses CrewAI synchronously (not async)
        - Thread-based execution
        """
        # Check if query_results contains hybrid search results (fused_results)
        if "fused_results" in query_results:
            # This is hybrid search results - check confidence
            confidence_score: float = self.calculate_confidence_score(query_results)

            if self.is_low_confidence(confidence_score, threshold=confidence_threshold):
                # Return clarification request
                clarification: dict[str, Any] = self.generate_clarification_request(
                    query_text=query_text,
                    search_results=query_results
                )
                # Add plain_text version
                plain_text: str = self._html_to_plain_text(clarification["html_content"])
                clarification["plain_text"] = plain_text
                return clarification

            # High confidence but we don't have SQL results yet
            # In full implementation, this would trigger SQL generation
            # For now, return a basic response indicating high confidence
            return {
                "html_content": f"<article><p>Query understood with {confidence_score:.0%} confidence.</p></article>",
                "plain_text": f"Query understood with {confidence_score:.0%} confidence.",
                "confidence_score": confidence_score,
                "clarification_needed": False,
            }

        # This is SQL query results (existing behavior)
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
        html_content_str: str = str(result.raw) if hasattr(result, "raw") else str(result)

        # Generate plain text version by stripping HTML tags
        plain_text_str: str = self._html_to_plain_text(html_content_str)

        # Calculate confidence score (simple heuristic for now)
        confidence_score_sql: float = self._calculate_confidence(query_results)

        return {
            "html_content": html_content_str,
            "plain_text": plain_text_str,
            "confidence_score": confidence_score_sql,
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
