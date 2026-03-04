"""CrewAI task definitions for RAG query processing.

Defines tasks for SQL generation and HTML formatting that orchestrate
the agent workflow.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from crewai import Agent, Task

if TYPE_CHECKING:
    from backend.src.models.fusion import StrategyDispatchPlan


def create_sql_generation_task(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    # TODO(pylint-refactor): Refactor to use config object or keyword-only args
    agent: Agent,
    query_text: str,
    dataset_ids: list[UUID] | None,
    cross_references: list[dict[str, Any]] | None = None,
    search_results: dict[str, Any] | None = None,
    schema_context: str | None = None,
    index_context: str | None = None,
    strategy_dispatch: StrategyDispatchPlan | None = None,
) -> Task:
    """Create task for generating SQL from natural language query.

    Args:
        agent: SQL Generator agent
        query_text: Natural language question from user
        dataset_ids: Optional list of dataset UUIDs to query
        cross_references: Optional list of cross-reference relationships for JOIN generation
        search_results: Optional column search results with data value matches
        schema_context: Optional explicit schema description with valid table/column names
        index_context: Optional index capabilities context from build_index_context().
            When provided, appended after schema_context and new FTS/vector
            requirements are added. When None, agent falls back to current
            behavior per FR-017.
        strategy_dispatch: Optional strategy dispatch plan for multi-strategy
            SQL generation. When provided, the prompt includes labeled block
            delimiters and per-strategy guidelines.

    Returns:
        Task configured for SQL generation

    Task Output:
    - SQL query string with parameterized placeholders
    - Query should be safe from SQL injection
    - Query should target specified datasets or all datasets
    - Query should use JOINs when cross-references are available

    When strategy_dispatch is provided with multiple strategies, the
    task description includes multi-strategy SQL generation instructions
    with labeled block delimiters per FR-016.
    """
    dataset_info: str = (
        f"specific datasets: {dataset_ids}" if dataset_ids else "all available datasets"
    )

    # Build cross-reference context if available
    join_context: str = ""
    if cross_references:
        join_context = "\n\nAvailable Relationships (for JOIN clauses):\n"
        for ref in cross_references:
            join_context += (
                f"- {ref['source_dataset_id']}.{ref['source_column']} "
                f"→ {ref['target_dataset_id']}.{ref['target_column']} "
                f"({ref['relationship_type']}, confidence: {ref['confidence_score']:.2f})\n"
            )
        join_context += (
            "\nUse these relationships to JOIN tables when the question "
            "requires data from multiple datasets."
        )

    # Build value match context if available
    value_context: str = ""
    if search_results:
        fused_results: list[dict[str, Any]] = search_results.get("fused_results", [])
        data_value_matches: list[dict[str, Any]] = [
            r for r in fused_results if r.get("source") == "data_values"
        ]

        if data_value_matches:
            value_context = (
                "\n\nIMPORTANT: The search found matches in DATA VALUES, not column names:\n"
            )
            for match in data_value_matches[:3]:  # Show top 3
                value_context += (
                    f"- Column '{match['column_name']}' contains '{query_text}' "
                    f"in {match['match_count']} rows\n"
                )
                if match.get("sample_values"):
                    samples: str = ", ".join([f"'{v}'" for v in match["sample_values"][:2]])
                    value_context += f"  Sample values: {samples}\n"

            if index_context:
                value_context += (
                    "\nThis is a VALUE-BASED QUERY. Use full-text search operators"
                    " (plainto_tsquery, ts_rank) to find matching rows when the"
                    " column has a full-text search index — see INDEX CAPABILITIES"
                    " section for the correct _ts_ column names."
                    " Fall back to ILIKE only for columns without full-text indexes"
                    " or when substring matching is required.\n"
                )
            else:
                value_context += (
                    "\nThis is a VALUE-BASED QUERY. Generate a WHERE clause using"
                    " ILIKE to search for the query term within these columns.\n"
                    f"Example: WHERE column_name ILIKE '%{query_text}%'\n"
                )

    # Include explicit schema context if provided
    schema_info: str = schema_context if schema_context else ""

    # Include index capabilities context if provided (per FR-017)
    index_info: str = ""
    if index_context:
        index_info = f"\n\n{index_context}"

    # Add FTS/vector requirements when index context is available
    index_requirements: str = ""
    if index_context:
        index_requirements = (
            "\n11. PREFER full-text search operators (@@, ts_rank,"
            " plainto_tsquery) over ILIKE for text searches when a"
            " full-text search index is available on the column."
            " See INDEX CAPABILITIES section."
            "\n12. For semantic or meaning-based searches, use vector"
            " cosine distance (<=> operator) when vector indexes"
            " are available. See INDEX CAPABILITIES section."
        )

    description: str = f"""Analyze the user's question and generate a SQL query to answer it.

