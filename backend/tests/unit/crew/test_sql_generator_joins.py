"""
Unit tests for enhanced SQL Generator agent with JOIN support - T178-TEST

Tests generation of multi-table JOINs using cross_references metadata.

Requirements:
- Generate INNER JOIN, LEFT JOIN based on relationship type
- Use proper JOIN conditions from cross_references
- Handle multiple JOINs in single query
- Maintain SQL injection prevention
"""

# pylint: disable=redefined-outer-name,broad-exception-caught,docstring-first-line-empty
from crewai import Agent
import pytest
from src.crew.agents import create_sql_generator_agent


@pytest.fixture
def sql_agent() -> Agent:
    """Create SQL Generator agent with JOIN capabilities."""
    # RED: Agent enhancement doesn't exist yet
    return create_sql_generator_agent()


class TestSQLGeneratorJoins:
    """Unit tests for SQL Generator agent with multi-table support."""

    def test_generate_inner_join_for_foreign_key(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should generate INNER JOIN for foreign_key relationships."""
        # RED: Implementation needed

        # Expected SQL with INNER JOIN:
        # SELECT c.customer_name, SUM(o.total) as order_total
        # FROM orders o
        # INNER JOIN customers c ON o.customer_id = c.customer_id
        # GROUP BY c.customer_name
        # ORDER BY order_total DESC

    def test_generate_left_join_for_optional_relationship(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should generate LEFT JOIN for optional relationships."""
        # RED: Implementation needed

        # Expected SQL with LEFT JOIN:
        # SELECT p.product_name, c.category_name
        # FROM products p
        # LEFT JOIN categories c ON p.category_id = c.category_id

    def test_generate_multiple_joins(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should chain multiple JOINs in single query."""
        # RED: Implementation needed

        # Expected: Multiple JOINs in proper order
        # FROM orders o
        # INNER JOIN customers c ON o.customer_id = c.customer_id
        # INNER JOIN products p ON o.product_id = p.product_id

    def test_select_relevant_columns_from_joined_tables(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should select appropriate columns from all joined tables."""
        # RED: Implementation needed
        # Query mentions "customer name" and "order total"
        # Expected: SELECT includes c.customer_name and o.total

    def test_handle_ambiguous_column_names(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should use table aliases to disambiguate column names."""
        # RED: Implementation needed
        # Both tables have 'id' and 'name' columns
        # Expected: Use aliases like c.id, c.name, o.id, o.name

    def test_prevent_sql_injection_in_joins(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should use parameterized queries even with JOINs."""
        # RED: Implementation needed
        # Expected: Proper parameterization, no SQL injection

    def test_optimize_join_order(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should order JOINs for query performance."""
        # RED: Implementation needed
        # Join smaller tables first, filter early
        # Expected: Efficient JOIN ordering based on estimated row counts

    def test_fallback_to_single_table_when_no_joins_needed(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should generate single-table query when no cross-references."""
        # RED: Implementation needed

        # Expected: Simple SELECT without JOINs
        # SELECT * FROM customers

    def test_agent_backstory_includes_join_guidance(
        self,
        sql_agent: Agent,
    ) -> None:
        """Should have backstory explaining JOIN capabilities."""
        # RED: Implementation needed
        # Agent backstory should mention:
        # - Use of cross_references metadata
        # - When to use INNER vs LEFT JOIN
        # - Multi-table query construction
        assert "JOIN" in sql_agent.backstory or "join" in sql_agent.backstory
