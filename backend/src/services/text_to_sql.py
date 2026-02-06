"""Text-to-SQL service with CrewAI orchestration.

Orchestrates the complete query processing workflow:
1. Natural language → SQL (CrewAI SQL Generator)
2. Execute SQL query
3. Format results → HTML (CrewAI Result Analyst)

Also handles metadata queries (listing available datasets, tables, columns).

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
from psycopg import sql
from psycopg_pool import ConnectionPool

from src.crew.agents import (
    create_result_analyst_agent,
    create_schema_inspector_agent,
    create_sql_generator_agent,
)
from src.crew.tasks import (
    create_html_formatting_task,
    create_schema_inspection_task,
    create_sql_generation_task,
)
from src.crew.tools import (
    get_sample_data_tool,
    inspect_schema_tool,
    list_datasets_tool,
    set_schema_inspector_context,
)
from src.services.schema_inspector import SchemaInspectorService


class TextToSQLService:
    """Service for converting natural language to SQL queries."""

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize TextToSQLService.

        Args:
            pool: Optional database connection pool for cross-reference retrieval
        """
        self.pool: ConnectionPool | None = pool

    @staticmethod
    def is_metadata_query(query_text: str) -> bool:
        """Detect if query is asking for metadata (available datasets/tables/columns).

        Args:
            query_text: Natural language question

        Returns:
            True if query is asking for metadata, False otherwise

        Examples:
            "what datasets do I have?" → True
            "show me available tables" → True
            "list all columns" → True
            "what data can I query?" → True
            "show me customers in California" → False (data query, not metadata)
        """
        query_lower: str = query_text.lower()

        # Metadata query patterns
        metadata_patterns: list[str] = [
            r"\b(what|which|show|list|display|get)\s+(datasets?|tables?|columns?|data|files?|csv)",
            r"\b(available|existing|uploaded)\s+(datasets?|tables?|columns?|data|files?)",
            r"\bdo\s+i\s+have\b",
            r"\bcan\s+i\s+query\b",
            r"\bwhat'?s\s+(available|in|here)",
            r"\bshow\s+me\s+(my|the|all)\s+(datasets?|tables?|columns?|data)",
            r"\b(list|enumerate)\s+(all|my)\b",
        ]

        return any(re.search(pattern, query_lower) for pattern in metadata_patterns)

    def get_available_metadata(self, username: str) -> dict[str, Any]:
        """Retrieve metadata about available datasets, tables, and columns for a user.

        Args:
            username: Username for schema isolation

        Returns:
            Dictionary containing datasets with their tables and columns

        Raises:
            ValueError: If pool is not configured
        """
        if self.pool is None:
            raise ValueError("Database pool is not configured")

        user_schema: str = f"{username}_schema"
        metadata: dict[str, Any] = {"datasets": []}

        with self.pool.connection() as conn, conn.cursor() as cur:
            # Set search path
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            # Get all datasets for this user
            cur.execute(
                """
                SELECT id, filename, row_count, column_count, uploaded_at
                FROM datasets
                ORDER BY uploaded_at DESC
                """,
            )

            dataset_rows: list[tuple[Any, ...]] = cur.fetchall()

            for dataset_row in dataset_rows:
                dataset_id: str = str(dataset_row[0])
                filename: str = dataset_row[1]

                # Handle both "file.csv" and "file" formats
                table_name: str
                if filename.endswith(".csv"):
                    table_name = filename.replace(".csv", "_data")
                else:
                    table_name = f"{filename}_data"

                dataset_info: dict[str, Any] = {
                    "id": dataset_id,
                    "filename": filename,
                    "table_name": table_name,
                    "row_count": dataset_row[2],
                    "column_count": dataset_row[3],
                    "uploaded_at": str(dataset_row[4]),
                    "columns": [],
                }

                # Get columns for this dataset
                cur.execute(
                    """
                    SELECT column_name, inferred_type
                    FROM column_mappings
                    WHERE dataset_id = %s
                    ORDER BY column_name
                    """,
                    (dataset_id,),
                )

                column_rows: list[tuple[Any, ...]] = cur.fetchall()
                for column_row in column_rows:
                    dataset_info["columns"].append(
                        {
                            "name": column_row[0],
                            "type": column_row[1],
                        }
                    )

                metadata["datasets"].append(dataset_info)

        metadata["total_datasets"] = len(metadata["datasets"])
        return metadata

    def format_metadata_as_html(self, metadata: dict[str, Any]) -> str:
        """Format metadata dictionary as clean, readable HTML.

        Args:
            metadata: Metadata dictionary from get_available_metadata()

        Returns:
            HTML string with formatted metadata

        Format:
            <article>
              <h2>Available Datasets</h2>
              <section>
                <h3>Dataset: filename.csv</h3>
                <ul><li>Table: table_name</li>...</ul>
                <h4>Columns ({count})</h4>
                <table>...</table>
              </section>
            </article>
        """
        datasets: list[dict[str, Any]] = metadata.get("datasets", [])
        total_datasets: int = metadata.get("total_datasets", 0)

        if total_datasets == 0:
            return """
            <article>
                <h2>Available Datasets</h2>
                <p>You don't have any datasets uploaded yet.</p>
                <p>Upload a CSV file to get started.</p>
            </article>
            """.strip()

        html_parts: list[str] = [
            "<article>",
            f"<h2>Available Datasets ({total_datasets})</h2>",
        ]

        for dataset in datasets:
            filename: str = dataset["filename"]
            table_name: str = dataset["table_name"]
            row_count: int = dataset["row_count"]
            column_count: int = dataset["column_count"]
            columns: list[dict[str, str]] = dataset["columns"]

            html_parts.extend(
                [
                    (
                        "<section style='margin-bottom: 2em; padding: 1em; "
                        "border: 1px solid #ddd; border-radius: 4px;'>"
                    ),
                    f"<h3>{filename}</h3>",
                    "<ul style='list-style: none; padding: 0; margin: 0.5em 0;'>",
                    f"<li><strong>Table:</strong> {table_name}</li>",
                    f"<li><strong>Rows:</strong> {row_count:,}</li>",
                    f"<li><strong>Columns:</strong> {column_count}</li>",
                    "</ul>",
                    f"<h4>Columns ({column_count})</h4>",
                    "<table style='width: 100%; border-collapse: collapse;'>",
                    "<thead>",
                    "<tr style='background-color: #f5f5f5;'>",
                    (
                        "<th style='padding: 8px; text-align: left; "
                        "border: 1px solid #ddd;'>Column Name</th>"
                    ),
                    (
                        "<th style='padding: 8px; text-align: left; "
                        "border: 1px solid #ddd;'>Data Type</th>"
                    ),
                    "</tr>",
                    "</thead>",
                    "<tbody>",
                ]
            )

            for column in columns:
                html_parts.extend(
                    [
                        "<tr>",
                        f"<td style='padding: 8px; border: 1px solid #ddd;'>{column['name']}</td>",
                        f"<td style='padding: 8px; border: 1px solid #ddd;'>{column['type']}</td>",
                        "</tr>",
                    ]
                )

            html_parts.extend(
                [
                    "</tbody>",
                    "</table>",
                    "</section>",
                ]
            )

        html_parts.append("</article>")

        return "\n".join(html_parts)

    def resolve_datasets(
        self,
        _username: str,
        query_text: str,
        available_datasets: list[str],
        dataset_ids: list[str] | None = None,
    ) -> list[str]:
        """Identify relevant datasets for a query based on content and relationships.

        Args:
            query_text: Natural language question text
            available_datasets: List of available dataset names/IDs
            dataset_ids: Optional user-specified filter (if provided, limits to these)

        Returns:
            List of dataset names/IDs relevant to the query

        Note:
            _username parameter reserved for future cross-reference support

        Algorithm:
        1. If dataset_ids filter provided, return intersection with available_datasets
        2. Otherwise, fuzzy match dataset names in query_text
        3. Include datasets connected via cross-references

        Examples:
            query="Show customers" → ["customers"]
            query="Customer orders" → ["customers", "orders"]
        """
        # If user specified dataset filter, respect it (intersection with available)
        if dataset_ids is not None:
            return [ds for ds in dataset_ids if ds in available_datasets]

        # Fuzzy match dataset names in query text (case-insensitive, substring match)
        query_lower: str = query_text.lower()
        matched_datasets: list[str] = []

        for dataset in available_datasets:
            # Remove .csv extension and convert to lowercase for comparison
            dataset_name: str = dataset.replace(".csv", "").lower()

            # Check if dataset name (or singular/plural variant) appears in query
            if (
                dataset_name in query_lower
                # Check for singular variant (e.g., "customer" matches "customers")
                or (dataset_name.endswith("s") and dataset_name[:-1] in query_lower)
                # Check for plural variant (e.g., "customers" matches "customer")
                or (not dataset_name.endswith("s") and f"{dataset_name}s" in query_lower)
            ):
                matched_datasets.append(dataset)

        # If no matches found, return all available datasets (query all by default)
        if not matched_datasets:
            return available_datasets

        return matched_datasets

    def get_cross_references(self, username: str, dataset_ids: list[UUID]) -> list[dict[str, Any]]:
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

    def get_schema_context(
        self, username: str, dataset_ids: list[UUID] | None = None
    ) -> dict[str, Any]:
        """Extract valid table and column names from database schema.

        Args:
            username: Username for schema isolation
            dataset_ids: Optional list of dataset UUIDs to filter

        Returns:
            Dictionary with tables (list of table names) and columns (dict mapping table_name -> column list)

        Raises:
            ValueError: If pool is not configured
        """
        if self.pool is None:
            raise ValueError("Database pool is not configured")

        user_schema: str = f"{username}_schema"
        schema_context: dict[str, Any] = {"tables": [], "columns": {}}

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(user_schema))
            )

            # Build dataset filter clause if needed
            filter_clause: str = ""
            filter_params: tuple[Any, ...] = ()
            if dataset_ids:
                dataset_id_strs: list[str] = [str(dataset_id) for dataset_id in dataset_ids]
                filter_clause = " WHERE d.id = ANY(%s)"
                filter_params = (dataset_id_strs,)

            # Get all tables for user (from datasets table)
            cur.execute(
                f"""
                SELECT d.id, d.filename
                FROM datasets d
                {filter_clause}
                ORDER BY d.uploaded_at DESC
                """,
                filter_params,
            )

            dataset_rows: list[tuple[Any, ...]] = cur.fetchall()

            for dataset_row in dataset_rows:
                dataset_id: str = str(dataset_row[0])
                filename: str = dataset_row[1]

                # Construct table name (same logic as ingestion)
                table_name: str
                if filename.endswith(".csv"):
                    table_name = filename.replace(".csv", "_data")
                else:
                    table_name = f"{filename}_data"

                schema_context["tables"].append(table_name)

                # Get columns for this dataset
                cur.execute(
                    """
                    SELECT column_name
                    FROM column_mappings
                    WHERE dataset_id = %s
                    ORDER BY column_name
                    """,
                    (dataset_id,),
                )

                column_rows: list[tuple[Any, ...]] = cur.fetchall()
                column_names: list[str] = [str(row[0]) for row in column_rows]

                schema_context["columns"][table_name] = column_names

        return schema_context

    def validate_sql_against_schema(
        self, sql_query: str, schema_context: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate that SQL only references tables and columns that exist in schema.

        Args:
            sql_query: Generated SQL query to validate
            schema_context: Schema context from get_schema_context()

        Returns:
            Dictionary with is_valid (bool), errors (list of str), and corrections (dict)

        Validation Checks:
        1. Extract table names from FROM and JOIN clauses
        2. Extract column names from SELECT, WHERE, and other clauses
        3. Check that all tables exist in schema_context["tables"]
        4. Check that all columns exist in schema_context["columns"][table_name]
        """
        valid_tables: list[str] = schema_context["tables"]
        valid_columns_by_table: dict[str, list[str]] = schema_context["columns"]

        errors: list[str] = []
        corrections: dict[str, str] = {}

        # Extract table names from SQL (FROM and JOIN clauses)
        # Simplified regex - matches table names after FROM or JOIN
        table_pattern: str = r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)"
        referenced_tables: list[str] = re.findall(table_pattern, sql_query, re.IGNORECASE)

        # Check each referenced table
        for table in referenced_tables:
            table_lower: str = table.lower()
            if table_lower not in valid_tables:
                errors.append(
                    f"Table '{table}' does not exist. Valid tables: {', '.join(valid_tables)}"
                )
                # Find closest match
                if valid_tables:
                    corrections[table] = valid_tables[0]  # Use first valid table as suggestion

        # Extract column names from SQL (simplified - looks for identifiers)
        # This is a heuristic approach - not perfect but catches most cases
        # Matches identifiers that are likely column references
        # CRITICAL: Require word boundaries BEFORE and AFTER operator to prevent
        # matching "IS" within "analySIS" or "ILIKE". Also require whitespace before operator.
        column_pattern: str = r"\b([a-z_][a-z0-9_]*)\s+\b(?:ILIKE|LIKE|IN|IS|=|<|>)\b"

        # DEBUG: Log the pattern and SQL being validated
        import logging
        logger: logging.Logger = logging.getLogger(__name__)
        logger.info(f"[VALIDATION DEBUG] Using regex pattern: {column_pattern}")
        logger.info(f"[VALIDATION DEBUG] Validating SQL: {sql_query[:200]}")

        potential_columns: list[str] = re.findall(column_pattern, sql_query, re.IGNORECASE)
        logger.info(f"[VALIDATION DEBUG] Extracted columns: {potential_columns}")

        # Check columns against all valid tables (since we may not know which table each column belongs to)
        all_valid_columns: set[str] = set()
        for columns in valid_columns_by_table.values():
            all_valid_columns.update(columns)

        for column in potential_columns:
            column_lower: str = column.lower()
            # Skip SQL keywords
            sql_keywords: set[str] = {
                "select",
                "from",
                "where",
                "join",
                "left",
                "right",
                "inner",
                "outer",
                "on",
                "and",
                "or",
                "not",
                "null",
                "true",
                "false",
                "limit",
                "offset",
                "order",
                "by",
                "group",
                "having",
                "as",
                "distinct",
                "all",
                "any",
            }
            if column_lower not in sql_keywords and column_lower not in all_valid_columns:
                errors.append(
                    f"Column '{column}' may not exist. Valid columns: {', '.join(sorted(all_valid_columns))}"
                )

        is_valid: bool = len(errors) == 0

        return {
            "is_valid": is_valid,
            "errors": errors,
            "corrections": corrections,
        }

    def generate_sql(
        self,
        query_text: str,
        dataset_ids: list[UUID] | None,
        username: str,
        search_results: dict[str, Any] | None = None,
        use_schema_inspection: bool = False,
    ) -> dict[str, Any]:
        """Generate SQL from natural language query.

        Args:
            query_text: Natural language question
            dataset_ids: Optional list of dataset UUIDs to query
            username: Username for schema isolation
            search_results: Optional search results with column matches and value matches
            use_schema_inspection: Whether to use Schema Inspector Agent for dynamic schema discovery

        Returns:
            Dictionary with sql and params

        Raises:
            Exception: If SQL generation fails or validation fails
        """
        # Get schema context for validation
        schema_context: dict[str, Any] = self.get_schema_context(username, dataset_ids)

        # Retrieve cross-references if multiple datasets specified
        cross_references: list[dict[str, Any]] = []
        if dataset_ids and len(dataset_ids) > 1:
            cross_references = self.get_cross_references(username, dataset_ids)

        # Build schema description for agent (explicit table and column names)
        schema_description: str = "\n\nAVAILABLE SCHEMA (YOU MUST USE EXACTLY THESE NAMES):\n"
        schema_description += "=" * 80 + "\n"
        for table_name in schema_context["tables"]:
            columns: list[str] = schema_context["columns"].get(table_name, [])
            schema_description += f"\nTable: {table_name}\n"
            schema_description += f"Columns: {', '.join(columns)}\n"
        schema_description += "\n" + "=" * 80 + "\n"
        schema_description += (
            "⚠️  WARNING: ANY table or column name NOT listed above DOES NOT EXIST.\n"
        )
        schema_description += "⚠️  DO NOT invent, guess, or modify these names. COPY THEM EXACTLY.\n"

        # Optional: Use Schema Inspector Agent for dynamic schema discovery
        schema_inspection_task: Any | None = None
        if use_schema_inspection:
            if self.pool is None:
                raise ValueError("Database pool is required for schema inspection")

            # Initialize Schema Inspector Service
            schema_inspector_service: SchemaInspectorService = SchemaInspectorService(self.pool)

            # Set global context for tools
            set_schema_inspector_context(schema_inspector_service, username)

            # Create Schema Inspector Agent with tools
            inspector_tools: list[Any] = [
                list_datasets_tool,
                inspect_schema_tool,
                get_sample_data_tool,
            ]
            inspector_agent: Any = create_schema_inspector_agent(inspector_tools)

            # Create schema inspection task
            schema_inspection_task = create_schema_inspection_task(
                agent=inspector_agent, query_text=query_text, dataset_ids=dataset_ids
            )

        # Create SQL Generator agent
        sql_agent: Any = create_sql_generator_agent()

        # Create SQL generation task (with cross-reference context and search results)
        # If schema inspection is enabled, pass it as context
        sql_task_context: list[Any] = [schema_inspection_task] if schema_inspection_task else []
        task: Any = create_sql_generation_task(
            agent=sql_agent,
            query_text=query_text,
            dataset_ids=dataset_ids,
            cross_references=cross_references,
            search_results=search_results,
            schema_context=schema_description,  # Pass explicit schema
        )

        # Set context if schema inspection task exists
        if sql_task_context:
            task.context = sql_task_context

        # Create crew and execute
        crew_agents: list[Any] = (
            [inspector_agent, sql_agent] if schema_inspection_task else [sql_agent]
        )
        crew_tasks: list[Any] = [schema_inspection_task, task] if schema_inspection_task else [task]
        crew: Crew = Crew(agents=crew_agents, tasks=crew_tasks, verbose=False)

        # Execute crew (synchronous)
        result: Any = crew.kickoff()

        # Extract SQL from result
        sql_output: str = str(result.raw) if hasattr(result, "raw") else str(result)

        # Clean up SQL (remove markdown code blocks if present)
        cleaned_sql: str = self._clean_sql(sql_output)

        # Validate SQL against schema
        validation: dict[str, Any] = self.validate_sql_against_schema(cleaned_sql, schema_context)

        if not validation["is_valid"]:
            error_message: str = "Generated SQL contains invalid table or column names:\n"
            error_message += "\n".join(f"  - {error}" for error in validation["errors"])
            error_message += f"\n\nGenerated SQL:\n{cleaned_sql}"
            raise ValueError(error_message)

        # Extract parameters for placeholders (%s)
        # For data value queries, use keywords from query_text wrapped in % for ILIKE
        params: list[str] = []
        placeholder_count: int = cleaned_sql.count("%s")

        if placeholder_count > 0 and search_results:
            # Extract keywords from data_value_results if available
            data_value_results: list[dict[str, Any]] = search_results.get("data_value_results", [])

            if len(data_value_results) > 0:
                # Use query_text to extract the search keyword
                # Simple approach: take the last word from query (e.g., "gold" from "tell me about gold")
                query_words: list[str] = query_text.lower().split()
                keyword: str = query_words[-1] if query_words else ""

                # Create params list with keyword wrapped in % for ILIKE matching
                params = [f"%{keyword}%"] * placeholder_count

        return {
            "sql": cleaned_sql,
            "params": params,
        }

    def _clean_sql(self, raw_sql: str) -> str:
        """Clean generated SQL by removing markdown formatting.

        Args:
            raw_sql: Raw SQL string possibly with markdown

        Returns:
            Clean SQL string
        """
        # Remove markdown code block markers
        cleaned_sql: str = raw_sql.replace("```sql", "").replace("```", "")
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

    def _clean_sql(self, raw_sql: str) -> str:
        """Clean generated SQL by removing markdown formatting.

        Args:
            raw_sql: Raw SQL string possibly with markdown

        Returns:
            Clean SQL string
        """
        cleaned_sql: str = raw_sql.replace("```sql", "").replace("```", "")
        return cleaned_sql.strip()
