"""Authentication endpoints for username-only authentication.

Implements POST /auth/login and GET /auth/me per openapi.yaml.
Follows FR-021: Username-only authentication (no password).

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- All route handlers use def (NOT async def)
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError  # type: ignore[import-untyped]
from psycopg import Connection
from pydantic import ValidationError

from backend.src.api.dependencies import get_current_user
from backend.src.db.connection import get_global_pool
from backend.src.models.user import AuthToken, User, UserLogin
from backend.src.services.auth import generate_jwt_token
from backend.src.services.schema_manager import (
    ensure_user_schema_exists,
    update_last_login,
)
from backend.src.utils.logging import get_structured_logger, log_event

# Initialize router and logger
router: APIRouter = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_structured_logger(__name__)

# Security scheme for Bearer token
bearer_scheme: HTTPBearer = HTTPBearer()


def get_jwt_config() -> tuple[str, str, int]:
    """Get JWT configuration from environment variables.

    Returns:
        Tuple of (secret_key, algorithm, expire_minutes)

    Raises:
        RuntimeError: If JWT_SECRET environment variable not set
    """
    secret_key: str | None = os.getenv("JWT_SECRET")
    if not secret_key:
        raise RuntimeError("JWT_SECRET environment variable not set. Required for authentication.")

    algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    expire_minutes_str: str = os.getenv("JWT_EXPIRE_MINUTES", "1440")  # 24 hours

    try:
        expire_minutes: int = int(expire_minutes_str)
    except ValueError as e:
        raise RuntimeError(
            f"Invalid JWT_EXPIRE_MINUTES value: {expire_minutes_str}. Must be an integer."
        ) from e

    return secret_key, algorithm, expire_minutes


@router.post("/login", response_model=AuthToken, status_code=status.HTTP_200_OK)
def login(login_request: UserLogin) -> AuthToken:
    """User login endpoint (username-only, no password).

    Creates user schema on first login. Returns JWT token for authenticated sessions.

    Args:
        login_request: UserLogin with username field

    Returns:
        AuthToken with access_token, token_type, and username

    Raises:
        HTTPException 400: If username format is invalid
        HTTPException 500: If schema creation or token generation fails

    Per openapi.yaml POST /auth/login:
    - Request: {"username": "alice"}
    - Response 200: {"access_token": "...", "token_type": "bearer", "username": "alice"}
    - Response 400: Invalid username format
    - Response 500: Server error

    Per FR-021: Username-only authentication with automatic schema creation
    """
    username: str = login_request.username

    # Log login attempt
    log_event(
        logger=logger,
        level="info",
        event="login_attempt",
        user=username,
        extra={},
    )

    # Get database connection pool
    try:
        pool = get_global_pool()
    except RuntimeError as e:
        log_event(
            logger=logger,
            level="error",
            event="login_failed",
            user=username,
            extra={"error": "Database pool not initialized"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection unavailable",
        ) from e

    # Ensure user schema exists (idempotent, creates on first login)
    try:
        with pool.connection() as conn:
            conn: Connection[tuple[str, ...]]
            ensure_user_schema_exists(conn, username)
            update_last_login(conn, username)
    except ValueError as e:
        # Username validation error from schema_manager
        log_event(
            logger=logger,
            level="warning",
            event="login_failed",
            user=username,
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        # Database or schema creation error
        log_event(
            logger=logger,
            level="error",
            event="login_failed",
            user=username,
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema creation failed: {e!s}",
        ) from e

    # Generate JWT token
    try:
        secret_key: str
        algorithm: str
        expire_minutes: int
        secret_key, algorithm, expire_minutes = get_jwt_config()

        token: str = generate_jwt_token(
            username=username,
            secret_key=secret_key,
            algorithm=algorithm,
            expire_minutes=expire_minutes,
        )
    except (ValueError, JWTError, RuntimeError) as e:
        log_event(
            logger=logger,
            level="error",
            event="token_generation_failed",
            user=username,
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        ) from e

    # Log successful login
    log_event(
        logger=logger,
        level="info",
        event="login_success",
        user=username,
        extra={},
    )

    # Return AuthToken response per openapi.yaml
    return AuthToken(
        access_token=token,
        token_type="bearer",
        username=username,
    )


@router.get("/me", response_model=User, status_code=status.HTTP_200_OK)
def get_current_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    """Get current authenticated user information.

    Requires valid JWT bearer token in Authorization header.

    Args:
        credentials: HTTPAuthorizationCredentials from bearer_scheme

    Returns:
        User model with username, schema_name, created_at, last_login_at, is_active

    Raises:
        HTTPException 401: If token is missing, invalid, or expired
        HTTPException 404: If user not found in database
        HTTPException 500: If database query fails

    Per openapi.yaml GET /auth/me:
    - Request: Authorization: Bearer <token>
    - Response 200: {"username": "alice", "schema_name": "alice_schema", ...}
    - Response 401: Unauthorized (token invalid/expired)

    Per FR-021: Token-based user profile retrieval
    """
    # Extract and validate username from token
    try:
        secret_key: str
        algorithm: str
        secret_key, algorithm, _ = get_jwt_config()

        username: str = get_current_user(
            credentials=credentials,
            secret_key=secret_key,
            algorithm=algorithm,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (401 Unauthorized)
        raise
    except Exception as e:
        log_event(
            logger=logger,
            level="error",
            event="get_user_failed",
            user=None,
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Query user from database
    try:
        pool = get_global_pool()
    except RuntimeError as e:
        log_event(
            logger=logger,
            level="error",
            event="get_user_failed",
            user=username,
            extra={"error": "Database pool not initialized"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection unavailable",
        ) from e

    try:
        with pool.connection() as conn:
            conn: Connection[tuple[str, ...]]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT username, schema_name, created_at, last_login_at, is_active
                    FROM public.users
                    WHERE username = %s
                    """,
                    (username,),
                )
                row: tuple[str, ...] | None = cur.fetchone()

                if row is None:
                    log_event(
                        logger=logger,
                        level="warning",
                        event="user_not_found",
                        user=username,
                        extra={},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User '{username}' not found",
                    )

                # Convert row to User model
                user_data: dict[str, Any] = {
                    "username": row[0],
                    "schema_name": row[1],
                    "created_at": row[2],
                    "last_login_at": row[3],
                    "is_active": row[4],
                }

                user: User = User(**user_data)

                log_event(
                    logger=logger,
                    level="info",
                    event="get_user_success",
                    user=username,
                    extra={},
                )

                return user

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValidationError as e:
        # Pydantic validation error
        log_event(
            logger=logger,
            level="error",
            event="user_validation_failed",
            user=username,
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User data validation failed",
        ) from e
    except Exception as e:
        # Database query error
        log_event(
            logger=logger,
            level="error",
            event="get_user_failed",
            user=username,
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information",
        ) from e
