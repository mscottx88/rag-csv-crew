"""Unit tests for username-only authentication service.

Tests JWT token generation and validation per FR-021:
- Username-only authentication (no password)
- JWT token creation with expiration
- Token validation and username extraction

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
import pytest


@pytest.mark.unit
class TestAuthenticationService:
    """Test username-only authentication with JWT tokens."""

    def test_generate_jwt_token(self) -> None:
        """Test JWT token generation for valid username.

        Validates:
        - Token contains username claim
        - Token contains expiration claim (exp)
        - Token can be decoded with correct secret
        - Expiration set to 24 hours by default

        Per FR-021: Username-only authentication, no password required
        """
        from backend.src.services.auth import generate_jwt_token

        username: str = "alice"
        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"
        expire_minutes: int = 1440  # 24 hours

        token: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=expire_minutes,
        )

        # Verify token is not empty
        assert token
        assert len(token) > 0

        # Decode and verify claims
        payload: dict[str, Any] = jwt.decode(token, secret_key, algorithms=[algorithm])

        assert payload["sub"] == username
        assert "exp" in payload

        # Verify expiration is approximately 24 hours from now
        exp_timestamp: float = payload["exp"]
        exp_datetime: datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)
        now: datetime = datetime.now(UTC)
        time_diff: timedelta = exp_datetime - now

        # Should be close to 24 hours (within 1 minute tolerance)
        expected_seconds: float = expire_minutes * 60
        assert abs(time_diff.total_seconds() - expected_seconds) < 60

    def test_validate_jwt_token_success(self) -> None:
        """Test successful JWT token validation.

        Validates:
        - Valid token returns username
        - Token with correct signature accepted
        - Non-expired token accepted
        """
        from backend.src.services.auth import (
            generate_jwt_token,
            validate_jwt_token,
        )

        username: str = "alice"
        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"

        # Generate token
        token: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=1440,
        )

        # Validate token
        extracted_username: str = validate_jwt_token(
            token=token, secret_key=secret_key, algorithm=algorithm
        )

        assert extracted_username == username

    def test_validate_jwt_token_expired(self) -> None:
        """Test JWT token validation fails for expired token.

        Validates:
        - Expired token raises JWTError
        - Expiration enforcement works correctly
        """
        from backend.src.services.auth import (
            generate_jwt_token,
            validate_jwt_token,
        )

        username: str = "alice"
        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"

        # Generate token that expires immediately
        token: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=-1,  # Already expired
        )

        # Validation should raise JWTError for expired token
        with pytest.raises(JWTError):
            validate_jwt_token(token=token, secret_key=secret_key, algorithm=algorithm)

    def test_validate_jwt_token_invalid_signature(self) -> None:
        """Test JWT token validation fails for wrong secret key.

        Validates:
        - Token signed with different key rejected
        - Signature verification enforced
        """
        from backend.src.services.auth import (
            generate_jwt_token,
            validate_jwt_token,
        )

        username: str = "alice"
        secret_key: str = "test-secret-key"
        wrong_secret: str = "wrong-secret-key"
        algorithm: str = "HS256"

        # Generate token with one key
        token: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=1440,
        )

        # Try to validate with different key (should fail)
        with pytest.raises(JWTError):
            validate_jwt_token(token=token, secret_key=wrong_secret, algorithm=algorithm)

    def test_validate_jwt_token_malformed(self) -> None:
        """Test JWT token validation fails for malformed token.

        Validates:
        - Invalid token format rejected
        - Proper error handling for malformed tokens
        """
        from backend.src.services.auth import validate_jwt_token

        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"

        # Try to validate malformed tokens
        invalid_tokens: list[str] = [
            "not-a-jwt-token",
            "invalid.token.format",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
        ]

        for invalid_token in invalid_tokens:
            with pytest.raises((JWTError, Exception)):
                validate_jwt_token(token=invalid_token, secret_key=secret_key, algorithm=algorithm)

    def test_username_extraction_from_token(self) -> None:
        """Test extracting username from valid token.

        Validates:
        - Username stored in 'sub' claim
        - Username correctly extracted
        - Special characters in username handled
        """
        from backend.src.services.auth import (
            generate_jwt_token,
            validate_jwt_token,
        )

        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"

        # Test various valid usernames
        test_usernames: list[str] = [
            "alice",
            "bob_smith",
            "user123",
            "test_user_123",
        ]

        for username in test_usernames:
            token: str = generate_jwt_token(
                username=username,
                secret_key=secret_key,
                algorithm=algorithm,
                expire_minutes=1440,
            )

            extracted: str = validate_jwt_token(
                token=token, secret_key=secret_key, algorithm=algorithm
            )

            assert extracted == username

    def test_token_uniqueness(self) -> None:
        """Test each token generation produces unique token.

        Validates:
        - Multiple tokens for same user are different
        - Tokens include unique identifiers (e.g., 'jti' or timestamp)
        """
        from backend.src.services.auth import generate_jwt_token

        username: str = "alice"
        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"

        # Generate multiple tokens
        token1: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=1440,
        )

        token2: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=1440,
        )

        # Tokens should be different (include timestamp or jti)
        assert token1 != token2

    def test_configurable_expiration(self) -> None:
        """Test JWT expiration time is configurable.

        Validates:
        - Custom expiration times respected
        - Different expiration durations work correctly
        """
        from backend.src.services.auth import generate_jwt_token

        username: str = "alice"
        secret_key: str = "test-secret-key"
        algorithm: str = "HS256"

        # Test different expiration times
        expire_configs: list[int] = [5, 60, 1440, 10080]  # 5m, 1h, 24h, 7d

        for expire_minutes in expire_configs:
            token: str = generate_jwt_token(
                username=username,
                secret_key=secret_key,
                algorithm=algorithm,
                expire_minutes=expire_minutes,
            )

            # Decode and check expiration
            payload: dict[str, Any] = jwt.decode(token, secret_key, algorithms=[algorithm])

            exp_timestamp: float = payload["exp"]
            exp_datetime: datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)
            now: datetime = datetime.now(UTC)
            time_diff: timedelta = exp_datetime - now

            expected_seconds: float = expire_minutes * 60
            # Allow 1 minute tolerance
            assert abs(time_diff.total_seconds() - expected_seconds) < 60
