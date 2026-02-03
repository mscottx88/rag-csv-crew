"""CrewAI task definitions for RAG query processing.

Defines tasks for SQL generation and HTML formatting that orchestrate
the agent workflow.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from uuid import UUID

from crewai import Agent, Task


def create_sql_generation_task(
    agent: Agent, query_text: str, dataset_ids: list[UUID] | None
) -> Task:
    """Create task for generating SQL from natural language query.

    Args:
        agent: SQL Generator agent
        query_text: Natural language question from user
        dataset_ids: Optional list of dataset UUIDs to query

    Returns:
        Task configured for SQL generation

    Task Output:
    - SQL query string with parameterized placeholders
    - Query should be safe from SQL injection
    - Query should target specified datasets or all datasets
    """
    dataset_info: str = (
        f"specific datasets: {dataset_ids}" if dataset_ids else "all available datasets"
    )

    description: str = f"""Analyze the user's question and generate a SQL query to answer it.

User Question: "{query_text}"
Target Datasets: {dataset_info}

Requirements:
1. Generate a valid PostgreSQL SQL query
2. Use parameterized queries with %s placeholders for any user input
3. NEVER concatenate user input directly into SQL strings
4. Select appropriate columns to answer the question
5. Use appropriate WHERE clauses, JOINs, and aggregations as needed
6. Include LIMIT clauses where appropriate to avoid huge result sets
7. Ensure the query is efficient and readable

Output only the SQL query text, nothing else."""

    expected_output: str = "A valid PostgreSQL SQL query string with parameterized placeholders"

    task: Task = Task(description=description, expected_output=expected_output, agent=agent)
    return task


def create_html_formatting_task(
    agent: Agent, query_text: str, query_results: dict[str, Any], context: list[Task] | None = None
) -> Task:
    """Create task for formatting query results as HTML.

    Args:
        agent: Result Analyst agent
        query_text: Original user question
        query_results: SQL query results (rows, columns, count)
        context: Optional list of previous tasks for dependency

    Returns:
        Task configured for HTML formatting

    Task Output:
    - HTML content string with semantic structure
    - Plain text alternative for accessibility
    - User-friendly formatting of data
    """
    row_count: int = query_results.get("row_count", 0)
    columns: list[str] = query_results.get("columns", [])

    description: str = f"""Format the query results into readable HTML for the user.

Original Question: "{query_text}"
Results: {row_count} rows returned
Columns: {', '.join(columns) if columns else 'No columns'}

Data:
{query_results.get("rows", [])}

Requirements:
1. Use semantic HTML5 elements (article, section, table, etc.)
2. Include a clear heading that relates to the original question
3. For tabular data, use proper <table> with <thead> and <tbody>
4. For lists, use <ul> or <ol> as appropriate
5. Format numbers and dates for readability
6. Use plain, non-technical language
7. If results are empty, provide a helpful message and suggestions
8. Ensure proper heading hierarchy (h1, h2, h3)

Output the HTML content only, starting with a containing element like <article> or <div>."""

    expected_output: str = (
        "Valid semantic HTML5 content that presents the query results in a user-friendly format"
    )

    task: Task = Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context if context else [],
    )
    return task
