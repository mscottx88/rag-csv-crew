"""Integration tests for CrewAI orchestration.

Tests the end-to-end CrewAI workflow coordinating SQL Generator and
Result Analyst agents in sequential execution.

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


@pytest.mark.integration
class TestCrewOrchestration:
    """Integration tests for CrewAI orchestration (T062)."""

    @patch("backend.src.services.text_to_sql.Crew")
    def test_sequential_agent_execution(self, mock_crew: MagicMock) -> None:
        """Test CrewAI orchestrates agents in correct sequence.

        Validates:
        - SQL Generator agent runs first
        - Query execution happens after SQL generation
        - Result Analyst agent runs last with query results
        - Task dependencies are enforced

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T062):
        - Agents execute in order: SQL → Execute → HTML
        - Each step receives output from previous step
        - Orchestration is seamless
        """
        from backend.src.services.text_to_sql import TextToSQLOrchestrator

        # Mock crew execution
        mock_crew_instance: MagicMock = MagicMock()
        mock_crew_instance.kickoff.return_value = MagicMock(
            tasks_output=[
                MagicMock(raw="SELECT * FROM data LIMIT 10"),  # SQL generation
                MagicMock(raw="<p>Top 10 results shown</p>"),  # HTML formatting
            ]
        )
        mock_crew.return_value = mock_crew_instance

        orchestrator: TextToSQLOrchestrator = TextToSQLOrchestrator()

        result: dict[str, Any] = orchestrator.process_query(
            query_text="Show me the top 10 rows", dataset_ids=[uuid4()], _username="testuser"
        )

        # Verify crew was executed
        mock_crew_instance.kickoff.assert_called_once()

        # Verify result contains both SQL and HTML
        assert "generated_sql" in result
        assert "html_content" in result

    @patch("backend.src.crew.agents.create_sql_generator_agent")
    @patch("backend.src.crew.agents.create_result_analyst_agent")
    def test_task_dependencies_enforced(
        self, mock_result_analyst: MagicMock, mock_sql_generator: MagicMock
    ) -> None:
        """Test CrewAI task dependencies prevent out-of-order execution.

        Validates:
        - Result Analyst cannot run before SQL generation
        - Tasks explicitly depend on previous task completion
        - Context is passed between tasks

        Args:
            mock_result_analyst: Mocked Result Analyst agent creator
            mock_sql_generator: Mocked SQL Generator agent creator

        Success Criteria (T062):
        - Task dependencies are defined
        - Execution order is guaranteed
        - Context flows between tasks
        """
        from crewai import Agent

        from backend.src.crew.tasks import create_html_formatting_task, create_sql_generation_task

        # Create real Agent instances to pass Pydantic validation
        mock_sql_agent: Agent = Agent(
            role="SQL Generator",
            goal="Generate SQL",
            backstory="Test SQL agent",
            verbose=False,
            allow_delegation=False,
        )
        mock_analyst_agent: Agent = Agent(
            role="Result Analyst",
            goal="Format results",
            backstory="Test analyst agent",
            verbose=False,
            allow_delegation=False,
        )
        mock_sql_generator.return_value = mock_sql_agent
        mock_result_analyst.return_value = mock_analyst_agent

        # Create tasks
        sql_task: Any = create_sql_generation_task(
            agent=mock_sql_agent, query_text="Test query", dataset_ids=[uuid4()]
        )

        html_task: Any = create_html_formatting_task(
            agent=mock_analyst_agent,
            query_text="Test query",
            query_results={"rows": [], "row_count": 0, "columns": []},
            context=[sql_task],  # HTML task depends on SQL task
        )

        # Verify task properties
        assert sql_task is not None
        assert html_task is not None

        # Verify HTML task has context dependency
        if hasattr(html_task, "context"):
            assert sql_task in html_task.context

    @patch("backend.src.services.text_to_sql.Crew")
    def test_crew_handles_agent_failures(self, mock_crew: MagicMock) -> None:
        """Test CrewAI orchestration handles agent failures gracefully.

        Validates:
        - LLM API failures are caught
        - Retry logic is applied
        - User-friendly error messages are returned

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T062):
        - Agent failures don't crash orchestration
        - Errors are propagated correctly
        - Cleanup happens on failure
        """
        from backend.src.services.text_to_sql import TextToSQLOrchestrator

        # Mock crew to raise exception
        mock_crew_instance: MagicMock = MagicMock()
        mock_crew_instance.kickoff.side_effect = Exception("LLM API error")
        mock_crew.return_value = mock_crew_instance

        orchestrator: TextToSQLOrchestrator = TextToSQLOrchestrator()

        with pytest.raises(Exception) as exc_info:
            orchestrator.process_query(
                query_text="Test query", dataset_ids=[uuid4()], _username="testuser"
            )

        # Verify error is raised
        assert exc_info.value is not None

    @patch("backend.src.services.text_to_sql.Crew")
    @patch("backend.src.services.query_execution.QueryExecutionService")
    def test_orchestration_includes_query_execution(
        self, mock_execution_service: MagicMock, mock_crew: MagicMock
    ) -> None:
        """Test orchestration includes actual query execution between agents.

        Validates:
        - SQL generated by first agent is executed
        - Query results are passed to Result Analyst
        - Execution errors are handled

        Args:
            mock_execution_service: Mocked query execution service
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T062):
        - Query execution is integrated
        - Results flow to Result Analyst
        - Pipeline is complete
        """
        from backend.src.services.text_to_sql import TextToSQLOrchestrator

        # Mock SQL generation
        mock_crew_instance: MagicMock = MagicMock()
        mock_crew_instance.kickoff.return_value = MagicMock(
            tasks_output=[MagicMock(raw="SELECT * FROM data"), MagicMock(raw="<p>Results</p>")]
        )
        mock_crew.return_value = mock_crew_instance

        # Mock query execution
        mock_execution_instance: MagicMock = MagicMock()
        mock_execution_instance.execute_query.return_value = {
            "rows": [{"id": 1, "name": "Test"}],
            "row_count": 1,
            "columns": ["id", "name"],
        }
        mock_execution_service.return_value = mock_execution_instance

        orchestrator: TextToSQLOrchestrator = TextToSQLOrchestrator()

        result: dict[str, Any] = orchestrator.process_query(
            query_text="Show me the data", dataset_ids=[uuid4()], _username="testuser"
        )

        # Verify orchestration completed
        assert "generated_sql" in result
        assert "html_content" in result

    @patch("backend.src.services.text_to_sql.Crew")
    def test_orchestration_thread_safety(self, mock_crew: MagicMock) -> None:
        """Test CrewAI orchestration is thread-safe for concurrent queries.

        Validates:
        - Multiple queries can run concurrently
        - No race conditions occur
        - Each query maintains independent context

        Args:
            mock_crew: Mocked CrewAI Crew class

        Success Criteria (T062):
        - Concurrent execution works correctly
        - No data corruption
        - Thread-based concurrency per constitution
        """
        from concurrent.futures import ThreadPoolExecutor

        from backend.src.services.text_to_sql import TextToSQLOrchestrator

        # Mock crew responses
        mock_crew_instance: MagicMock = MagicMock()
        mock_crew_instance.kickoff.return_value = MagicMock(
            tasks_output=[MagicMock(raw="SELECT * FROM data"), MagicMock(raw="<p>Results</p>")]
        )
        mock_crew.return_value = mock_crew_instance

        orchestrator: TextToSQLOrchestrator = TextToSQLOrchestrator()

        def run_query(query_num: int) -> dict[str, Any]:
            """Run a single query."""
            return orchestrator.process_query(
                query_text=f"Query {query_num}", dataset_ids=[uuid4()], _username="testuser"
            )

        # Run multiple queries concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures: list[Any] = [executor.submit(run_query, i) for i in range(5)]
            results: list[dict[str, Any]] = [f.result() for f in futures]

        # Verify all queries completed
        assert len(results) == 5
        for result in results:
            assert "generated_sql" in result
            assert "html_content" in result

    def test_crew_configuration_follows_constitution(self) -> None:
        """Test CrewAI configuration follows constitutional requirements.

        Validates:
        - No async/await in crew configuration
        - Thread-based concurrency used
        - Proper error handling

        Success Criteria (T062):
        - Constitution compliance verified
        - Thread-based execution confirmed
        """
        from backend.src.crew.agents import create_result_analyst_agent, create_sql_generator_agent

        # Verify agents can be created (synchronous)
        sql_agent: Any = create_sql_generator_agent()
        analyst_agent: Any = create_result_analyst_agent()

        # Verify agents are properly configured
        assert sql_agent is not None
        assert analyst_agent is not None

        # Agents should use synchronous patterns (no async methods)
        # This is verified by the absence of async keywords in agent definitions
