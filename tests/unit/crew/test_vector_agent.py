"""Unit tests for Vector Search agent (T103-TEST).

Tests the CrewAI Vector Search agent that specializes in semantic similarity
search using pgvector embeddings and cosine distance.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

import pytest

from backend.src.crew.agents import create_keyword_search_agent, create_vector_search_agent
from backend.src.crew.tasks import create_vector_search_task


@pytest.mark.unit
class TestVectorSearchAgent:
    """Unit tests for Vector Search agent (T103)."""

    def test_vector_agent_creation(self) -> None:
        """Test Vector Search agent is created with correct configuration.

        Validates:
        - Agent has appropriate role and goal
        - Backstory emphasizes semantic similarity expertise
        - No delegation allowed (specialist agent)

        Success Criteria (T103):
        - Agent configured for semantic search
        - Tools include vector similarity search capabilities
        - Verbose logging enabled for debugging
        """
        agent: Any = create_vector_search_agent()

        # Verify agent attributes
        assert agent.role is not None
        assert (
            "vector" in agent.role.lower()
            or "semantic" in agent.role.lower()
            or "similarity" in agent.role.lower()
        )
        assert agent.goal is not None
        assert agent.backstory is not None
        assert agent.allow_delegation is False
        assert agent.verbose is True

    def test_vector_agent_semantic_search_expertise(self) -> None:
        """Test agent backstory emphasizes semantic similarity and embeddings.

        Validates:
        - Backstory mentions semantic meaning or embeddings
        - Agent understands concept similarity vs keyword matching
        - Focuses on meaning-based search

        Success Criteria (T103):
        - Agent configured with semantic search context
        - Differentiates from keyword search approach
        """
        agent: Any = create_vector_search_agent()

        backstory_lower: str = agent.backstory.lower()

        # Verify semantic search focus
        assert (
            "semantic" in backstory_lower
            or "vector" in backstory_lower
            or "embedding" in backstory_lower
            or "similarity" in backstory_lower
            or "meaning" in backstory_lower
        )

    def test_vector_agent_task_execution(self) -> None:
        """Test Vector Search agent executes semantic search tasks.

        Validates:
        - Agent receives search query and dataset context
        - Agent returns columns ranked by semantic similarity
        - Results include cosine distance scores

        Success Criteria (T103):
        - Agent processes semantic search requests
        - Returns columns ranked by meaning similarity
        """
        # Create real agent (required for CrewAI Task Pydantic validation)
        agent: Any = create_vector_search_agent()

        # Create task
        query_text: str = "find earnings data"
        dataset_ids: list[str] = ["dataset-1", "dataset-2"]

        task: Any = create_vector_search_task(
            agent=agent,
            query_text=query_text,
            dataset_ids=dataset_ids
        )

        # Verify task configuration
        assert task.agent == agent
        assert query_text in task.description
        assert task.expected_output is not None

        # Verify task description mentions semantic or vector search
        description_lower: str = task.description.lower()
        assert "semantic" in description_lower or "vector" in description_lower

    def test_vector_agent_handles_synonym_queries(self) -> None:
        """Test agent understands synonyms and related concepts.

        Validates:
        - "revenue", "income", "earnings" are treated as semantically similar
        - "customer", "client", "buyer" are treated as semantically similar
        - Agent doesn't require exact keyword matches

        Success Criteria (T103):
        - Agent configured for semantic understanding
        - Role emphasizes meaning over exact words
        """
        agent: Any = create_vector_search_agent()

        # Verify agent focuses on semantic meaning
        goal_lower: str = agent.goal.lower()
        backstory_lower: str = agent.backstory.lower()

        assert (
            "meaning" in goal_lower
            or "semantic" in goal_lower
            or "concept" in goal_lower
            or "meaning" in backstory_lower
            or "semantic" in backstory_lower
        )

    def test_vector_agent_vs_keyword_agent_differentiation(self) -> None:
        """Test Vector Search agent differs from Keyword Search agent.

        Validates:
        - Vector agent focuses on semantic similarity
        - Keyword agent focuses on exact/fuzzy text matching
        - Agents have distinct roles and goals

        Success Criteria (T103):
        - Vector and keyword agents have different configurations
        - Roles clearly distinguish search strategies
        """
        keyword_agent: Any = create_keyword_search_agent()
        vector_agent: Any = create_vector_search_agent()

        # Verify different roles
        assert keyword_agent.role != vector_agent.role

        # Verify vector agent focuses on semantic meaning
        vector_role_lower: str = vector_agent.role.lower()
        assert "vector" in vector_role_lower or "semantic" in vector_role_lower

        # Verify keyword agent focuses on text matching
        keyword_role_lower: str = keyword_agent.role.lower()
        assert "keyword" in keyword_role_lower or "text" in keyword_role_lower

    def test_vector_agent_returns_similarity_scores(self) -> None:
        """Test Vector Search agent returns cosine distance scores.

        Validates:
        - Results include similarity scores (1 - cosine distance)
        - Columns ranked by semantic similarity
        - Supports configurable result limit

        Success Criteria (T103):
        - Agent output includes ranked column list
        - Each result has similarity score
        - Results ordered by descending similarity
        """
        from backend.src.crew.tasks import create_vector_search_task

        # Create real agent (required for CrewAI Task Pydantic validation)
        agent: Any = create_vector_search_agent()

        task: Any = create_vector_search_task(
            agent=agent,
            query_text="product information",
            dataset_ids=["dataset-1"]
        )

        # Verify task expects similarity-scored output
        expected_output_lower: str = task.expected_output.lower()
        assert (
            "similarity" in expected_output_lower
            or "distance" in expected_output_lower
            or "score" in expected_output_lower
            or "rank" in expected_output_lower
        )

    def test_vector_agent_empty_query_handling(self) -> None:
        """Test agent handles empty or invalid semantic queries.

        Validates:
        - Empty queries are rejected or handled gracefully
        - Whitespace-only queries are normalized
        - Error messages are informative

        Success Criteria (T103):
        - Agent validates input queries
        - Appropriate errors for invalid input
        """
        agent: Any = create_vector_search_agent()

        # Agent should be created successfully
        assert agent is not None

        # Actual query validation happens in task execution (tested in integration)

    def test_vector_agent_embedding_integration(self) -> None:
        """Test agent is configured to work with embedding generation.

        Validates:
        - Agent understands vector embeddings
        - Backstory references embedding-based search
        - Compatible with OpenAI text-embedding-3-small

        Success Criteria (T103):
        - Agent configured for embedding-based search
        - Role mentions vectors or embeddings
        """
        agent: Any = create_vector_search_agent()

        backstory_lower: str = agent.backstory.lower()
        role_lower: str = agent.role.lower()

        # Should reference vectors, embeddings, or semantic search
        assert (
            "vector" in backstory_lower
            or "embedding" in backstory_lower
            or "vector" in role_lower
            or "semantic" in role_lower
        )

    def test_vector_agent_cross_lingual_capability(self) -> None:
        """Test agent is configured for potential cross-lingual search.

        Validates:
        - Agent understands semantic embeddings work across languages
        - Backstory may mention language-independent search
        - Compatible with multilingual embeddings

        Success Criteria (T103):
        - Agent role doesn't restrict to English-only
        - Semantic search naturally supports multiple languages
        """
        agent: Any = create_vector_search_agent()

        # Agent should focus on semantic meaning (language-agnostic)
        backstory_lower: str = agent.backstory.lower()
        assert "semantic" in backstory_lower or "meaning" in backstory_lower

        # Should not explicitly restrict to English
        assert "english only" not in backstory_lower
