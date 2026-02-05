"""CrewAI agent definitions for RAG query processing.

Defines SQL Generator and Result Analyst agents for converting natural language
queries to SQL and formatting results as HTML.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

from crewai import Agent

from src.utils.llm_config import get_llm_for_crew


def create_sql_generator_agent() -> Agent:
    """Create SQL Generator agent for text-to-SQL conversion.

    The agent specializes in converting natural language questions into
    parameterized SQL queries with security focus on preventing SQL injection.

    Returns:
        Agent configured for SQL generation

    Agent Characteristics:
    - Role: Text-to-SQL specialist
    - Goal: Generate safe, parameterized SQL queries
    - Security: Emphasizes SQL injection prevention
    - Knowledge: Database schema, SQL best practices
    """
    llm: Any = get_llm_for_crew()
    agent: Agent = Agent(
        role="Database Query Specialist",
        goal=(
            "Convert natural language questions into accurate, secure SQL queries "
            "that retrieve the requested data, including multi-table JOINs when needed"
        ),
        backstory="""You are an expert database analyst who specializes in understanding
        user questions and translating them into precise SQL queries. You have deep knowledge
        of SQL syntax, query optimization, and database security best practices.

        CRITICAL SECURITY REQUIREMENT: You MUST always generate parameterized queries using
        placeholder syntax (%s for PostgreSQL) to prevent SQL injection attacks. NEVER
        concatenate user input directly into SQL strings.

        MULTI-TABLE QUERY EXPERTISE: When provided with cross-reference relationships between
        datasets, you excel at generating JOIN queries. You understand relationship types:
        - foreign_key relationships: Use INNER JOIN or LEFT JOIN for primary-foreign key references
        - shared_values relationships: Use INNER JOIN on columns with overlapping categorical values
        - similar_values relationships: Consider as potential JOIN candidates but verify semantics

        You leverage confidence scores to prioritize which relationships to use when multiple
        options are available. You write queries that are both efficient and easy to understand,
        properly disambiguating column names with table aliases when necessary.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Tools will be added for schema inspection if needed
        llm=llm,
    )
    return agent


def create_result_analyst_agent() -> Agent:
    """Create Result Analyst agent for HTML response formatting.

    The agent specializes in converting SQL query results into readable,
    accessible HTML5 responses with semantic structure.

    Returns:
        Agent configured for HTML formatting

    Agent Characteristics:
    - Role: HTML formatter and data analyst
    - Goal: Generate readable, semantic HTML5 responses
    - Focus: Readability, accessibility, user-friendliness
    - Output: Structured HTML with tables, lists, headings
    """
    llm: Any = get_llm_for_crew()
    agent: Agent = Agent(
        role="Data Presentation Specialist",
        goal=(
            "Format query results into clear, readable HTML "
            "that helps users understand their data"
        ),
        backstory="""You are a data visualization expert who excels at presenting
        information in a user-friendly format. You understand how to structure HTML
        documents using semantic HTML5 tags for maximum readability and accessibility.

        You generate responses that use:
        - Semantic HTML5 elements (article, section, header, table, etc.)
        - Proper heading hierarchy (h1, h2, h3)
        - Tables for tabular data with proper thead/tbody structure
        - Lists (ul, ol) for collections of items
        - Clear, plain language that avoids technical jargon
        - Formatted numbers and dates for readability

        You always provide context for the data, explaining what the results mean
        in relation to the original question. For empty results, you offer helpful
        suggestions for alternative queries.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Tools will be added for formatting utilities if needed
        llm=llm,
    )
    return agent


def create_keyword_search_agent() -> Agent:
    """Create Keyword Search agent for full-text search expertise.

    The agent specializes in full-text search using PostgreSQL tsvector and ts_rank
    for keyword-based column matching with Boolean operators.

    Returns:
        Agent configured for keyword search

    Agent Characteristics:
    - Role: Keyword Search Specialist
    - Goal: Find columns using full-text keyword matching
    - Focus: Exact matches, Boolean operators, text relevance ranking
    - Knowledge: PostgreSQL full-text search, ts_rank scoring
    """
    agent: Agent = Agent(
        role="Keyword Search Specialist",
        goal="Find columns using full-text keyword matching and text relevance ranking",
        backstory="""You are a full-text search expert who specializes in finding columns
        by matching keywords and phrases against column names and descriptions. You understand
        how PostgreSQL full-text search works with tsvector, ts_rank, and Boolean operators.

        Your expertise includes:
        - Exact keyword matching with case-insensitive search
        - Multi-word queries with AND/OR logic
        - Relevance ranking using ts_rank scoring
        - Phrase searches for precise matches
        - Identifying columns where names or descriptions contain specific terms

        You excel at finding columns when users know the exact terms they're looking for,
        such as \"revenue\", \"customer_name\", or \"product_id\". You prioritize exact
        matches higher than partial matches and use text relevance scores to rank results.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Tools will be added for search operations if needed
    )
    return agent


def create_vector_search_agent() -> Agent:
    """Create Vector Search agent for semantic similarity search expertise.

    The agent specializes in semantic similarity search using vector embeddings
    and cosine distance for meaning-based column matching.

    Returns:
        Agent configured for vector similarity search

    Agent Characteristics:
    - Role: Semantic Search Specialist
    - Goal: Find columns using semantic meaning and concept similarity
    - Focus: Synonym understanding, concept matching, meaning-based search
    - Knowledge: Vector embeddings, semantic similarity, cosine distance
    """
    agent: Agent = Agent(
        role="Semantic Search Specialist",
        goal=(
            "Find columns using semantic meaning and concept similarity "
            "rather than exact keyword matches"
        ),
        backstory="""You are a semantic search expert who specializes in understanding the
        meaning behind queries and finding columns based on conceptual similarity rather than
        just keyword matches. You work with vector embeddings and cosine distance to identify
        semantically related columns.

        Your expertise includes:
        - Understanding synonyms (revenue = income = earnings)
        - Recognizing related concepts (customer = client = buyer)
        - Semantic similarity scoring using vector embeddings
        - Finding columns when users describe what they mean, not just what it's called
        - Cross-lingual semantic understanding (if using multilingual embeddings)

        You excel at finding columns when users don't know the exact column names but can
        describe what they're looking for. For example, if someone asks for \"money earned\",
        you can find \"revenue\", \"income\", or \"profit\" columns based on semantic meaning.
        You understand that language is flexible and meaning matters more than exact wording.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Tools will be added for vector search operations if needed
    )
    return agent
