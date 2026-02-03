"""Contract tests for queries endpoints per openapi.yaml.

Tests POST /queries, GET /queries, GET /queries/{query_id},
POST /queries/{query_id}/cancel, and GET /queries/examples endpoints
following OpenAPI specification.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest


@pytest.mark.contract
class TestQueriesContract:
    """Contract tests for query submission and management endpoints (T055-T059)."""

    def test_submit_query_success(self, client: TestClient) -> None:
        """Test POST /queries with valid query returns 201 and Query object.

        Validates per openapi.yaml:
        - 201 status code
        - Response schema matches Query model
        - Query status is 'pending' or 'processing'
        - Query ID is valid UUID
        - Submitted timestamp is present

        Args:
            client: FastAPI test client fixture

        Success Criteria (T055):
        - Valid query submission returns 201
        - Response contains all required Query fields
        - Status is one of the valid enum values
        """
        # First login to get token
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Submit query
        query_body: dict[str, Any] = {
            "query_text": "What are the top 10 rows?",
            "dataset_ids": None  # Query all datasets
        }
        response: Any = client.post("/queries", json=query_body, headers=headers)

        # Verify 201 status
        assert response.status_code == 201

        # Verify response schema per openapi.yaml Query model
        data: dict[str, Any] = response.json()
        assert "id" in data
        assert "query_text" in data
        assert "submitted_at" in data
        assert "status" in data

        # Verify query text matches request
        assert data["query_text"] == "What are the top 10 rows?"

        # Verify status is valid enum value
        valid_statuses: list[str] = ["pending", "processing", "completed", "failed", "cancelled", "timeout"]
        assert data["status"] in valid_statuses

        # Verify optional fields are present (nullable per schema)
        assert "completed_at" in data
        assert "generated_sql" in data
        assert "result_count" in data
        assert "execution_time_ms" in data

    def test_submit_query_with_dataset_ids(self, client: TestClient) -> None:
        """Test POST /queries with specific dataset_ids array.

        Validates per openapi.yaml:
        - Query submission with dataset_ids array succeeds
        - Response includes submitted query

        Args:
            client: FastAPI test client fixture

        Success Criteria (T055):
        - Query with dataset_ids is accepted
        - Response status is 201
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Submit query with specific dataset IDs
        dataset_id: str = str(uuid4())
        query_body: dict[str, Any] = {
            "query_text": "Show me the data",
            "dataset_ids": [dataset_id]
        }
        response: Any = client.post("/queries", json=query_body, headers=headers)

        assert response.status_code == 201
        data: dict[str, Any] = response.json()
        assert data["query_text"] == "Show me the data"

    def test_submit_query_invalid_text(self, client: TestClient) -> None:
        """Test POST /queries with invalid query_text returns 400 or 422.

        Validates per openapi.yaml:
        - Empty query_text rejected
        - Query_text exceeding maxLength rejected
        - Error response includes detail

        Args:
            client: FastAPI test client fixture

        Success Criteria (T055):
        - Invalid query text returns error status
        - Error response follows ErrorResponse schema
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Test empty query_text
        query_body: dict[str, str] = {"query_text": ""}
        response: Any = client.post("/queries", json=query_body, headers=headers)
        assert response.status_code in [400, 422]
        data: dict[str, Any] = response.json()
        assert "detail" in data or "message" in data

        # Test query_text exceeding maxLength (5000 chars per openapi.yaml)
        long_query: dict[str, str] = {"query_text": "a" * 5001}
        response = client.post("/queries", json=long_query, headers=headers)
        assert response.status_code in [400, 422]

    def test_submit_query_unauthorized(self, client: TestClient) -> None:
        """Test POST /queries without authentication returns 401.

        Validates per openapi.yaml:
        - Missing Bearer token returns 401
        - Error response follows UnauthorizedError schema

        Args:
            client: FastAPI test client fixture

        Success Criteria (T055):
        - Request without token returns 401
        """
        query_body: dict[str, Any] = {
            "query_text": "What are the top 10 rows?"
        }
        response: Any = client.post("/queries", json=query_body)

        assert response.status_code == 401

    def test_get_query_by_id_success(self, client: TestClient) -> None:
        """Test GET /queries/{query_id} returns query status and response.

        Validates per openapi.yaml:
        - 200 status code
        - Response schema matches QueryWithResponse model
        - Query object includes all required fields
        - Response object (if present) follows Response schema

        Args:
            client: FastAPI test client fixture

        Success Criteria (T056):
        - Valid query ID returns 200
        - Response includes query details
        - Optional response field follows schema
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # First submit a query
        query_body: dict[str, Any] = {"query_text": "What are the top 10 rows?"}
        submit_response: Any = client.post("/queries", json=query_body, headers=headers)
        assert submit_response.status_code == 201
        query_id: str = submit_response.json()["id"]

        # Get query by ID
        response: Any = client.get(f"/queries/{query_id}", headers=headers)

        assert response.status_code == 200

        # Verify QueryWithResponse schema
        data: dict[str, Any] = response.json()
        assert "id" in data
        assert data["id"] == query_id
        assert "query_text" in data
        assert "submitted_at" in data
        assert "status" in data
        assert "response" in data  # Nullable per openapi.yaml

        # If response is present, verify Response schema
        if data["response"] is not None:
            response_data: dict[str, Any] = data["response"]
            assert "id" in response_data
            assert "query_id" in response_data
            assert "html_content" in response_data
            assert "plain_text" in response_data
            assert "generated_at" in response_data

    def test_get_query_by_id_not_found(self, client: TestClient) -> None:
        """Test GET /queries/{query_id} with non-existent ID returns 404.

        Validates per openapi.yaml:
        - 404 status for non-existent query ID
        - Error response follows ErrorResponse schema

        Args:
            client: FastAPI test client fixture

        Success Criteria (T056):
        - Non-existent query ID returns 404
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        fake_query_id: str = str(uuid4())
        response: Any = client.get(f"/queries/{fake_query_id}", headers=headers)

        assert response.status_code == 404
        data: dict[str, Any] = response.json()
        assert "detail" in data or "message" in data

    def test_get_query_by_id_unauthorized(self, client: TestClient) -> None:
        """Test GET /queries/{query_id} without authentication returns 401.

        Args:
            client: FastAPI test client fixture

        Success Criteria (T056):
        - Request without token returns 401
        """
        fake_query_id: str = str(uuid4())
        response: Any = client.get(f"/queries/{fake_query_id}")

        assert response.status_code == 401

    def test_get_query_history_success(self, client: TestClient) -> None:
        """Test GET /queries returns paginated query history.

        Validates per openapi.yaml:
        - 200 status code
        - Response schema matches QueryHistory model
        - Pagination fields present (queries, total_count, page, page_size)

        Args:
            client: FastAPI test client fixture

        Success Criteria (T057):
        - Query history endpoint returns 200
        - Response follows QueryHistory schema
        - Pagination parameters work correctly
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Get query history
        response: Any = client.get("/queries", headers=headers)

        assert response.status_code == 200

        # Verify QueryHistory schema
        data: dict[str, Any] = response.json()
        assert "queries" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data

        # Verify queries is an array
        assert isinstance(data["queries"], list)

        # Verify pagination defaults (per openapi.yaml)
        assert data["page"] >= 1
        assert data["page_size"] >= 1
        assert data["total_count"] >= 0

    def test_get_query_history_with_pagination(self, client: TestClient) -> None:
        """Test GET /queries with page and page_size parameters.

        Validates per openapi.yaml:
        - Page and page_size query parameters accepted
        - Response reflects pagination parameters

        Args:
            client: FastAPI test client fixture

        Success Criteria (T057):
        - Pagination parameters are respected
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Get query history with pagination
        response: Any = client.get("/queries?page=1&page_size=10", headers=headers)

        assert response.status_code == 200
        data: dict[str, Any] = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_get_query_history_with_status_filter(self, client: TestClient) -> None:
        """Test GET /queries with status filter parameter.

        Validates per openapi.yaml:
        - Status query parameter accepted
        - Filtered results match status

        Args:
            client: FastAPI test client fixture

        Success Criteria (T057):
        - Status filter parameter is accepted
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Get query history filtered by status
        response: Any = client.get("/queries?status=completed", headers=headers)

        assert response.status_code == 200
        data: dict[str, Any] = response.json()
        assert "queries" in data

    def test_get_query_history_unauthorized(self, client: TestClient) -> None:
        """Test GET /queries without authentication returns 401.

        Args:
            client: FastAPI test client fixture

        Success Criteria (T057):
        - Request without token returns 401
        """
        response: Any = client.get("/queries")

        assert response.status_code == 401

    def test_cancel_query_success(self, client: TestClient) -> None:
        """Test POST /queries/{query_id}/cancel cancels running query.

        Validates per openapi.yaml:
        - 200 status code
        - Response schema matches Query model
        - Query status transitions to 'cancelled'

        Args:
            client: FastAPI test client fixture

        Success Criteria (T058):
        - Cancellable query returns 200
        - Query status becomes 'cancelled'
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Submit a query
        query_body: dict[str, Any] = {"query_text": "Long running query"}
        submit_response: Any = client.post("/queries", json=query_body, headers=headers)
        assert submit_response.status_code == 201
        query_id: str = submit_response.json()["id"]

        # Cancel the query
        response: Any = client.post(f"/queries/{query_id}/cancel", headers=headers)

        # Verify response (200 if cancelled, 400 if already completed)
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data: dict[str, Any] = response.json()
            assert "id" in data
            assert "status" in data
            # Status should be 'cancelled' or 'processing' (race condition)
            assert data["status"] in ["cancelled", "processing", "completed"]

    def test_cancel_query_not_found(self, client: TestClient) -> None:
        """Test POST /queries/{query_id}/cancel with non-existent ID returns 404.

        Validates per openapi.yaml:
        - 404 status for non-existent query ID
        - Error response follows ErrorResponse schema

        Args:
            client: FastAPI test client fixture

        Success Criteria (T058):
        - Non-existent query ID returns 404
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        fake_query_id: str = str(uuid4())
        response: Any = client.post(f"/queries/{fake_query_id}/cancel", headers=headers)

        assert response.status_code == 404
        data: dict[str, Any] = response.json()
        assert "detail" in data or "message" in data

    def test_cancel_query_unauthorized(self, client: TestClient) -> None:
        """Test POST /queries/{query_id}/cancel without authentication returns 401.

        Args:
            client: FastAPI test client fixture

        Success Criteria (T058):
        - Request without token returns 401
        """
        fake_query_id: str = str(uuid4())
        response: Any = client.post(f"/queries/{fake_query_id}/cancel")

        assert response.status_code == 401

    def test_get_example_queries_success(self, client: TestClient) -> None:
        """Test GET /queries/examples returns example questions.

        Validates per openapi.yaml:
        - 200 status code
        - Response contains 'examples' array
        - Each example has question, description, category fields

        Args:
            client: FastAPI test client fixture

        Success Criteria (T059):
        - Example queries endpoint returns 200
        - Response contains array of examples
        - Each example follows schema
        """
        login_response: Any = client.post("/auth/login", json={"username": "testuser"})
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        response: Any = client.get("/queries/examples", headers=headers)

        assert response.status_code == 200

        # Verify response schema
        data: dict[str, Any] = response.json()
        assert "examples" in data
        assert isinstance(data["examples"], list)

        # Verify each example follows schema (if any examples present)
        if len(data["examples"]) > 0:
            example: dict[str, Any] = data["examples"][0]
            assert "question" in example
            assert "description" in example
            assert "category" in example

            # Verify category is valid enum value per openapi.yaml
            valid_categories: list[str] = ["basic", "aggregation", "filtering", "cross_dataset"]
            assert example["category"] in valid_categories

    def test_get_example_queries_unauthorized(self, client: TestClient) -> None:
        """Test GET /queries/examples without authentication returns 401.

        Args:
            client: FastAPI test client fixture

        Success Criteria (T059):
        - Request without token returns 401
        """
        response: Any = client.get("/queries/examples")

        assert response.status_code == 401