User Question: "{query_text}"
Target Datasets: {dataset_info}{schema_info}{index_info}{join_context}{value_context}

Requirements:
1. Generate a valid PostgreSQL SQL query
2. Use parameterized queries with %s placeholders for any user input
3. NEVER concatenate user input directly into SQL strings
4. Select appropriate columns to answer the question
5. Use appropriate WHERE clauses, JOINs, and aggregations as needed
6. When multiple datasets are involved, use the provided relationships to JOIN tables
7. For foreign_key relationships, use INNER JOIN (or LEFT JOIN if optional)
8. For shared_values relationships, use INNER JOIN on matching values
9. Include LIMIT clauses where appropriate to avoid huge result sets
10. Ensure the query is efficient and readable{index_requirements}

Output only the SQL query text, nothing else."""

    # Multi-strategy prompt injection (FR-016)
    multi_strategy_section: str = ""
    if strategy_dispatch is not None and len(strategy_dispatch.strategies) > 1:
        strategy_names: list[str] = [s.value for s in strategy_dispatch.strategies]
        block_examples: str = "\n\n".join(
            f"---STRATEGY: {name}---\n<your {name} SQL here>\n---END STRATEGY---"
            for name in strategy_names
        )
        multi_strategy_section = f"""

MULTI-STRATEGY SQL GENERATION
{'=' * 80}
Generate SEPARATE SQL queries for each of the following strategies.
Each query MUST include 'ctid' as the first column in the SELECT list.
Each query MUST end with LIMIT 50.

Wrap each query in the following delimiters:

{block_examples}

STRATEGY GUIDELINES:
- structured: Use standard WHERE, JOIN, GROUP BY, ORDER BY with B-tree indexes.
  Always include ctid as the first SELECT column.
- fulltext: Use plainto_tsquery, @@, ts_rank operators on _ts_ columns.
  Always include ctid as the first SELECT column.
  The search terms should reflect the user's query intent.
- vector: Use <=> cosine distance operator on _emb_ columns with %s::vector placeholder.
  Always include ctid as the first SELECT column.
  The query concept for embedding should reflect the user's semantic intent.

If the user's question is an AGGREGATION (COUNT, SUM, AVG, MIN, MAX, GROUP BY),
generate ONLY the structured strategy. Do NOT generate fulltext or vector strategies
for aggregation queries.
{'=' * 80}"""
        description = description + multi_strategy_section

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


def create_keyword_search_task(
    agent: Agent, query_text: str, dataset_ids: list[UUID] | None
) -> Task:
    """Create task for keyword-based full-text column search.

    Args:
        agent: Keyword Search agent
        query_text: Natural language query to search for
        dataset_ids: Optional list of dataset UUIDs to filter results

    Returns:
        Task configured for keyword search

    Task Output:
    - List of matching columns ranked by text relevance (ts_rank)
    - Each result includes column_name, dataset_id, and rank score
    - Results ordered by descending relevance
    """
    dataset_info: str = (
        f"specific datasets: {dataset_ids}" if dataset_ids else "all available datasets"
    )

    description: str = f"""Find columns that match the query using full-text keyword search.

Query: "{query_text}"
Target Datasets: {dataset_info}

Search Strategy:
1. Use PostgreSQL full-text search with tsvector and ts_rank
2. Match keywords against column names and descriptions
3. Apply AND/OR Boolean logic for multi-word queries
4. Rank results by text relevance score (ts_rank)
5. Prioritize exact matches over partial matches
6. Return columns ordered by descending relevance

