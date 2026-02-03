"""User models for authentication and user management.

Defines Pydantic models for username-only authentication system per FR-021.
No password required - demo/prototype environment per spec clarifications.

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- Thread-based operations only (no async/await)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserBase(BaseModel):
    """Base user model with username validation.

    Validates username format per FR-021 and data-model.md:
    - Must start with lowercase letter
    - Can contain lowercase letters, digits, underscores
    - Length: 3-50 characters
    - Pattern: ^[a-z][a-z0-9_]{2,49}$

    Attributes:
        username: Unique username identifier
    """

    username: str = Field(..., min_length=3, max_length=50)

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, v: str) -> str:
        """Validate username matches required format.

        Args:
            v: Username value to validate

        Returns:
            Validated username

        Raises:
            ValueError: If username doesn't match pattern
        """
        if not v:
            raise ValueError("Username cannot be empty")

        # Must start with lowercase letter
        if not v[0].islower() or not v[0].isalpha():
            raise ValueError("Username must start with a lowercase letter")

        # Can only contain lowercase letters, digits, underscores
        for char in v:
            if not (char.islower() or char.isdigit() or char == "_"):
                raise ValueError(
                    "Username can only contain lowercase letters, digits, and underscores"
                )

        return v


class UserCreate(UserBase):
    """User creation request model.

    Inherits username validation from UserBase.
    Used for new user registration via username-only authentication.
    """


class User(UserBase):
    """Complete user model with metadata.

    Extends UserBase with system-generated fields for tracking
    user lifecycle and schema management per FR-020, FR-021.

    Attributes:
        username: Unique username identifier (inherited)
        schema_name: PostgreSQL schema name for user isolation
        created_at: User registration timestamp
        last_login_at: Most recent login timestamp (nullable)
        is_active: Whether user account is active
    """

    schema_name: str
    created_at: datetime
    last_login_at: datetime | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class UserLogin(UserBase):
    """Login request for username-only authentication.

    Per FR-021 and spec clarifications: No password required.
    This is a demo/prototype environment not for production use.

    Inherits username validation from UserBase (^[a-z][a-z0-9_]{2,49}$).

    Attributes:
        username: Username to authenticate (3-50 characters, validated format)
    """


class AuthToken(BaseModel):
    """Authentication token response.

    JWT token issued after successful username-only login.
    Per FR-021a: Tokens expire after 24 hours of inactivity.

    Attributes:
        access_token: JWT token string (non-empty)
        token_type: Token type (always "bearer")
        username: Authenticated username
    """

    access_token: str = Field(..., min_length=1)
    token_type: str = "bearer"
    username: str
