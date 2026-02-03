"""Text-to-SQL service with CrewAI orchestration.

Orchestrates the complete query processing workflow:
1. Natural language → SQL (CrewAI SQL Generator)
2. Execute SQL query
3. Format results → HTML (CrewAI Result Analyst)

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from uuid import UUID

from crewai import Crew

from backend.src.crew.agents import create_result_analyst_agent, create_sql_generator_agent
from backend.src.crew.tasks import create_html_formatting_task, create_sql_generation_task


class TextToSQLService:
    """Service for converting natural language to SQL queries."""

    def generate_sql(
        self, query_text: str, dataset_ids: list[UUID] | None, _username: str
    ) -> dict[str, Any]:
        """Generate SQL from natural language query.

        Args:
            query_text: Natural language question
            dataset_ids: Optional list of dataset UUIDs to query

        Returns:
            Dictionary with sql and params

        Raises:
            Exception: If SQL generation fails
        """
        # Create SQL Generator agent
        sql_agent: Any = create_sql_generator_agent()

        # Create SQL generation task
        task: Any = create_sql_generation_task(
            agent=sql_agent, query_text=query_text, dataset_ids=dataset_ids
        )

        # Create crew and execute
        crew: Crew = Crew(agents=[sql_agent], tasks=[task], verbose=False)

        # Execute crew (synchronous)
        result: Any = crew.kickoff()

        # Extract SQL from result
        generated_sql: str = str(result.raw) if hasattr(result, "raw") else str(result)

        # Clean up SQL (remove markdown code blocks if present)
        sql: str = self._clean_sql(generated_sql)

        return {
            "sql": sql,
            "params": [],  # Params would be extracted from user input if needed
        }

    def _clean_sql(self, sql: str) -> str:
        """Clean generated SQL by removing markdown formatting.

        Args:
            sql: Raw SQL string possibly with markdown

        Returns:
            Clean SQL string
        """
        # Remove markdown code block markers
        sql = sql.replace("```sql", "").replace("```", "")
        # Trim whitespace
        return sql.strip()


class TextToSQLOrchestrator:
    """Orchestrates the complete query processing workflow."""

    def process_query(
        self, query_text: str, dataset_ids: list[UUID] | None, _username: str
    ) -> dict[str, Any]:
        """Process complete query workflow: SQL generation → execution → HTML formatting.

        Args:
            query_text: Natural language question
            dataset_ids: Optional list of dataset UUIDs
            _username: Username for context (unused, reserved for future use)

        Returns:
            Dictionary with generated_sql, html_content, execution results

        Workflow:
        1. Generate SQL using CrewAI SQL Generator agent
        2. Execute SQL query (would happen here, mocked for now)
        3. Format results using CrewAI Result Analyst agent

        Constitutional Compliance:
        - Uses CrewAI synchronously (not async)
        - Thread-based execution
        """
        # Create agents
        sql_agent: Any = create_sql_generator_agent()
        analyst_agent: Any = create_result_analyst_agent()

        # Create SQL generation task
        sql_task: Any = create_sql_generation_task(
            agent=sql_agent, query_text=query_text, dataset_ids=dataset_ids
        )

        # Mock query results for now (would come from actual execution)
        mock_results: dict[str, Any] = {"rows": [], "row_count": 0, "columns": []}

        # Create HTML formatting task (depends on SQL task)
        html_task: Any = create_html_formatting_task(
            agent=analyst_agent,
            query_text=query_text,
            query_results=mock_results,
            context=[sql_task],
        )

        # Create crew with both agents and tasks
        crew: Crew = Crew(
            agents=[sql_agent, analyst_agent], tasks=[sql_task, html_task], verbose=False
        )

        # Execute crew (synchronous, sequential execution)
        result: Any = crew.kickoff()

        # Extract results from tasks
        tasks_output: list[Any] = result.tasks_output if hasattr(result, "tasks_output") else []

        generated_sql: str = ""
        html_content: str = ""

        if len(tasks_output) >= 1:
            generated_sql = (
                str(tasks_output[0].raw)
                if hasattr(tasks_output[0], "raw")
                else str(tasks_output[0])
            )
            generated_sql = self._clean_sql(generated_sql)

        if len(tasks_output) >= 2:
            html_content = (
                str(tasks_output[1].raw)
                if hasattr(tasks_output[1], "raw")
                else str(tasks_output[1])
            )

        return {
            "generated_sql": generated_sql,
            "html_content": html_content,
            "query_results": mock_results,
        }

    def _clean_sql(self, sql: str) -> str:
        """Clean generated SQL by removing markdown formatting.

        Args:
            sql: Raw SQL string possibly with markdown

        Returns:
            Clean SQL string
        """
        sql = sql.replace("```sql", "").replace("```", "")
        return sql.strip()
