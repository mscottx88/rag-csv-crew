"""Username-only authentication service with JWT token generation.

Implements FR-021: Username-only authentication (no password required)
- JWT token generation with configurable expiration
- Token validation and username extraction
- Thread-safe operations (no async/await)

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime, timedelta
import uuid

from jose import JWTError, jwt


def generate_jwt_token(
    username: str,
    secret_key: str,
    algorithm: str,
    expire_minutes: int,
) -> str:
    """Generate JWT token for username-only authentication.

    Args:
        username: User's username (lowercase, validated by caller)
        secret_key: Secret key for signing JWT
        algorithm: JWT signing algorithm (e.g., "HS256")
        expire_minutes: Token expiration time in minutes

    Returns:
        Encoded JWT token string

    Raises:
        ValueError: If username is empty or invalid
        JWTError: If token generation fails

    Per FR-021: Username-only authentication, no password required
    Token includes:
    - sub: username (subject claim)
    - exp: expiration timestamp
    - iat: issued at timestamp (for uniqueness)
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    # Calculate expiration time
    now: datetime = datetime.now(UTC)
    expire_delta: timedelta = timedelta(minutes=expire_minutes)
    expire_time: datetime = now + expire_delta

    # Create JWT payload with unique identifier
    payload: dict[str, datetime | str] = {
        "sub": username,  # Subject: username
        "exp": expire_time,  # Expiration time
        "iat": now,  # Issued at timestamp
        "jti": str(uuid.uuid4()),  # JWT ID (ensures token uniqueness)
    }

    # Encode token
    token: str = jwt.encode(payload, secret_key, algorithm=algorithm)

    return token


def validate_jwt_token(
    token: str,
    secret_key: str,
    algorithm: str,
) -> str:
    """Validate JWT token and extract username.

    Args:
        token: Encoded JWT token string
        secret_key: Secret key for verifying JWT signature
        algorithm: JWT signing algorithm (e.g., "HS256")

    Returns:
        Username extracted from token's 'sub' claim

    Raises:
        JWTError: If token is invalid, expired, or signature doesn't match
        ValueError: If token doesn't contain username

    Per FR-021: Token validation for route protection
    Validates:
    - Token signature matches secret_key
    - Token is not expired
    - Token contains 'sub' claim with username
    """
    if not token or not token.strip():
        raise JWTError("Token cannot be empty")

    try:
        # Decode and validate token
        payload: dict[str, str] = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
        )

        # Extract username from 'sub' claim
        username: str | None = payload.get("sub")

        if not username:
            raise ValueError("Token does not contain username (sub claim)")

        return username

    except JWTError as e:
        # Re-raise JWT-specific errors (expired, invalid signature, etc.)
        raise e
    except Exception as e:
        # Wrap unexpected errors as JWTError for consistent error handling
        raise JWTError(f"Token validation failed: {e!s}") from e
