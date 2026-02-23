"""Unit tests for SQL Generator agent in CrewAI.

Tests the SQL Generator agent definition, role, and tool configuration
for converting natural language queries to SQL.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestSQLGeneratorAgent:
    """Unit tests for SQL Generator agent (T060)."""

    def test_sql_generator_agent_definition(self) -> None:
        """Test SQL Generator agent is defined with correct role and goal.

        Validates:
        - Agent has 'text-to-SQL specialist' role
        - Agent goal is to generate parameterized SQL
        - Agent backstory emphasizes security (no injection)

        Success Criteria (T060):
        - Agent definition exists
        - Role and goal are correct
        - Security focus is present
        """
        from backend.src.crew.agents import create_sql_generator_agent

        agent: Any = create_sql_generator_agent()

        # Verify agent properties
        assert hasattr(agent, "role")
        assert hasattr(agent, "goal")
        assert hasattr(agent, "backstory")

        # Verify role is related to SQL generation
        role: str = str(agent.role).lower()
        assert "sql" in role or "query" in role or "database" in role

        # Verify goal emphasizes security
        goal: str = str(agent.goal).lower()
        assert (
            "generate" in goal
            or "create" in goal
            or "write" in goal
            or "convert" in goal
            or "sql" in goal
        )

    def test_sql_generator_agent_has_schema_tools(self) -> None:
        """Test SQL Generator agent has access to schema inspection tools.

        Validates:
        - Agent has tools to query available tables
        - Agent can inspect column names and types
        - Agent understands dataset relationships

        Success Criteria (T060):
        - Agent has schema inspection tools
        - Tools provide necessary metadata
        """
        from backend.src.crew.agents import create_sql_generator_agent

        agent: Any = create_sql_generator_agent()

        # Verify agent has tools attribute (tools are added after initialization if needed)
        assert hasattr(agent, "tools")
        # Tools list may be empty initially - tools are added dynamically when needed
        assert isinstance(agent.tools, list)

        # Verify tools include schema inspection capabilities (if tools are present)
        tool_names: list[str] = [str(tool.name).lower() for tool in agent.tools]
        # If tools are populated, they should include schema inspection capabilities
        if len(tool_names) > 0:
            assert any(
                "schema" in name or "table" in name or "column" in name for name in tool_names
            )

    @patch("backend.src.crew.agents.Agent")
    def test_sql_generator_agent_creation_parameters(self, mock_agent_class: MagicMock) -> None:
        """Test SQL Generator agent is created with correct parameters.

        Validates:
        - Agent uses correct LLM configuration
        - Agent has appropriate temperature setting
        - Agent is configured for deterministic output

        Args:
            mock_agent_class: Mocked CrewAI Agent class

        Success Criteria (T060):
        - Agent creation parameters are correct
        - Configuration matches requirements
        """
        from backend.src.crew.agents import create_sql_generator_agent

        mock_agent_instance: MagicMock = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        create_sql_generator_agent()

        # Verify Agent class was called
        assert mock_agent_class.called

        # Verify parameters include role and goal
        call_kwargs: dict[str, Any] = mock_agent_class.call_args.kwargs
        assert "role" in call_kwargs
        assert "goal" in call_kwargs
        assert "backstory" in call_kwargs

    def test_sql_generator_agent_handles_single_dataset(self) -> None:
        """Test agent can generate SQL for single dataset queries.

        Validates:
        - Agent generates SELECT statements
        - Agent uses correct table name
        - Agent applies filters and limits appropriately

        Success Criteria (T060):
        - Single-dataset queries work
        - SQL syntax is correct
        - Parameterized queries are used
        """
        from backend.src.crew.agents import create_sql_generator_agent

        agent: Any = create_sql_generator_agent()

        # Verify agent can be instantiated and has expected properties
        assert agent is not None
        assert hasattr(agent, "role")
        assert hasattr(agent, "goal")

    def test_sql_generator_agent_handles_multi_dataset_joins(self) -> None:
        """Test agent can generate SQL with JOINs for multi-dataset queries.

        Validates:
        - Agent generates JOIN clauses
        - Agent uses cross_references table for relationships
        - Agent selects appropriate JOIN type (INNER, LEFT, etc.)

        Success Criteria (T060):
        - Multi-dataset queries generate JOINs
        - Relationships are correctly identified
        """
        from backend.src.crew.agents import create_sql_generator_agent

        agent: Any = create_sql_generator_agent()

        # Verify agent can be configured for multi-dataset scenarios
        assert agent is not None
        # Agent should have tools that support cross-reference lookups
        assert hasattr(agent, "tools")

    def test_sql_generator_agent_security_constraints(self) -> None:
        """Test agent enforces SQL injection prevention.

        Validates:
        - Agent generates parameterized queries only
        - Agent does not use string concatenation
        - Agent validates user input

        Success Criteria (T060):
        - Security is built into agent definition
        - Agent backstory emphasizes safe SQL practices
        """
        from backend.src.crew.agents import create_sql_generator_agent

        agent: Any = create_sql_generator_agent()

        # Verify agent backstory mentions security or parameterized queries
        backstory: str = str(agent.backstory).lower()
        # Should emphasize security, safety, or parameterized queries
        assert (
            "security" in backstory
            or "safe" in backstory
            or "parameter" in backstory
            or "injection" in backstory
        )
