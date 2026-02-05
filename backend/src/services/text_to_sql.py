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
from psycopg import sql
from psycopg_pool import ConnectionPool

from src.crew.agents import create_result_analyst_agent, create_sql_generator_agent
from src.crew.tasks import create_html_formatting_task, create_sql_generation_task


class TextToSQLService:
    """Service for converting natural language to SQL queries."""

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize TextToSQLService.

        Args:
            pool: Optional database connection pool for cross-reference retrieval
        """
        self.pool: ConnectionPool | None = pool

    def get_cross_references(
        self, username: str, dataset_ids: list[UUID]
    ) -> list[dict[str, Any]]:
        """Retrieve cross-references between specified datasets.

        Args:
            username: Username for schema isolation
            dataset_ids: List of dataset UUIDs to find relationships between

        Returns:
            List of cross-references with relationship metadata

        Raises:
            ValueError: If pool is not configured
        """
        if self.pool is None:
            return []

        user_schema: str = f"{username}_schema"
        cross_references: list[dict[str, Any]] = []

        with self.pool.connection() as conn, conn.cursor() as cur:
            # Set search path using SQL composition
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            # Query cross_references table for relationships between these datasets
            dataset_id_strs: list[str] = [str(dataset_id) for dataset_id in dataset_ids]

            cur.execute(
                """
                    SELECT
                        source_dataset_id,
                        source_column,
                        target_dataset_id,
                        target_column,
                        relationship_type,
                        confidence_score
                    FROM cross_references
                    WHERE source_dataset_id = ANY(%s)
                      AND target_dataset_id = ANY(%s)
                    ORDER BY confidence_score DESC
                    """,
                (dataset_id_strs, dataset_id_strs),
            )

            rows: list[tuple[Any, ...]] = cur.fetchall()
            for row in rows:
                cross_references.append(
                    {
                        "source_dataset_id": row[0],
                        "source_column": row[1],
                        "target_dataset_id": row[2],
                        "target_column": row[3],
                        "relationship_type": row[4],
                        "confidence_score": row[5],
                    }
                )

        return cross_references

    def generate_sql(
        self, query_text: str, dataset_ids: list[UUID] | None, username: str
    ) -> dict[str, Any]:
        """Generate SQL from natural language query.

        Args:
            query_text: Natural language question
            dataset_ids: Optional list of dataset UUIDs to query
            username: Username for schema isolation

        Returns:
            Dictionary with sql and params

        Raises:
            Exception: If SQL generation fails
        """
        # Retrieve cross-references if multiple datasets specified
        cross_references: list[dict[str, Any]] = []
        if dataset_ids and len(dataset_ids) > 1:
            cross_references = self.get_cross_references(username, dataset_ids)

        # Create SQL Generator agent
        sql_agent: Any = create_sql_generator_agent()

        # Create SQL generation task (with cross-reference context)
        task: Any = create_sql_generation_task(
            agent=sql_agent,
            query_text=query_text,
            dataset_ids=dataset_ids,
            cross_references=cross_references,
        )

        # Create crew and execute
        crew: Crew = Crew(agents=[sql_agent], tasks=[task], verbose=False)

        # Execute crew (synchronous)
        result: Any = crew.kickoff()

        # Extract SQL from result
        generated_sql: str = str(result.raw) if hasattr(result, "raw") else str(result)  # pylint: disable=redefined-outer-name

        # Clean up SQL (remove markdown code blocks if present)
        sql: str = self._clean_sql(generated_sql)  # pylint: disable=redefined-outer-name

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
        cleaned_sql: str = sql.replace("```sql", "").replace("```", "")  # pylint: disable=redefined-outer-name
        # Trim whitespace
        return cleaned_sql.strip()


class TextToSQLOrchestrator:
    """Orchestrates the complete query processing workflow."""

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize TextToSQLOrchestrator.

        Args:
            pool: Optional database connection pool for cross-reference retrieval
        """
        self.pool: ConnectionPool | None = pool
        self.text_to_sql_service: TextToSQLService = TextToSQLService(pool)

    def process_query(
        self, query_text: str, dataset_ids: list[UUID] | None, username: str
    ) -> dict[str, Any]:
        """Process complete query workflow: SQL generation → execution → HTML formatting.

        Args:
            query_text: Natural language question
            dataset_ids: Optional list of dataset UUIDs
            username: Username for schema isolation

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
        # Retrieve cross-references if multiple datasets specified
        cross_references: list[dict[str, Any]] = []
        if dataset_ids and len(dataset_ids) > 1:
            cross_references = self.text_to_sql_service.get_cross_references(username, dataset_ids)

        # Create agents
        sql_agent: Any = create_sql_generator_agent()
        analyst_agent: Any = create_result_analyst_agent()

        # Create SQL generation task (with cross-reference context)
        sql_task: Any = create_sql_generation_task(
            agent=sql_agent,
            query_text=query_text,
            dataset_ids=dataset_ids,
            cross_references=cross_references,
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

        generated_sql: str = ""  # pylint: disable=redefined-outer-name
        html_content: str = ""

        if len(tasks_output) >= 1:
            generated_sql = (  # pylint: disable=redefined-outer-name
                str(tasks_output[0].raw)
                if hasattr(tasks_output[0], "raw")
                else str(tasks_output[0])
            )
            generated_sql = self._clean_sql(generated_sql)  # pylint: disable=redefined-outer-name

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

    def _clean_sql(self, sql: str) -> str:  # pylint: disable=redefined-outer-name
        """Clean generated SQL by removing markdown formatting.

        Args:
            sql: Raw SQL string possibly with markdown

        Returns:
            Clean SQL string
        """
        cleaned_sql: str = sql.replace("```sql", "").replace("```", "")  # pylint: disable=redefined-outer-name
        return cleaned_sql.strip()
