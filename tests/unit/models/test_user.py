"""Unit tests for user models (UserBase, UserCreate, User, UserLogin, AuthToken).

Tests field constraints, username format validation, token structure per data-model.md.

Constitutional Requirements:
- All variables must have explicit type annotations
- All functions must have return type annotations
- Thread-based testing only
- mypy --strict compliant
"""

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

# These imports will fail initially - TDD RED phase
from backend.src.models.user import AuthToken, User, UserBase, UserCreate, UserLogin


@pytest.mark.unit
class TestUserBase:
    """Test UserBase model validation."""

    def test_userbase_valid_username(self) -> None:
        """Test UserBase accepts valid usernames."""
        valid_usernames: list[str] = [
            "alice",
            "bob123",
            "user_name",
            "a12",
            "test_user_123",
        ]

        for username in valid_usernames:
            user: UserBase = UserBase(username=username)
            assert user.username == username

    def test_userbase_username_min_length(self) -> None:
        """Test UserBase rejects usernames shorter than 3 characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserBase(username="ab")

        errors: list[dict[str, Any]] = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_userbase_username_max_length(self) -> None:
        """Test UserBase rejects usernames longer than 50 characters."""
        long_username: str = "a" * 51
        with pytest.raises(ValidationError):
            UserBase(username=long_username)

    def test_userbase_username_format_lowercase_start(self) -> None:
        """Test UserBase requires username to start with lowercase letter."""
        invalid_usernames: list[str] = [
            "Alice",  # Starts with uppercase
            "1user",  # Starts with digit
            "_user",  # Starts with underscore
        ]

        for username in invalid_usernames:
            with pytest.raises(ValidationError):
                UserBase(username=username)

    def test_userbase_username_format_allowed_characters(self) -> None:
        """Test UserBase only allows lowercase, digits, underscores."""
        invalid_usernames: list[str] = [
            "user-name",  # Hyphen not allowed
            "user.name",  # Dot not allowed
            "user name",  # Space not allowed
            "user@test",  # Special char not allowed
        ]

        for username in invalid_usernames:
            with pytest.raises(ValidationError):
                UserBase(username=username)


@pytest.mark.unit
class TestUserCreate:
    """Test UserCreate model."""

    def test_user_create_inherits_from_userbase(self) -> None:
        """Test UserCreate inherits UserBase validation."""
        user: UserCreate = UserCreate(username="testuser")
        assert user.username == "testuser"

    def test_user_create_rejects_invalid_username(self) -> None:
        """Test UserCreate validates username format."""
        with pytest.raises(ValidationError):
            UserCreate(username="Invalid_Username")


@pytest.mark.unit
class TestUser:
    """Test complete User model with metadata."""

    def test_user_model_with_all_fields(self) -> None:
        """Test User model with all fields populated."""
        now: datetime = datetime.now(timezone.utc)

        user: User = User(
            username="alice",
            schema_name="alice_schema",
            created_at=now,
            last_login_at=now,
            is_active=True,
        )

        assert user.username == "alice"
        assert user.schema_name == "alice_schema"
        assert user.created_at == now
        assert user.last_login_at == now
        assert user.is_active is True

    def test_user_model_optional_last_login(self) -> None:
        """Test User model allows None for last_login_at."""
        now: datetime = datetime.now(timezone.utc)

        user: User = User(
            username="newuser",
            schema_name="newuser_schema",
            created_at=now,
            last_login_at=None,
            is_active=True,
        )

        assert user.last_login_at is None

    def test_user_model_default_is_active(self) -> None:
        """Test User model defaults is_active to True."""
        now: datetime = datetime.now(timezone.utc)

        user: User = User(
            username="activeuser",
            schema_name="activeuser_schema",
            created_at=now,
        )

        assert user.is_active is True

    def test_user_model_from_attributes_config(self) -> None:
        """Test User model can be created from ORM attributes."""
        # Verify model_config has from_attributes=True
        user: User = User(
            username="test",
            schema_name="test_schema",
            created_at=datetime.now(timezone.utc),
        )

        assert user.model_config.get("from_attributes") is True


@pytest.mark.unit
class TestUserLogin:
    """Test UserLogin request model."""

    def test_user_login_valid_request(self) -> None:
        """Test UserLogin with valid username."""
        login: UserLogin = UserLogin(username="alice")
        assert login.username == "alice"

    def test_user_login_min_length(self) -> None:
        """Test UserLogin requires username >= 3 characters."""
        with pytest.raises(ValidationError):
            UserLogin(username="ab")

    def test_user_login_max_length(self) -> None:
        """Test UserLogin requires username <= 50 characters."""
        long_username: str = "a" * 51
        with pytest.raises(ValidationError):
            UserLogin(username=long_username)

    def test_user_login_missing_username(self) -> None:
        """Test UserLogin requires username field."""
        with pytest.raises(ValidationError):
            UserLogin()  # type: ignore[call-arg]


@pytest.mark.unit
class TestAuthToken:
    """Test AuthToken response model."""

    def test_auth_token_valid_response(self) -> None:
        """Test AuthToken with all required fields."""
        token: AuthToken = AuthToken(
            access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
            token_type="bearer",
            username="alice",
        )

        assert token.access_token.startswith("eyJ")
        assert token.token_type == "bearer"
        assert token.username == "alice"

    def test_auth_token_default_token_type(self) -> None:
        """Test AuthToken defaults token_type to 'bearer'."""
        token: AuthToken = AuthToken(
            access_token="test_token",
            username="bob",
        )

        assert token.token_type == "bearer"

    def test_auth_token_missing_required_fields(self) -> None:
        """Test AuthToken requires access_token and username."""
        with pytest.raises(ValidationError) as exc_info:
            AuthToken()  # type: ignore[call-arg]

        errors: list[dict[str, Any]] = exc_info.value.errors()
        error_fields: set[str] = {error["loc"][0] for error in errors}

        assert "access_token" in error_fields
        assert "username" in error_fields

    def test_auth_token_empty_fields(self) -> None:
        """Test AuthToken rejects empty access_token."""
        with pytest.raises(ValidationError):
            AuthToken(
                access_token="",
                username="alice",
            )