Requirements:
- Use plainto_tsquery() for natural language processing
- Query against _fulltext tsvector columns
- Return top 10 most relevant columns
- Include column_name, dataset_id, and rank score for each result

Output a JSON list of matching columns with their relevance scores."""

    expected_output: str = (
        "JSON list of columns ranked by keyword relevance, "
        "including column_name, dataset_id, and rank score"
    )

    task: Task = Task(description=description, expected_output=expected_output, agent=agent)
    return task


def create_vector_search_task(
    agent: Agent, query_text: str, dataset_ids: list[UUID] | None
) -> Task:
    """Create task for semantic vector similarity column search.

    Args:
        agent: Vector Search agent
        query_text: Natural language query to search for
        dataset_ids: Optional list of dataset UUIDs to filter results

    Returns:
        Task configured for vector similarity search

    Task Output:
    - List of matching columns ranked by semantic similarity
    - Each result includes column_name, dataset_id, distance, and similarity score
    - Results ordered by descending similarity (lowest distance first)
    """
    dataset_info: str = (
        f"specific datasets: {dataset_ids}" if dataset_ids else "all available datasets"
    )

    description: str = f"""Find columns that are semantically similar to the query using vector
embeddings.

Query: "{query_text}"
Target Datasets: {dataset_info}

Search Strategy:
1. Generate embedding for the query using OpenAI text-embedding-3-small
2. Use pgvector cosine distance (<=> operator) for similarity search
3. Find columns with similar semantic meaning, not just keyword matches
4. Understand synonyms (revenue = income = earnings)
5. Recognize related concepts (customer = client = buyer)
6. Convert distance to similarity score: similarity = 1 - (distance / 2)

Requirements:
- Generate 1536-dimensional embedding for query
- Query against embedding column using cosine distance
- Return top 10 most similar columns
- Include column_name, dataset_id, distance, and similarity score
- Order by ascending distance (descending similarity)

Output a JSON list of semantically similar columns with their similarity scores."""

    expected_output: str = (
        "JSON list of columns ranked by semantic similarity, "
        "including column_name, dataset_id, distance, and similarity score"
    )

    task: Task = Task(description=description, expected_output=expected_output, agent=agent)
    return task


def create_schema_inspection_task(
    agent: Agent, query_text: str, dataset_ids: list[UUID] | None
) -> Task:
    """Create task for inspecting database schema before SQL generation.

    Args:
        agent: Schema Inspector agent with schema inspection tools
        query_text: Natural language query to understand context
        dataset_ids: Optional list of dataset UUIDs to inspect

    Returns:
        Task configured for schema inspection

    Task Output:
    - Complete schema information including table names, column names, and types
    - Sample data for understanding data structure
    - Used as context for SQL generation task
    """
    dataset_info: str = (
        f"specific datasets: {dataset_ids}" if dataset_ids else "all available datasets"
    )

    description: str = f"""Inspect the database schema to provide accurate context for SQL query generation.

Query: "{query_text}"
Target Datasets: {dataset_info}

Your Task:
1. Use the list_datasets tool to discover available tables
2. For each relevant dataset, use inspect_schema tool to get exact table and column names
3. Optionally use get_sample_data tool to understand data structure (if helpful for the query)
4. Provide a clear summary of the schema including:
   - Exact table names
   - Exact column names with their types
   - Sample data (if retrieved)

CRITICAL INSTRUCTIONS:
- ALWAYS use tools - DO NOT guess or rely on prior knowledge
- Provide EXACT names as returned by the tools
- Include data types for all columns
- Be thorough but concise

Output Format:
Provide a structured summary that includes:
- Available Tables: [list with exact names]
- Schema Details: [for each table, list columns with types]
- Sample Data: [if helpful, show a few example rows]

This information will guide SQL query generation."""

    expected_output: str = (
        "Structured schema summary with exact table names, column names, "
        "types, and optional sample data"
    )

    task: Task = Task(description=description, expected_output=expected_output, agent=agent)
    return task
