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

from collections.abc import Callable
import io
import re
import sys
import threading
from typing import Any
from uuid import UUID

from crewai import Crew
from psycopg import sql
from psycopg_pool import ConnectionPool

from backend.src.crew.agents import (
    create_result_analyst_agent,
    create_schema_inspector_agent,
    create_sql_generator_agent,
)
from backend.src.crew.tasks import (
    create_html_formatting_task,
    create_schema_inspection_task,
    create_sql_generation_task,
)
from backend.src.crew.tools import (
    get_sample_data_tool,
    inspect_schema_tool,
    list_datasets_tool,
    set_schema_inspector_context,
)
from backend.src.models.fusion import StrategyDispatchPlan, StrategySQL, StrategyType
from backend.src.models.index_metadata import DataColumnIndexProfile
from backend.src.services.index_manager import build_index_context, get_index_profiles
from backend.src.services.schema_inspector import SchemaInspectorService
from backend.src.utils.logging import get_structured_logger, log_event

# Get logger for query processing (T203-POLISH)
logger = get_structured_logger(__name__)

_VECTOR_PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"%s::vector")

# Multi-strategy SQL block delimiter pattern (FR-016)
_STRATEGY_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"---STRATEGY:\s*(\w+)\s*---\s*\n(.*?)\n\s*---END STRATEGY---",
    re.DOTALL,
)


def _detect_vector_placeholders(generated_sql: str) -> bool:
    """Detect %s::vector placeholders in generated SQL.

    Args:
        generated_sql: SQL string from the SQL generation agent.

    Returns:
        True if the SQL contains %s::vector placeholders.
    """
    return bool(_VECTOR_PLACEHOLDER_PATTERN.search(generated_sql))


def _resolve_vector_params(
    generated_sql: str,
    query_text: str,
) -> tuple[str, list[Any]]:
    """Resolve %s::vector placeholders by generating runtime embeddings.

    When the SQL agent generates SQL with vector similarity operators,
    this function generates the query embedding and prepares the
    parameters for execution.

    Args:
        generated_sql: SQL string with potential %s::vector placeholders.
        query_text: Original natural language query text.

    Returns:
        Tuple of (resolved_sql, vector_params) where resolved_sql has
        %s::vector replaced with %s and vector_params contains the
        embedding vectors.
    """
    if not _detect_vector_placeholders(generated_sql):
        return (generated_sql, [])

    from backend.src.services.vector_search import (  # pylint: disable=import-outside-toplevel
        VectorSearchService,
    )
    # JUSTIFICATION: VectorSearchService depends on external API keys; importing at
    # module level causes import errors in test environments without API keys configured.

    vs_service: VectorSearchService = VectorSearchService()
    query_embedding: list[float] = vs_service.generate_embedding(query_text)

    # Replace %s::vector with %s (psycopg handles the casting)
    resolved_sql: str = _VECTOR_PLACEHOLDER_PATTERN.sub("%s", generated_sql)

    # Count how many vector placeholders were replaced
    match_count: int = len(_VECTOR_PLACEHOLDER_PATTERN.findall(generated_sql))
    vector_params: list[list[float]] = [query_embedding] * match_count

    return (resolved_sql, vector_params)


def parse_multi_strategy_sql(
    raw_output: str,
    query_text: str,
) -> list[StrategySQL]:
    """Parse labeled SQL blocks from LLM multi-strategy output.

    Extracts blocks delimited by ---STRATEGY: name--- / ---END STRATEGY---
    and creates StrategySQL objects. Invalid blocks are skipped (FR-020).

    Args:
        raw_output: Raw LLM output containing labeled SQL blocks.
        query_text: Original query text for parameter extraction.

    Returns:
        List of parsed StrategySQL objects. May be fewer than
        requested if blocks are malformed or have invalid names.
    """
    valid_strategy_names: set[str] = {s.value for s in StrategyType}
    matches: list[tuple[str, str]] = _STRATEGY_BLOCK_PATTERN.findall(raw_output)

    strategies: list[StrategySQL] = []
    for strategy_name, sql_block in matches:
        name_lower: str = strategy_name.strip().lower()

        # Skip invalid strategy names (FR-020)
        if name_lower not in valid_strategy_names:
            logger.warning("Skipping invalid strategy name: %s", strategy_name)
            continue

        # Clean the SQL block
        cleaned_sql: str = _clean_sql_block(sql_block.strip())

        # Skip empty SQL blocks (FR-020)
        if not cleaned_sql:
            logger.warning("Skipping empty SQL for strategy: %s", name_lower)
            continue

        # Count %s placeholders for parameters
        placeholder_count: int = cleaned_sql.count("%s")
        params: list[str] = []
        if placeholder_count > 0:
            # Use query text as parameter value for all placeholders
            params = [f"%{query_text}%"] * placeholder_count

        strategies.append(
            StrategySQL(
                strategy_type=StrategyType(name_lower),
                sql=cleaned_sql,
                parameters=params,
            )
        )

    return strategies


