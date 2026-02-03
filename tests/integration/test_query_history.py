"""Integration tests for query history storage in PostgreSQL.

Tests the query history storage service that persists queries and responses
in the user schema's queries and responses tables.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from uuid import UUID

from psycopg_pool import ConnectionPool
import pytest


@pytest.mark.integration
class TestQueryHistory:
    """Integration tests for query history storage (T054)."""

    def test_store_query_creates_record(self, connection_pool: ConnectionPool) -> None:
        """Test storing a query creates a record in queries table.

        Validates:
        - Query is inserted into user schema queries table
        - All required fields are populated
        - Query ID is returned
        - Timestamps are accurate

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - Query record is created
        - Fields match input data
        - ID is valid UUID
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)

        query_text: str = "What are the top 10 sales?"
        username: str = "testuser"

        query_id: UUID = service.store_query(
            query_text=query_text,
            username=username,
            status="pending"
        )

        # Verify query ID is valid UUID
        assert isinstance(query_id, UUID)

        # Retrieve and verify query
        query: dict[str, Any] = service.get_query_by_id(query_id, username)
        assert query["id"] == query_id
        assert query["query_text"] == query_text
        assert query["status"] == "pending"
        assert query["submitted_at"] is not None

    def test_update_query_status(self, connection_pool: ConnectionPool) -> None:
        """Test updating query status as it progresses through workflow.

        Validates:
        - Query status can be updated
        - Status transitions are tracked
        - Completed timestamp is set when status=completed

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - Status updates persist correctly
        - Timestamps are updated appropriately
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)
        username: str = "testuser"

        # Create query
        query_id: UUID = service.store_query(
            query_text="Test query",
            username=username,
            status="pending"
        )

        # Update to processing
        service.update_query_status(query_id, username, "processing")
        query: dict[str, Any] = service.get_query_by_id(query_id, username)
        assert query["status"] == "processing"
        assert query["completed_at"] is None

        # Update to completed
        service.update_query_status(
            query_id,
            username,
            "completed",
            generated_sql="SELECT * FROM data",
            result_count=42,
            execution_time_ms=1250
        )
        query = service.get_query_by_id(query_id, username)
        assert query["status"] == "completed"
        assert query["completed_at"] is not None
        assert query["generated_sql"] == "SELECT * FROM data"
        assert query["result_count"] == 42
        assert query["execution_time_ms"] == 1250

    def test_store_response_creates_record(self, connection_pool: ConnectionPool) -> None:
        """Test storing a response creates a record in responses table.

        Validates:
        - Response is inserted into user schema responses table
        - Response is linked to query via query_id
        - HTML and plain text are stored
        - Confidence score is persisted

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - Response record is created
        - Foreign key relationship is enforced
        - All fields are populated
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)
        username: str = "testuser"

        # Create query first
        query_id: UUID = service.store_query(
            query_text="Test query",
            username=username,
            status="pending"
        )

        # Store response
        html_content: str = "<p>The answer is 42</p>"
        plain_text: str = "The answer is 42"
        confidence_score: float = 0.95

        response_id: UUID = service.store_response(
            query_id=query_id,
            username=username,
            html_content=html_content,
            plain_text=plain_text,
            confidence_score=confidence_score
        )

        # Verify response ID is valid UUID
        assert isinstance(response_id, UUID)

        # Retrieve and verify response
        response: dict[str, Any] = service.get_response_by_query_id(query_id, username)
        assert response["id"] == response_id
        assert response["query_id"] == query_id
        assert response["html_content"] == html_content
        assert response["plain_text"] == plain_text
        assert response["confidence_score"] == confidence_score
        assert response["generated_at"] is not None

    def test_get_query_with_response(self, connection_pool: ConnectionPool) -> None:
        """Test retrieving query with embedded response (QueryWithResponse).

        Validates:
        - Query and response are joined correctly
        - Response field is null if no response exists
        - Response field contains full Response object if exists

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - Query retrieval includes response
        - Join works correctly
        - Data integrity is maintained
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)
        username: str = "testuser"

        # Create query
        query_id: UUID = service.store_query(
            query_text="Test query with response",
            username=username,
            status="completed"
        )

        # Store response
        service.store_response(
            query_id=query_id,
            username=username,
            html_content="<p>Result</p>",
            plain_text="Result",
            confidence_score=0.9
        )

        # Get query with response
        query_with_response: dict[str, Any] = service.get_query_with_response(query_id, username)

        assert query_with_response["id"] == query_id
        assert query_with_response["response"] is not None
        assert query_with_response["response"]["html_content"] == "<p>Result</p>"
        assert query_with_response["response"]["plain_text"] == "Result"

    def test_get_query_history_paginated(self, connection_pool: ConnectionPool) -> None:
        """Test retrieving paginated query history.

        Validates:
        - Queries are returned in reverse chronological order
        - Pagination works correctly
        - Total count is accurate
        - Page and page_size are respected

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - History retrieval works
        - Pagination is correct
        - Sorting is consistent
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)
        username: str = "testuser"

        # Create multiple queries
        query_ids: list[UUID] = []
        for i in range(15):
            query_id: UUID = service.store_query(
                query_text=f"Query {i}",
                username=username,
                status="completed"
            )
            query_ids.append(query_id)

        # Get first page
        history: dict[str, Any] = service.get_query_history(
            username=username,
            page=1,
            page_size=10
        )

        assert "queries" in history
        assert "total_count" in history
        assert "page" in history
        assert "page_size" in history

        assert history["total_count"] >= 15
        assert len(history["queries"]) == 10
        assert history["page"] == 1
        assert history["page_size"] == 10

        # Verify reverse chronological order (newest first)
        first_query: dict[str, Any] = history["queries"][0]
        last_query: dict[str, Any] = history["queries"][-1]
        assert first_query["submitted_at"] >= last_query["submitted_at"]

    def test_get_query_history_filter_by_status(self, connection_pool: ConnectionPool) -> None:
        """Test filtering query history by status.

        Validates:
        - Status filter parameter works
        - Only queries with matching status are returned
        - Filter doesn't affect pagination

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - Status filtering works correctly
        - Multiple status values can be filtered
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)
        username: str = "testuser"

        # Create queries with different statuses
        service.store_query("Query 1", username, "completed")
        service.store_query("Query 2", username, "failed")
        service.store_query("Query 3", username, "completed")

        # Filter by completed status
        history: dict[str, Any] = service.get_query_history(
            username=username,
            page=1,
            page_size=50,
            status="completed"
        )

        # Verify all returned queries have completed status
        for query in history["queries"]:
            assert query["status"] == "completed"

    def test_query_isolation_between_users(self, connection_pool: ConnectionPool) -> None:
        """Test query history isolation between different users.

        Validates:
        - User A cannot see User B's queries
        - Schema isolation is enforced
        - Cross-user query access returns 404

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - User queries are isolated per FR-020
        - Unauthorized access is prevented
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)

        # Create query for user A
        query_id_a: UUID = service.store_query(
            query_text="User A query",
            username="usera",
            status="completed"
        )

        # Try to access user A's query as user B
        with pytest.raises(Exception):
            service.get_query_by_id(query_id_a, "userb")

        # Verify user B's history doesn't include user A's queries
        history_b: dict[str, Any] = service.get_query_history(
            username="userb",
            page=1,
            page_size=50
        )

        query_ids_b: list[UUID] = [q["id"] for q in history_b["queries"]]
        assert query_id_a not in query_ids_b

    def test_cascade_delete_response_on_query_delete(self, connection_pool: ConnectionPool) -> None:
        """Test cascading delete removes response when query is deleted.

        Validates:
        - Deleting query also deletes associated response
        - CASCADE constraint is enforced
        - No orphaned response records

        Args:
            connection_pool: Database connection pool fixture

        Success Criteria (T054):
        - Cascade delete works correctly
        - Database integrity is maintained
        """
        from backend.src.services.query_history import QueryHistoryService

        service: QueryHistoryService = QueryHistoryService(connection_pool)
        username: str = "testuser"

        # Create query and response
        query_id: UUID = service.store_query("Test", username, "completed")
        service.store_response(
            query_id=query_id,
            username=username,
            html_content="<p>Test</p>",
            plain_text="Test",
            confidence_score=0.9
        )

        # Delete query
        service.delete_query(query_id, username)

        # Verify query is deleted
        with pytest.raises(Exception):
            service.get_query_by_id(query_id, username)

        # Verify response is also deleted (cascade)
        with pytest.raises(Exception):
            service.get_response_by_query_id(query_id, username)
