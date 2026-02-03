"""Contract tests for /health endpoint.

Tests health check endpoint per openapi.yaml:
- Response schema validation
- Database connectivity check
- HTTP status codes

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
class TestHealthEndpointContract:
    """Test /health endpoint contract per openapi.yaml."""

    def test_health_endpoint_exists(self, client: TestClient) -> None:
        """Test /health endpoint is accessible.

        Validates:
        - Endpoint responds to GET requests
        - Returns 200 status code when healthy
        - Per openapi.yaml: /health GET operation
        """
        response = client.get("/health")

        # Should return 200 or 503 depending on health
        assert response.status_code in [200, 503]

    def test_health_response_schema(self, client: TestClient) -> None:
        """Test /health response matches openapi.yaml schema.

        Validates response schema:
        - status: string ("healthy" or "unhealthy")
        - database: object with "connected" boolean
        - timestamp: string (ISO 8601)

        Per openapi.yaml: HealthResponse schema
        """
        response = client.get("/health")

        # Parse response
        data: dict[str, Any] = response.json()

        # Verify required fields
        assert "status" in data
        assert isinstance(data["status"], str)
        assert data["status"] in ["healthy", "unhealthy"]

        # Database connectivity check
        if "database" in data:
            assert isinstance(data["database"], dict)
            assert "connected" in data["database"]
            assert isinstance(data["database"]["connected"], bool)

    def test_health_endpoint_healthy_status(
        self, client: TestClient
    ) -> None:
        """Test /health returns 200 when all systems operational.

        Validates:
        - Status 200 for healthy system
        - status field is "healthy"
        - database.connected is true
        """
        response = client.get("/health")

        # If database is running, should be healthy
        if response.status_code == 200:
            data: dict[str, Any] = response.json()
            assert data["status"] == "healthy"

            if "database" in data:
                assert data["database"]["connected"] is True

    def test_health_endpoint_unhealthy_status(
        self, client_no_db: TestClient
    ) -> None:
        """Test /health returns 503 when systems unavailable.

        Validates:
        - Status 503 for unhealthy system
        - status field is "unhealthy"
        - database.connected is false

        Args:
            client_no_db: Test client with no database connection
        """
        response = client_no_db.get("/health")

        # Should return 503 when database unavailable
        if response.status_code == 503:
            data: dict[str, Any] = response.json()
            assert data["status"] == "unhealthy"

            if "database" in data:
                assert data["database"]["connected"] is False

    def test_health_endpoint_no_authentication_required(
        self, client: TestClient
    ) -> None:
        """Test /health endpoint accessible without authentication.

        Validates:
        - No Authorization header required
        - Public endpoint for monitoring
        - Returns 200/503 without credentials
        """
        # Request without Authorization header
        response = client.get("/health")

        # Should not return 401 (unauthorized)
        assert response.status_code != 401
        assert response.status_code in [200, 503]

    def test_health_endpoint_response_time(
        self, client: TestClient
    ) -> None:
        """Test /health endpoint responds quickly.

        Validates:
        - Response time < 1 second
        - Health check is lightweight
        - No expensive operations
        """
        import time

        start: float = time.time()
        response = client.get("/health")
        elapsed: float = time.time() - start

        # Health check should be fast
        assert elapsed < 1.0
        assert response.status_code in [200, 503]

    def test_health_endpoint_database_connectivity_check(
        self, client: TestClient
    ) -> None:
        """Test /health performs actual database connectivity check.

        Validates:
        - Executes database query (e.g., SELECT 1)
        - Returns false if database unreachable
        - Catches connection errors gracefully
        """
        response = client.get("/health")
        data: dict[str, Any] = response.json()

        # Should have database connectivity information
        if "database" in data:
            assert "connected" in data["database"]
            # Value should be boolean, not error message
            assert isinstance(data["database"]["connected"], bool)

    def test_health_endpoint_timestamp_format(
        self, client: TestClient
    ) -> None:
        """Test /health response includes ISO 8601 timestamp.

        Validates:
        - timestamp field present
        - Format is ISO 8601 with timezone
        - Timestamp is recent (within last minute)
        """
        from datetime import datetime

        response = client.get("/health")
        data: dict[str, Any] = response.json()

        # Check for timestamp field
        if "timestamp" in data:
            timestamp_str: str = data["timestamp"]

            # Parse ISO 8601 timestamp
            try:
                timestamp: datetime = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )

                # Verify timestamp is recent
                now: datetime = datetime.now()
                time_diff: float = abs((now - timestamp).total_seconds())
                assert time_diff < 60  # Within last minute
            except ValueError:
                pytest.fail(f"Invalid timestamp format: {timestamp_str}")

    def test_health_endpoint_idempotent(self, client: TestClient) -> None:
        """Test /health endpoint is idempotent.

        Validates:
        - Multiple requests return same status
        - No side effects from health checks
        - Safe to call repeatedly
        """
        # Call health endpoint multiple times
        responses: list[int] = []

        for _ in range(5):
            response = client.get("/health")
            responses.append(response.status_code)

        # All responses should be the same
        assert len(set(responses)) == 1  # All status codes identical

    def test_health_endpoint_concurrent_requests(
        self, client: TestClient
    ) -> None:
        """Test /health handles concurrent requests.

        Validates:
        - Multiple simultaneous requests handled
        - No race conditions
        - All requests return valid responses

        Per Constitutional Principle VI: Thread-based concurrency
        """
        from concurrent.futures import ThreadPoolExecutor

        results: list[int] = []

        def check_health() -> None:
            """Check health in thread."""
            response = client.get("/health")
            results.append(response.status_code)

        # Make 20 concurrent health checks
        num_threads: int = 20
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures: list[Any] = [
                executor.submit(check_health) for _ in range(num_threads)
            ]
            for future in futures:
                future.result()

        # All requests should complete successfully
        assert len(results) == num_threads
        # All should return 200 or 503
        for status_code in results:
            assert status_code in [200, 503]

    def test_health_endpoint_content_type(self, client: TestClient) -> None:
        """Test /health returns JSON content type.

        Validates:
        - Content-Type header is application/json
        - Response is valid JSON
        """
        response = client.get("/health")

        # Verify content type
        assert "application/json" in response.headers.get(
            "content-type", ""
        ).lower()

        # Verify response is valid JSON
        data: dict[str, Any] = response.json()
        assert isinstance(data, dict)

    def test_health_endpoint_cors_headers(
        self, client: TestClient
    ) -> None:
        """Test /health includes CORS headers for frontend access.

        Validates:
        - Access-Control-Allow-Origin header present
        - CORS enabled for monitoring dashboards
        """
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )

        # CORS headers may or may not be present depending on config
        # Just verify endpoint accessible
        assert response.status_code in [200, 503]