def _clean_sql_block(sql_text: str) -> str:
    """Clean a SQL block from LLM output.

    Removes markdown code fences and extra whitespace.

    Args:
        sql_text: Raw SQL text from LLM output.

    Returns:
        Cleaned SQL string.
    """
    # Remove markdown code block markers
    cleaned: str = re.sub(r"```(?:sql)?\s*", "", sql_text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    # Strip whitespace
    return cleaned.strip()


def _execute_crew_with_progress(
    crew: Crew, progress_callback: Callable[[str], None] | None, progress_messages: list[str]
) -> tuple[Any, str]:
    """Execute CrewAI crew with periodic progress updates and capture agent logs.

    Args:
        crew: CrewAI Crew instance to execute
        progress_callback: Optional callback to report progress
        progress_messages: List of progress messages to cycle through

    Returns:
        Tuple of (crew_result, agent_logs) where agent_logs is captured stdout/stderr
    """
    result_container: list[Any] = []
    exception_container: list[Exception] = []
    logs_container: list[str] = []
    stop_event: threading.Event = threading.Event()

    def crew_worker() -> None:
        """Worker thread to execute crew and capture output."""
        try:
            # Capture stdout and stderr during crew execution
            stdout_capture: io.StringIO = io.StringIO()
            stderr_capture: io.StringIO = io.StringIO()
            old_stdout: Any = sys.stdout
            old_stderr: Any = sys.stderr

            try:
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture

                crew_result: Any = crew.kickoff()
                result_container.append(crew_result)
            finally:
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # Capture logs
                stdout_content: str = stdout_capture.getvalue()
                stderr_content: str = stderr_capture.getvalue()
                combined_logs: str = ""
                if stdout_content:
                    combined_logs += f"=== Agent Output ===\n{stdout_content}\n"
                if stderr_content:
                    combined_logs += f"=== Error Output ===\n{stderr_content}\n"
                logs_container.append(combined_logs)

        except Exception as e:
            exception_container.append(e)
        finally:
            stop_event.set()

    def progress_updater() -> None:
        """Periodically update progress messages."""
        message_index: int = 0
        while not stop_event.is_set():
            if progress_callback and progress_messages:
                progress_callback(progress_messages[message_index % len(progress_messages)])
                message_index += 1
            # Wait for 5 seconds or until stop event
            if stop_event.wait(timeout=5.0):
                break

    # Start crew execution in background thread
    crew_thread: threading.Thread = threading.Thread(target=crew_worker, daemon=True)
    crew_thread.start()

    # Start progress updater in background thread
    progress_thread: threading.Thread = threading.Thread(target=progress_updater, daemon=True)
    progress_thread.start()

    # Wait for crew to complete
    crew_thread.join()

    # Stop progress updater
    stop_event.set()
    progress_thread.join(timeout=1.0)

    # Check for exceptions
    if exception_container:
        raise exception_container[0]

    crew_result: Any = result_container[0] if result_container else None
    agent_logs: str = logs_container[0] if logs_container else ""
    return (crew_result, agent_logs)


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

        # Extract CTE names from WITH ... AS clauses so we don't flag them as missing tables
        cte_pattern: str = r"\bWITH\s+(?:RECURSIVE\s+)?(\w+)\s+AS\s*\("
        cte_continuation_pattern: str = r"\)\s*,\s*(\w+)\s+AS\s*\("
        cte_names: set[str] = set()
        for cte_match in re.finditer(cte_pattern, sql_query, re.IGNORECASE):
            cte_names.add(cte_match.group(1).lower())
        for cte_match in re.finditer(cte_continuation_pattern, sql_query, re.IGNORECASE):
            cte_names.add(cte_match.group(1).lower())

        # Extract table names from SQL (FROM and JOIN clauses)
        # Simplified regex - matches table names after FROM or JOIN
        table_pattern: str = r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)"
        referenced_tables: list[str] = re.findall(table_pattern, sql_query, re.IGNORECASE)

        # Check each referenced table (skip CTE names — they're query-defined, not real tables)
        for table in referenced_tables:
            table_lower: str = table.lower()
            if table_lower in cte_names:
                continue
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

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    # JUSTIFICATION: Orchestration method coordinates schema context retrieval,
    # index context building, CrewAI crew assembly, multi-strategy output
    # parsing, retry on zero blocks, and fallback to single-strategy.
    # Splitting would fragment the linear flow without meaningful benefit.
    def generate_multi_strategy_sql(  # pylint: disable=too-many-positional-arguments
        # TODO(pylint-refactor): Refactor to use config object or keyword-only args
        self,
        query_text: str,
        username: str,
        dataset_ids: list[UUID] | None,
        search_results: dict[str, Any],
        strategy_dispatch: StrategyDispatchPlan,
        *,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[StrategySQL]:
        """Generate SQL for multiple query strategies in a single LLM call.

        Args:
            query_text: The user's natural language query.
            username: For schema isolation.
            dataset_ids: Target datasets (None = all user datasets).
            search_results: Column discovery results from hybrid search.
            strategy_dispatch: Which strategies to generate SQL for.
            progress_callback: Optional progress reporting callback.

        Returns:
            List of StrategySQL objects, one per generated strategy.
            Falls back to single-strategy on total parse failure.
        """
        if progress_callback:
            progress_callback("Generating multi-strategy SQL...")

        # Build schema context
        schema_context: dict[str, Any] = self.get_schema_context(username, dataset_ids)
        schema_description: str = "\n\nAVAILABLE SCHEMA (YOU MUST USE EXACTLY THESE NAMES):\n"
        schema_description += "=" * 80 + "\n"
        for table_name in schema_context["tables"]:
            columns: list[str] = schema_context["columns"].get(table_name, [])
            schema_description += f"\nTable: {table_name}\n"
            schema_description += f"Columns: {', '.join(columns)}\n"
        schema_description += "\n" + "=" * 80 + "\n"

        # Build index context
        index_context: str = ""
        if self.pool is not None:
            try:
                table_names_map: dict[str, str] = {}
                with (
                    self.pool.connection() as idx_conn,
                    idx_conn.cursor() as cur,
                ):
                    idx_schema: str = f"{username}_schema"
                    cur.execute(
                        sql.SQL("SET search_path TO {}, public").format(sql.Identifier(idx_schema))
                    )
                    if dataset_ids:
                        ds_strs: list[str] = [str(d) for d in dataset_ids]
                        cur.execute(
                            "SELECT id::text, table_name FROM datasets WHERE id = ANY(%s)",
                            (ds_strs,),
                        )
                    else:
                        cur.execute("SELECT id::text, table_name FROM datasets")
                    ds_rows: list[tuple[str, ...]] = cur.fetchall()
                    for ds_row in ds_rows:
                        table_names_map[str(ds_row[0])] = str(ds_row[1])

                resolved_ids: list[str] = list(table_names_map.keys())
                if resolved_ids:
                    with self.pool.connection() as idx_conn_2:
                        index_profiles: dict[str, list[DataColumnIndexProfile]] = (
                            get_index_profiles(idx_conn_2, username, resolved_ids)
                        )
                    if index_profiles:
                        index_context = build_index_context(index_profiles, table_names_map)
            except Exception as idx_err:  # pylint: disable=broad-exception-caught
                # JUSTIFICATION: Index context is enhancement, not critical.
                log_event(
                    logger=logger,
                    level="warning",
                    event="index_context_retrieval_failed",
                    user=username,
                    extra={"error": str(idx_err)},
                )

        # Create SQL generation task with multi-strategy dispatch
        sql_agent: Any = create_sql_generator_agent()
        task: Any = create_sql_generation_task(
            agent=sql_agent,
            query_text=query_text,
            dataset_ids=dataset_ids,
            search_results=search_results,
            schema_context=schema_description,
            index_context=index_context if index_context else None,
            strategy_dispatch=strategy_dispatch,
        )

        crew: Crew = Crew(agents=[sql_agent], tasks=[task], verbose=False)

        progress_messages: list[str] = [
            "SQL Generator creating multi-strategy SQL...",
            "Generating structured query strategy...",
            "Generating search strategy variants...",
            "Finalizing multi-strategy SQL blocks...",
        ]

        result: Any
        _agent_logs: str
        result, _agent_logs = _execute_crew_with_progress(
            crew=crew,
            progress_callback=progress_callback,
            progress_messages=progress_messages,
        )

        raw_output: str = str(result.raw) if hasattr(result, "raw") else str(result)

        if progress_callback:
            progress_callback("Parsing multi-strategy SQL output...")

        # Parse multi-strategy output (attempt 1)
        strategy_sqls: list[StrategySQL] = parse_multi_strategy_sql(raw_output, query_text)

        # Retry once on zero valid blocks (FR-016)
        if not strategy_sqls:
            log_event(
                logger=logger,
                level="warning",
                event="multi_strategy_parse_failed_retry",
                user=username,
                extra={"attempt": 1},
            )
            if progress_callback:
                progress_callback("Retrying multi-strategy SQL generation...")

            result, _retry_logs = _execute_crew_with_progress(
                crew=Crew(agents=[sql_agent], tasks=[task], verbose=False),
                progress_callback=progress_callback,
                progress_messages=progress_messages,
            )
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)
            strategy_sqls = parse_multi_strategy_sql(raw_output, query_text)

        # Fallback to single-strategy on double failure (FR-016)
        if not strategy_sqls:
            log_event(
                logger=logger,
                level="warning",
                event="multi_strategy_fallback_single",
                user=username,
                extra={"reason": "zero_blocks_after_retry"},
            )
            if progress_callback:
                progress_callback("Falling back to single-strategy SQL...")
            fallback_result: dict[str, Any] = self.generate_sql(
                query_text=query_text,
                dataset_ids=dataset_ids,
                username=username,
                search_results=search_results,
                use_schema_inspection=True,
                progress_callback=progress_callback,
            )
            strategy_sqls = [
                StrategySQL(
                    strategy_type=StrategyType.STRUCTURED,
                    sql=fallback_result["sql"],
                    parameters=fallback_result["params"],
                )
            ]

        return strategy_sqls

    # pylint: enable=too-many-locals,too-many-branches,too-many-statements

    def generate_sql(
        self,
        query_text: str,
        dataset_ids: list[UUID] | None,
        username: str,
        search_results: dict[str, Any] | None = None,
        use_schema_inspection: bool = False,
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Generate SQL from natural language query.

        Args:
            query_text: Natural language question
            dataset_ids: Optional list of dataset UUIDs to query
            username: Username for schema isolation
            search_results: Optional search results with column matches and value matches
            use_schema_inspection: Whether to use Schema Inspector Agent for dynamic schema discovery
            progress_callback: Optional callback to report progress messages

        Returns:
            Dictionary with sql, params, and agent_logs fields

        Raises:
            Exception: If SQL generation fails or validation fails
        """
        if progress_callback:
            progress_callback("Loading database schema context for SQL generation...")

        # Get schema context for validation
        schema_context: dict[str, Any] = self.get_schema_context(username, dataset_ids)

        # Report which tables were loaded
        tables: list[str] = schema_context["tables"]
        if progress_callback and tables:
            table_list: str = (
                ", ".join(tables)
                if len(tables) <= 5
                else f"{', '.join(tables[:5])} and {len(tables) - 5} more"
            )
            progress_callback(f"Loaded schema for tables: {table_list}")

        # Retrieve cross-references if multiple datasets specified
        cross_references: list[dict[str, Any]] = []
        if dataset_ids and len(dataset_ids) > 1:
            if progress_callback:
                progress_callback(f"Analyzing relationships between {len(dataset_ids)} datasets...")
            cross_references = self.get_cross_references(username, dataset_ids)
            if progress_callback and cross_references:
                # List the tables involved in relationships
                relationship_tables: set[str] = set()
                for ref in cross_references:
                    relationship_tables.add(ref.get("from_table", ""))
                    relationship_tables.add(ref.get("to_table", ""))
                relationship_tables.discard("")
                tables_str: str = ", ".join(sorted(relationship_tables))
                progress_callback(
                    f"Found {len(cross_references)} relationships between tables: {tables_str}"
                )

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

            if progress_callback:
                table_list_inspector: str = (
                    ", ".join(tables)
                    if len(tables) <= 5
                    else f"{', '.join(tables[:5])} and {len(tables) - 5} more"
                )
                progress_callback(
                    f"Creating Schema Inspector Agent to analyze: {table_list_inspector}..."
                )

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

            if progress_callback:
                progress_callback(
                    "Schema Inspector Agent tools ready (list_datasets, inspect_schema, get_sample_data)"
                )

            # Create schema inspection task
            schema_inspection_task = create_schema_inspection_task(
                agent=inspector_agent, query_text=query_text, dataset_ids=dataset_ids
            )

            if progress_callback:
                progress_callback(
                    f"Schema Inspector Agent will examine {len(tables)} table(s) for relevant columns"
                )

        # Retrieve index capabilities context for SQL generation (FR-017)
        index_context: str = ""
        if self.pool is not None:
            try:
                # Resolve dataset IDs and table names in a single query
                table_names_map: dict[str, str] = {}
                with self.pool.connection() as idx_conn, idx_conn.cursor() as cur:
                    idx_schema: str = f"{username}_schema"
                    cur.execute(
                        sql.SQL("SET search_path TO {}, public").format(sql.Identifier(idx_schema))
                    )
                    if dataset_ids:
                        dataset_id_strs: list[str] = [str(d) for d in dataset_ids]
                        cur.execute(
                            "SELECT id::text, table_name FROM datasets WHERE id = ANY(%s)",
                            (dataset_id_strs,),
                        )
                    else:
                        cur.execute("SELECT id::text, table_name FROM datasets")

                    ds_rows: list[tuple[str, ...]] = cur.fetchall()
                    for ds_row in ds_rows:
                        table_names_map[str(ds_row[0])] = str(ds_row[1])

                resolved_ids: list[str] = list(table_names_map.keys())

                if resolved_ids:
                    with self.pool.connection() as idx_conn_2:
                        index_profiles: dict[str, list[DataColumnIndexProfile]] = (
                            get_index_profiles(idx_conn_2, username, resolved_ids)
                        )

                    if index_profiles:
                        index_context = build_index_context(
                            index_profiles,
                            table_names_map,
                        )

                        if progress_callback and index_context:
                            profile_count: int = sum(len(p) for p in index_profiles.values())
                            progress_callback(
                                f"Loaded index capabilities for {profile_count} columns"
                            )
            except Exception as idx_err:  # pylint: disable=broad-exception-caught
                # JUSTIFICATION: Index context is enhancement, not critical.
                # If index retrieval fails, SQL generation proceeds without
                # it (agent falls back to standard behavior per FR-017).
                log_event(
                    logger=logger,
                    level="warning",
                    event="index_context_retrieval_failed",
                    user=username,
                    extra={"error": str(idx_err)},
                )

        if progress_callback:
            progress_callback("Creating SQL Generator Agent for query translation...")

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
            index_context=index_context if index_context else None,
        )

        # Set context if schema inspection task exists
        if sql_task_context:
            task.context = sql_task_context

        # Create crew and execute
        crew_agents: list[Any] = (
            [inspector_agent, sql_agent] if schema_inspection_task else [sql_agent]
        )
        crew_tasks: list[Any] = [schema_inspection_task, task] if schema_inspection_task else [task]

        if progress_callback:
            agent_count: int = len(crew_agents)
            task_count: int = len(crew_tasks)
            progress_callback(
                f"Starting CrewAI with {agent_count} agent(s) and {task_count} task(s)..."
            )

        crew: Crew = Crew(agents=crew_agents, tasks=crew_tasks, verbose=False)

        # Prepare rotating progress messages for long crew execution
        progress_messages: list[str] = []
        if use_schema_inspection:
            progress_messages = [
                "Schema Inspector Agent analyzing database structure...",
                "Schema Inspector Agent inspecting tables and columns...",
                "Schema Inspector Agent retrieving sample data...",
                "SQL Generator Agent planning query structure...",
                "SQL Generator Agent translating natural language to SQL...",
                "SQL Generator Agent optimizing query performance...",
                "Agents collaborating on final SQL query...",
            ]
        else:
            progress_messages = [
                "SQL Generator Agent analyzing query requirements...",
                "SQL Generator Agent translating natural language to SQL...",
                "SQL Generator Agent mapping columns from schema...",
                "SQL Generator Agent constructing WHERE clauses...",
                "SQL Generator Agent optimizing query structure...",
                "SQL Generator Agent finalizing SQL query...",
            ]

        if progress_callback:
            progress_callback("Starting agent execution...")

        # Execute crew with periodic progress updates and capture agent logs
        result: Any
        agent_logs: str
        result, agent_logs = _execute_crew_with_progress(
            crew=crew, progress_callback=progress_callback, progress_messages=progress_messages
        )

        if progress_callback:
            progress_callback("CrewAI execution complete, extracting generated SQL...")

        # Extract SQL from result
        sql_output: str = str(result.raw) if hasattr(result, "raw") else str(result)

        if progress_callback:
            progress_callback("Cleaning SQL output (removing markdown formatting)...")

        # Clean up SQL (remove markdown code blocks if present)
        cleaned_sql: str = self._clean_sql(sql_output)

        if progress_callback:
            progress_callback("Validating SQL against database schema...")

        # Validate SQL against schema
        validation: dict[str, Any] = self.validate_sql_against_schema(cleaned_sql, schema_context)

        if not validation["is_valid"]:
            if progress_callback:
                progress_callback(
                    f"SQL validation failed: {len(validation['errors'])} error(s) found"
                )
            error_message: str = "Generated SQL contains invalid table or column names:\n"
            error_message += "\n".join(f"  - {error}" for error in validation["errors"])
            error_message += f"\n\nGenerated SQL:\n{cleaned_sql}"
            raise ValueError(error_message)

        if progress_callback:
            progress_callback("SQL validation passed, preparing parameterized query...")

        # Extract parameters for placeholders (%s)
        params: list[str] = self._extract_query_parameters(
            cleaned_sql, query_text, search_results, progress_callback
        )

        return {
            "sql": cleaned_sql,
            "params": params,
            "agent_logs": agent_logs,
        }

    def _extract_query_parameters(
        self,
        sql: str,
        query_text: str,
        search_results: dict[str, Any] | None,
        progress_callback: Callable[[str], None] | None,
    ) -> list[str]:
        """Extract parameter values for SQL placeholders using intelligent keyword detection.

        Extraction priority:
        1. Use actual matched values from data_value_results (most accurate)
        2. Smart keyword extraction (look for filter values near column names)
        3. Fallback to last significant word (legacy behavior)

        Args:
            sql: Generated SQL query with %s placeholders
            query_text: Original natural language query
            search_results: Optional search results with data_value_results
            progress_callback: Optional callback to report progress

        Returns:
            List of parameter values (empty if no placeholders)

        Examples:
            Query: "show me video sales by hour"
            SQL: "WHERE type ILIKE %s"
            Returns: ["%video%"]

            Query: "sales for customer Smith in 2024"
            SQL: "WHERE customer ILIKE %s AND year = %s"
            Returns: ["%smith%", "%2024%"]
        """
        params: list[str] = []
        placeholder_count: int = sql.count("%s")

        if placeholder_count == 0:
            return params

        if progress_callback:
            progress_callback(f"Extracting {placeholder_count} parameter value(s) from query...")

        # Strategy 1: Use data_value_results if available (most accurate)
        if search_results:
            data_value_results: list[dict[str, Any]] = search_results.get("data_value_results", [])

            if len(data_value_results) > 0:
                # Extract the actual matched values from search results
                matched_values: list[str] = []
                for result in data_value_results[:placeholder_count]:
                    matched_value: str = result.get("matched_value", "")
                    if matched_value:
                        matched_values.append(f"%{matched_value}%")

                if len(matched_values) == placeholder_count:
                    if progress_callback:
                        values_str: str = ", ".join(matched_values)
                        progress_callback(f"Using matched values from search: {values_str}")
                    return matched_values

        # Strategy 2: Smart keyword extraction from query text
        keywords: list[str] = self._extract_filter_keywords(sql, query_text)

        if len(keywords) >= placeholder_count:
            params = [f"%{kw}%" for kw in keywords[:placeholder_count]]
            if progress_callback:
                keywords_str: str = ", ".join(keywords[:placeholder_count])
                progress_callback(f"Extracted filter keywords: {keywords_str}")
            return params

        # Strategy 3: Fallback to last significant word (legacy behavior)
        # Filter out common stop words and query structure words
        stop_words: set[str] = {
            "show",
            "me",
            "the",
            "a",
            "an",
            "all",
            "by",
            "for",
            "in",
            "on",
            "at",
            "from",
            "to",
            "of",
            "with",
            "about",
            "tell",
            "give",
            "get",
            "find",
            "display",
            "list",
            "see",
            "view",
            "hour",
            "day",
            "month",
            "year",
            "time",
            "date",
            "detailed",
            "analysis",
            "report",
            "data",
            "sales",
        }

        query_words: list[str] = [
            word.strip(",.!?;:")
            for word in query_text.lower().split()
            if word.strip(",.!?;:") not in stop_words and len(word.strip(",.!?;:")) > 2
        ]

        if query_words:
            # Take the last significant word
            keyword: str = query_words[-1] if query_words else ""
            params = [f"%{keyword}%"] * placeholder_count

            if progress_callback:
                progress_callback(f"Fallback: using keyword '{keyword}' for all parameters")

        return params

    def _extract_filter_keywords(self, sql: str, query_text: str) -> list[str]:
        """Extract filter keywords from query text based on SQL WHERE clause context.

        Analyzes the SQL WHERE clause to identify column names being filtered,
        then extracts corresponding keywords from the natural language query.

        Args:
            sql: Generated SQL query
            query_text: Original natural language query

        Returns:
            List of extracted filter keywords

        Examples:
            SQL: "WHERE type ILIKE %s"
            Query: "show me video sales by hour"
            Returns: ["video"] (matches "type" column)

            SQL: "WHERE customer ILIKE %s AND status ILIKE %s"
            Query: "find orders for Smith with pending status"
            Returns: ["smith", "pending"]
        """
        keywords: list[str] = []

        # Extract WHERE clause from SQL
        where_match: re.Match[str] | None = re.search(
            r"WHERE\s+(.+?)(?:GROUP BY|ORDER BY|LIMIT|$)", sql, re.IGNORECASE
        )
        if not where_match:
            return keywords

        where_clause: str = where_match.group(1).lower()

        # Find column names before ILIKE %s or = %s
        # Pattern: column_name ILIKE %s or column_name = %s
        column_patterns: list[re.Match[str]] = list(
            re.finditer(r"(\w+)\s+(?:ILIKE|=|LIKE)\s+%s", where_clause, re.IGNORECASE)
        )

        # Common column name to keyword mappings
        column_keywords: dict[str, list[str]] = {
            "type": ["type", "kind", "category"],
            "category": ["category", "type", "kind"],
            "status": ["status", "state", "condition"],
            "name": ["name", "called", "named"],
            "customer": ["customer", "client", "buyer"],
            "product": ["product", "item", "goods"],
            "city": ["city", "town", "location"],
            "state": ["state", "province", "region"],
            "country": ["country", "nation"],
        }

        query_lower: str = query_text.lower()

        for col_match in column_patterns:
            column_name: str = col_match.group(1)

            # Get possible keywords for this column type
            possible_keywords: list[str] = column_keywords.get(column_name, [column_name])

            # Find the keyword in the query text near the column keyword
            for keyword in possible_keywords:
                # Look for pattern: "keyword_name value" (e.g., "type video", "status pending")
                pattern: str = rf"{keyword}\s+(\w+)"
                value_match: re.Match[str] | None = re.search(pattern, query_lower)

                if value_match:
                    keywords.append(value_match.group(1))
                    break
            else:
                # Fallback: look for any word that might be a value
                # Common patterns: "all X sales", "X customers", "X products"
                words: list[str] = query_lower.split()

                # Filter out stop words and find potential values
                stop_words: set[str] = {
                    "show",
                    "me",
                    "the",
                    "a",
                    "an",
                    "all",
                    "by",
                    "for",
                    "in",
                    "on",
                    "of",
                    "with",
                    "about",
                    "tell",
                    "find",
                    "get",
                    "sales",
                    "analysis",
                    "hour",
                    "day",
                    "month",
                    "year",
                    "time",
                    "date",
                    "detailed",
                    "report",
                }

                for word in words:
                    word_clean: str = word.strip(",.!?;:")
                    if (
                        word_clean not in stop_words
                        and len(word_clean) > 2
                        and any(
                            agg in query_lower for agg in ["sales", "orders", "customers", "by"]
                        )
                    ):
                        keywords.append(word_clean)
                        break

        return keywords

    def _clean_sql(self, raw_sql: str) -> str:
        """Clean generated SQL by extracting SQL from LLM response.

        Handles cases where the LLM returns prose mixed with SQL code blocks.
        Extracts the last (most refined) SQL block from markdown fences, or
        falls back to stripping markdown markers if no fenced blocks found.

        Args:
            raw_sql: Raw SQL string possibly with markdown and prose

        Returns:
            Clean SQL string
        """
        # Strategy 1: Extract SQL from markdown code blocks (```sql ... ``` or ``` ... ```)
        # Use the LAST fenced block since LLMs often refine their answer
        code_block_pattern: str = r"```(?:sql)?\s*\n?(.*?)```"
        matches: list[str] = re.findall(code_block_pattern, raw_sql, re.DOTALL | re.IGNORECASE)

        if matches:
            # Use the last code block (LLMs often say "here's a better version" at the end)
            extracted_sql: str = matches[-1].strip()
            if extracted_sql:
                return extracted_sql

        # Strategy 2: No markdown fences found — try to extract SQL by finding
        # the first SQL statement keyword and taking everything from there
        # Look for common SQL statement starts
        sql_start_pattern: str = r"(?:^|\n)\s*((?:WITH|SELECT|INSERT|UPDATE|DELETE)\b.*)"
        sql_match: re.Match[str] | None = re.search(
            sql_start_pattern, raw_sql, re.DOTALL | re.IGNORECASE
        )
        if sql_match:
            extracted_sql = sql_match.group(1).strip()
            # Remove any trailing prose after the SQL (text after final semicolon)
            semicolon_idx: int = extracted_sql.rfind(";")
            if semicolon_idx != -1:
                extracted_sql = extracted_sql[: semicolon_idx + 1]
            return extracted_sql

        # Strategy 3: Fallback — just strip markdown markers
        cleaned_sql: str = raw_sql.replace("```sql", "").replace("```", "")
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
        # Log query processing start (T203-POLISH: Structured logging for query processing)
        from datetime import datetime  # pylint: disable=import-outside-toplevel

        query_start_time: datetime = datetime.now()
        log_event(
            logger=logger,
            level="info",
            event="query_submit",
            user=username,
            extra={
                "query_text": query_text[:100],  # Truncate for logging
                "dataset_count": len(dataset_ids) if dataset_ids else 0,
            },
        )

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

        # Log successful query processing (T203-POLISH)
        query_time_ms: int = int((datetime.now() - query_start_time).total_seconds() * 1000)
        log_event(
            logger=logger,
            level="info",
            event="query_complete",
            user=username,
            extra={
                "query_text": query_text[:100],  # Truncate for logging
                "execution_time_ms": query_time_ms,
                "result_count": mock_results["row_count"],
                "sql_length": len(generated_sql),
                "html_length": len(html_content),
            },
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
