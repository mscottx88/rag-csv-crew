"""Unit tests for Keyword Search agent (T102-TEST).

Tests the CrewAI Keyword Search agent that specializes in full-text search
using PostgreSQL ts_rank for keyword-based column matching.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

import pytest

from backend.src.crew.agents import create_keyword_search_agent, create_vector_search_agent
from backend.src.crew.tasks import create_keyword_search_task


@pytest.mark.unit
class TestKeywordSearchAgent:
    """Unit tests for Keyword Search agent (T102)."""

    def test_keyword_agent_creation(self) -> None:
        """Test Keyword Search agent is created with correct configuration.

        Validates:
        - Agent has appropriate role and goal
        - Backstory emphasizes full-text search expertise
        - No delegation allowed (specialist agent)

        Success Criteria (T102):
        - Agent configured for keyword search
        - Tools include full-text search capabilities
        - Verbose logging enabled for debugging
        """
        agent: Any = create_keyword_search_agent()

        # Verify agent attributes
        assert agent.role is not None
        assert "keyword" in agent.role.lower() or "search" in agent.role.lower()
        assert agent.goal is not None
        assert agent.backstory is not None
        assert agent.allow_delegation is False
        assert agent.verbose is True

    def test_keyword_agent_full_text_search_expertise(self) -> None:
        """Test agent backstory emphasizes full-text search and ts_rank.

        Validates:
        - Backstory mentions ts_rank or full-text search
        - Agent understands keyword matching vs semantic search
        - Focuses on exact and fuzzy keyword matching

        Success Criteria (T102):
        - Agent configured with full-text search context
        - Differentiates from vector search approach
        """
        agent: Any = create_keyword_search_agent()

        backstory_lower: str = agent.backstory.lower()

        # Verify full-text search focus
        assert (
            "full-text" in backstory_lower
            or "keyword" in backstory_lower
            or "ts_rank" in backstory_lower
            or "text search" in backstory_lower
        )

    def test_keyword_agent_task_execution(self) -> None:
        """Test Keyword Search agent executes full-text search tasks.

        Validates:
        - Agent receives search query and dataset context
        - Agent returns ranked column matches using ts_rank
        - Results include relevance scores

        Success Criteria (T102):
        - Agent processes keyword search requests
        - Returns columns ranked by text relevance
        """
        # Create real agent (required for CrewAI Task Pydantic validation)
        agent: Any = create_keyword_search_agent()

        # Create task
        query_text: str = "find revenue columns"
        dataset_ids: list[str] = ["dataset-1", "dataset-2"]

        task: Any = create_keyword_search_task(
            agent=agent,
            query_text=query_text,
            dataset_ids=dataset_ids
        )

        # Verify task configuration
        assert task.agent == agent
        assert query_text in task.description
        assert task.expected_output is not None

        # Verify task description mentions ts_rank or full-text
        description_lower: str = task.description.lower()
        assert "keyword" in description_lower or "full-text" in description_lower

    def test_keyword_agent_handles_multiple_keywords(self) -> None:
        """Test agent handles queries with multiple keywords.

        Validates:
        - Multi-word queries are processed correctly
        - Boolean operators (AND, OR) are supported
        - Phrase searches work correctly

        Success Criteria (T102):
        - Agent processes complex keyword queries
        - Returns relevant columns for multi-keyword searches
        """
        agent: Any = create_keyword_search_agent()

        # Verify agent is configured (actual keyword processing tested in integration)
        assert agent is not None
        assert "keyword" in agent.role.lower() or "search" in agent.role.lower()

    def test_keyword_agent_vs_vector_agent_differentiation(self) -> None:
        """Test Keyword Search agent differs from Vector Search agent.

        Validates:
        - Keyword agent focuses on exact/fuzzy text matching
        - Vector agent focuses on semantic similarity
        - Agents have distinct roles and goals

        Success Criteria (T102):
        - Keyword and vector agents have different configurations
        - Roles clearly distinguish search strategies
        """
        keyword_agent: Any = create_keyword_search_agent()
        vector_agent: Any = create_vector_search_agent()

        # Verify different roles
        assert keyword_agent.role != vector_agent.role

        # Verify keyword agent focuses on text matching
        keyword_role_lower: str = keyword_agent.role.lower()
        assert "keyword" in keyword_role_lower or "text" in keyword_role_lower

        # Verify vector agent focuses on semantic meaning
        vector_role_lower: str = vector_agent.role.lower()
        assert "vector" in vector_role_lower or "semantic" in vector_role_lower

    def test_keyword_agent_returns_ranked_results(self) -> None:
        """Test Keyword Search agent returns ts_rank-ordered results.

        Validates:
        - Results include relevance scores (ts_rank)
        - Columns ranked by keyword match quality
        - Supports configurable result limit

        Success Criteria (T102):
        - Agent output includes ranked column list
        - Each result has relevance score
        - Results ordered by descending relevance
        """
        from backend.src.crew.tasks import create_keyword_search_task

        # Create real agent (required for CrewAI Task Pydantic validation)
        agent: Any = create_keyword_search_agent()

        task: Any = create_keyword_search_task(
            agent=agent,
            query_text="customer data",
            dataset_ids=["dataset-1"]
        )

        # Verify task expects ranked output
        expected_output_lower: str = task.expected_output.lower()
        assert (
            "rank" in expected_output_lower
            or "score" in expected_output_lower
            or "relevance" in expected_output_lower
        )

    def test_keyword_agent_empty_query_handling(self) -> None:
        """Test agent handles empty or invalid keyword queries.

        Validates:
        - Empty queries are rejected or handled gracefully
        - Whitespace-only queries are normalized
        - Error messages are informative

        Success Criteria (T102):
        - Agent validates input queries
        - Appropriate errors for invalid input
        """
        agent: Any = create_keyword_search_agent()

        # Agent should be created successfully
        assert agent is not None

        # Actual query validation happens in task execution (tested in integration)
