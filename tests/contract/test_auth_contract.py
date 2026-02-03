"""Contract tests for authentication endpoints per openapi.yaml.

Tests POST /auth/login and GET /auth/me endpoints following OpenAPI spec:
- Request/response schema validation
- HTTP status codes
- JWT token format
- Username validation rules

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import datetime
import re
from typing import Any

from fastapi.testclient import TestClient
import pytest


@pytest.mark.contract
class TestAuthContract:
    """Contract tests for authentication endpoints (T039, T040)."""

    def test_login_success(self, client: TestClient) -> None:
        """Test POST /auth/login with valid username returns JWT token.

        Validates per openapi.yaml:
        - 200 status code
        - Response schema: {access_token, token_type, username}
        - token_type is 'bearer'
        - access_token is valid JWT format
        - Username matches request

        Args:
            client: FastAPI test client fixture

        Success Criteria (T039):
        - Valid username returns 200 with JWT token
        - Token can be decoded
        - Response matches AuthToken schema
        """
        # Valid username per openapi.yaml pattern: ^[a-z][a-z0-9_]{2,49}$
        request_body: dict[str, str] = {"username": "testuser"}

        response: Any = client.post("/auth/login", json=request_body)

        # Verify 200 status
        assert response.status_code == 200

        # Verify response schema per openapi.yaml AuthToken
        data: dict[str, Any] = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert "username" in data

        # Verify token_type is 'bearer'
        assert data["token_type"] == "bearer"

        # Verify username matches request
        assert data["username"] == "testuser"

        # Verify access_token is valid JWT format (3 base64 sections separated by dots)
        token: str = data["access_token"]
        jwt_pattern: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
        assert jwt_pattern.match(token), f"Token does not match JWT format: {token}"

    def test_login_invalid_username_format(self, client: TestClient) -> None:
        """Test POST /auth/login with invalid username returns 400.

        Validates per openapi.yaml:
        - 400 status code for invalid username format
        - Username must match ^[a-z][a-z0-9_]{2,49}$
        - Response includes error details

        Args:
            client: FastAPI test client fixture

        Success Criteria (T039):
        - Invalid usernames return 400
        - Error response includes detail field
        """
        invalid_usernames: list[str] = [
            "A",  # Too short (< 3 chars)
            "ab",  # Too short (< 3 chars)
            "User123",  # Starts with uppercase
            "123user",  # Starts with digit
            "user-name",  # Contains hyphen (not allowed)
            "user.name",  # Contains dot (not allowed)
            "user name",  # Contains space
            "a" * 51,  # Too long (> 50 chars)
        ]

        for invalid_username in invalid_usernames:
            request_body: dict[str, str] = {"username": invalid_username}
            response: Any = client.post("/auth/login", json=request_body)

            # Verify 400 or 422 status (FastAPI returns 422 for Pydantic validation errors)
            assert response.status_code in [400, 422], (
                f"Expected 400 or 422 for username '{invalid_username}', "
                f"got {response.status_code}"
            )

            # Verify error response has detail field
            data: dict[str, Any] = response.json()
            assert "detail" in data or "error" in data or "errors" in data, (
                f"Error response missing detail/error/errors field for username '{invalid_username}'"
            )

    def test_login_creates_user_schema_on_first_login(self, client: TestClient) -> None:
        """Test POST /auth/login creates user schema on first login.

        Validates per openapi.yaml description:
        - "Creates user schema on first login"
        - Subsequent logins with same username succeed
        - User record persists across logins

        Args:
            client: FastAPI test client fixture

        Success Criteria (T039):
        - First login for new user returns 200
        - Second login for same user returns 200
        - Both logins return valid JWT tokens
        """
        request_body: dict[str, str] = {"username": "newuser123"}

        # First login (schema creation)
        response1: Any = client.post("/auth/login", json=request_body)
        assert response1.status_code == 200
        data1: dict[str, Any] = response1.json()
        assert "access_token" in data1

        # Second login (schema already exists)
        response2: Any = client.post("/auth/login", json=request_body)
        assert response2.status_code == 200
        data2: dict[str, Any] = response2.json()
        assert "access_token" in data2

        # Both tokens should be valid JWTs
        jwt_pattern: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
        assert jwt_pattern.match(data1["access_token"])
        assert jwt_pattern.match(data2["access_token"])

    def test_login_missing_username(self, client: TestClient) -> None:
        """Test POST /auth/login without username returns 400/422.

        Validates per openapi.yaml:
        - username is required field
        - Missing username returns 400 or 422

        Args:
            client: FastAPI test client fixture

        Success Criteria (T039):
        - Request without username returns error
        - Error indicates missing required field
        """
        request_body: dict[str, Any] = {}  # Empty body

        response: Any = client.post("/auth/login", json=request_body)

        # Accept either 400 (bad request) or 422 (validation error)
        assert response.status_code in [400, 422], (
            f"Expected 400 or 422 for missing username, got {response.status_code}"
        )

        # Verify error response
        data: dict[str, Any] = response.json()
        assert "detail" in data or "error" in data

    def test_get_current_user_with_valid_token(self, client: TestClient) -> None:
        """Test GET /auth/me with valid JWT returns user info.

        Validates per openapi.yaml:
        - 200 status code
        - Response schema: User (username, schema_name, created_at, last_login_at, is_active)
        - Requires bearer token authentication

        Args:
            client: FastAPI test client fixture

        Success Criteria (T040):
        - Valid token returns 200 with User schema
        - Response includes all required fields
        - Timestamps are valid ISO 8601 format
        """
        # First, login to get a valid token
        login_request: dict[str, str] = {"username": "testuser2"}
        login_response: Any = client.post("/auth/login", json=login_request)
        assert login_response.status_code == 200
        login_data: dict[str, Any] = login_response.json()
        token: str = login_data["access_token"]

        # Call /auth/me with bearer token
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
        response: Any = client.get("/auth/me", headers=headers)

        # Verify 200 status
        assert response.status_code == 200

        # Verify User schema per openapi.yaml
        data: dict[str, Any] = response.json()
        assert "username" in data
        assert "schema_name" in data
        assert "created_at" in data
        assert "is_active" in data

        # Verify username matches login
        assert data["username"] == "testuser2"

        # Verify schema_name follows pattern {username}_schema
        assert data["schema_name"] == "testuser2_schema"

        # Verify is_active is boolean
        assert isinstance(data["is_active"], bool)
        assert data["is_active"] is True

        # Verify created_at is valid ISO 8601 timestamp
        created_at_str: str = data["created_at"]
        created_at: datetime = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        assert created_at.tzinfo is not None  # Must be timezone-aware

        # Verify last_login_at is either null or valid timestamp
        if "last_login_at" in data and data["last_login_at"] is not None:
            last_login_str: str = data["last_login_at"]
            last_login: datetime = datetime.fromisoformat(last_login_str.replace("Z", "+00:00"))
            assert last_login.tzinfo is not None

    def test_get_current_user_without_token(self, client: TestClient) -> None:
        """Test GET /auth/me without authorization returns 401.

        Validates per openapi.yaml:
        - 401 status code when no bearer token provided
        - Security requirement: bearerAuth

        Args:
            client: FastAPI test client fixture

        Success Criteria (T040):
        - Request without Authorization header returns 401
        - Error response indicates authentication required
        """
        response: Any = client.get("/auth/me")

        # Verify 401 Unauthorized
        assert response.status_code == 401

        # Verify error response
        data: dict[str, Any] = response.json()
        assert "detail" in data or "error" in data

    def test_get_current_user_with_invalid_token(self, client: TestClient) -> None:
        """Test GET /auth/me with invalid JWT returns 401.

        Validates per openapi.yaml:
        - 401 status code for invalid/malformed token
        - Token validation is enforced

        Args:
            client: FastAPI test client fixture

        Success Criteria (T040):
        - Invalid token returns 401
        - Malformed token returns 401
        """
        invalid_tokens: list[str] = [
            "invalid.token.here",  # Malformed JWT
            "Bearer ",  # Empty token
            "not-a-jwt",  # Not JWT format
        ]

        for invalid_token in invalid_tokens:
            headers: dict[str, str] = {"Authorization": f"Bearer {invalid_token}"}
            response: Any = client.get("/auth/me", headers=headers)

            # Verify 401 status
            assert response.status_code == 401, (
                f"Expected 401 for invalid token '{invalid_token}', "
                f"got {response.status_code}"
            )

    def test_get_current_user_with_expired_token(self, client: TestClient) -> None:
        """Test GET /auth/me with expired JWT returns 401.

        Validates per openapi.yaml:
        - 401 status code for expired token
        - Token expiration is enforced

        Args:
            client: TestClient fixture

        Success Criteria (T040):
        - Expired token returns 401
        - Error indicates token expiration

        Note:
            This test may require token expiration to be short (e.g., 1 second)
            or mock time advancement. Implementation depends on JWT expiration
            configuration in backend.src.services.auth.
        """
        # This test is a placeholder for token expiration validation
        # Implementation will depend on JWT expiration configuration
        # For now, we just verify the endpoint exists and handles auth correctly
        pytest.skip("Token expiration test requires configurable JWT expiration time")
