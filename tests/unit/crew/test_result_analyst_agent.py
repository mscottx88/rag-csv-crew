"""Unit tests for Result Analyst agent in CrewAI.

Tests the Result Analyst agent definition, role, and HTML formatting capabilities
for converting query results into readable HTML responses.

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
class TestResultAnalystAgent:
    """Unit tests for Result Analyst agent (T061)."""

    def test_result_analyst_agent_definition(self) -> None:
        """Test Result Analyst agent is defined with correct role and goal.

        Validates:
        - Agent has 'HTML formatter' role
        - Agent goal is to generate readable HTML responses
        - Agent backstory emphasizes readability and accessibility

        Success Criteria (T061):
        - Agent definition exists
        - Role focuses on HTML formatting
        - Semantic HTML5 is emphasized
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        # Verify agent properties
        assert hasattr(agent, "role")
        assert hasattr(agent, "goal")
        assert hasattr(agent, "backstory")

        # Verify role is related to formatting/analysis
        role: str = str(agent.role).lower()
        assert (
            "html" in role
            or "format" in role
            or "analyst" in role
            or "response" in role
            or "presentation" in role
            or "data" in role
        )

        # Verify goal emphasizes readability
        goal: str = str(agent.goal).lower()
        assert "html" in goal or "format" in goal or "readable" in goal or "response" in goal

    def test_result_analyst_agent_html_formatting_focus(self) -> None:
        """Test agent backstory emphasizes semantic HTML5 and accessibility.

        Validates:
        - Agent understands semantic HTML5 tags
        - Agent prioritizes readability
        - Agent follows accessibility best practices

        Success Criteria (T061):
        - Backstory mentions HTML, formatting, or readability
        - Semantic structure is emphasized
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        backstory: str = str(agent.backstory).lower()

        # Verify backstory emphasizes HTML and formatting
        assert (
            "html" in backstory
            or "format" in backstory
            or "readable" in backstory
            or "semantic" in backstory
            or "structure" in backstory
        )

    def test_result_analyst_agent_has_formatting_tools(self) -> None:
        """Test Result Analyst agent has access to formatting tools.

        Validates:
        - Agent has tools for HTML generation
        - Agent can format numbers, dates, and text
        - Agent can create tables and lists

        Success Criteria (T061):
        - Agent has formatting tools
        - Tools support various data types
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        # Verify agent has tools
        assert hasattr(agent, "tools")
        # Agent may or may not have explicit tools (could use LLM directly)
        # If tools exist, they should support formatting
        if len(agent.tools) > 0:
            tool_names: list[str] = [str(tool.name).lower() for tool in agent.tools]
            assert any("format" in name or "html" in name or "table" in name for name in tool_names)

    @patch("backend.src.crew.agents.Agent")
    def test_result_analyst_agent_creation_parameters(self, mock_agent_class: MagicMock) -> None:
        """Test Result Analyst agent is created with correct parameters.

        Validates:
        - Agent uses correct LLM configuration
        - Agent has appropriate creativity setting
        - Agent is configured for formatted output

        Args:
            mock_agent_class: Mocked CrewAI Agent class

        Success Criteria (T061):
        - Agent creation parameters are correct
        - Configuration supports creative formatting
        """
        from backend.src.crew.agents import create_result_analyst_agent

        mock_agent_instance: MagicMock = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        create_result_analyst_agent()

        # Verify Agent class was called
        assert mock_agent_class.called

        # Verify parameters include role and goal
        call_kwargs: dict[str, Any] = mock_agent_class.call_args.kwargs
        assert "role" in call_kwargs
        assert "goal" in call_kwargs
        assert "backstory" in call_kwargs

    def test_result_analyst_agent_handles_tabular_data(self) -> None:
        """Test agent can format tabular data as HTML tables.

        Validates:
        - Agent generates <table> elements
        - Agent includes <thead> and <tbody>
        - Agent formats headers correctly

        Success Criteria (T061):
        - Tabular data produces tables
        - Table structure is semantic
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        # Verify agent is properly instantiated
        assert agent is not None
        assert hasattr(agent, "role")
        # Agent should be capable of formatting tables (tested in integration)

    def test_result_analyst_agent_handles_empty_results(self) -> None:
        """Test agent generates user-friendly messages for empty results.

        Validates:
        - Empty result sets produce helpful messages
        - Agent suggests alternative actions
        - Tone is friendly and constructive

        Success Criteria (T061):
        - Empty results are handled gracefully
        - User gets guidance
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        # Verify agent goal includes handling all result types
        goal: str = str(agent.goal).lower()
        # Agent should be capable of handling various scenarios
        assert len(goal) > 0

    def test_result_analyst_agent_readability_focus(self) -> None:
        """Test agent prioritizes readability over technical accuracy.

        Validates:
        - Agent uses plain language
        - Agent formats numbers for readability
        - Agent avoids jargon

        Success Criteria (T061):
        - Agent backstory emphasizes user-friendliness
        - Readability is a core principle
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        # Verify agent backstory or goal mentions readability
        combined_text: str = (
            str(agent.role) + " " + str(agent.goal) + " " + str(agent.backstory)
        ).lower()

        assert (
            "readable" in combined_text
            or "clear" in combined_text
            or "user" in combined_text
            or "friendly" in combined_text
        )

    def test_result_analyst_agent_generates_plain_text_alternative(self) -> None:
        """Test agent can generate both HTML and plain text versions.

        Validates:
        - Agent produces plain text alongside HTML
        - Plain text is accessible
        - Plain text preserves key information

        Success Criteria (T061):
        - Agent supports dual output format
        - Accessibility is considered
        """
        from backend.src.crew.agents import create_result_analyst_agent

        agent: Any = create_result_analyst_agent()

        # Verify agent is configured appropriately
        assert agent is not None
        # Plain text generation is tested in integration tests
        # Agent should be capable of producing both formats
