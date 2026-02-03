"""CrewAI agent definitions for RAG query processing.

Defines SQL Generator and Result Analyst agents for converting natural language
queries to SQL and formatting results as HTML.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""


from crewai import Agent


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
    agent: Agent = Agent(
        role="Database Query Specialist",
        goal="Convert natural language questions into accurate, secure SQL queries that retrieve the requested data",
        backstory="""You are an expert database analyst who specializes in understanding
        user questions and translating them into precise SQL queries. You have deep knowledge
        of SQL syntax, query optimization, and database security best practices.

        CRITICAL SECURITY REQUIREMENT: You MUST always generate parameterized queries using
        placeholder syntax (%s for PostgreSQL) to prevent SQL injection attacks. NEVER
        concatenate user input directly into SQL strings.

        You understand data relationships, can identify appropriate JOIN conditions, and
        write queries that are both efficient and easy to understand.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Tools will be added for schema inspection if needed
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
    agent: Agent = Agent(
        role="Data Presentation Specialist",
        goal="Format query results into clear, readable HTML that helps users understand their data",
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
    )
    return agent
