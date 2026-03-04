"""FastAPI dependency functions for route protection and shared resources.

Implements:
- JWT authentication dependency for route protection
- Current user extraction from Bearer token
- Rate limiting dependency (100 requests/minute per user)
- Thread-safe operations

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import os

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from backend.src.services.auth import validate_jwt_token
from backend.src.utils.logging import get_structured_logger, log_event
from backend.src.utils.rate_limiter import get_rate_limiter

logger = get_structured_logger(__name__)

# Bearer scheme for JWT token extraction
bearer_scheme: HTTPBearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Extract and validate current user from JWT Bearer token.

    Dependency for FastAPI route protection. Use with:
    ```python
    from fastapi import Depends
    from fastapi.security import HTTPBearer

    bearer_scheme = HTTPBearer()

    @app.get("/protected")
    def protected_route(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        current_user: str = Depends(get_current_user)
    ):
        return {"user": current_user}
    ```

    Args:
        credentials: HTTPAuthorizationCredentials from HTTPBearer()

    Returns:
        Username extracted from valid token

    Raises:
        HTTPException: 401 Unauthorized if token is invalid, expired, or missing

    Per FR-021: JWT-based authentication for route protection
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token: str = credentials.credentials

    # Get JWT configuration from environment
    secret_key: str | None = os.getenv("JWT_SECRET")
    algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT configuration missing",
        )

    try:
        # Validate token and extract username
        username: str = validate_jwt_token(
            token=token,
            secret_key=secret_key,
            algorithm=algorithm,
        )

        return username

    except JWTError as e:
        # Token validation failed (expired, invalid signature, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    except Exception as e:
        # Unexpected error during validation
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def check_rate_limit(
    response: Response,
    current_user: str = Depends(get_current_user),
) -> str:
    """Check rate limit for current user and add rate limit headers.

    Dependency for FastAPI route protection with rate limiting.
    Enforces 100 requests/minute per user per T209-POLISH.

    Use with:
    ```python
    from fastapi import Depends, Response

    @app.get("/protected")
    def protected_route(
        response: Response,
        current_user: str = Depends(check_rate_limit)
    ):
        # Rate limit already checked, current_user is validated
        return {"user": current_user}
    ```

    Rate limit headers added to response:
    - X-RateLimit-Limit: Maximum requests per window (100)
    - X-RateLimit-Remaining: Remaining requests in current window
    - X-RateLimit-Reset: Unix timestamp when limit resets

    Args:
        response: FastAPI Response object for adding headers
        current_user: Current username from JWT token (dependency)

    Returns:
        Username (same as current_user parameter)

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded

    Per FR-040: Rate limiting for API security
    Per T209-POLISH: 100 requests/minute per user rate limit
    """
    limiter = get_rate_limiter()

    # Check rate limit and consume token
    allowed: bool
    remaining: int
    reset_time: float
    allowed, remaining, reset_time = limiter.check_limit(current_user)

    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(reset_time))

    if not allowed:
        # Rate limit exceeded - log and reject
        log_event(
            logger=logger,
            level="warning",
            event="rate_limit_exceeded",
            user=current_user,
            extra={
                "limit": 100,
                "reset_time": int(reset_time),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded. Too many requests.",
                "hint": f"You have exceeded the rate limit of 100 requests per minute. "
                f"Please wait until {int(reset_time)} (Unix timestamp) to retry.",
                "retry_after": int(reset_time - limiter.check_limit(current_user)[2]),
            },
            headers={
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time)),
                "Retry-After": str(int(reset_time)),
            },
        )

    # Log successful rate limit check (debug level)
    log_event(
        logger=logger,
        level="debug",
        event="rate_limit_check",
        user=current_user,
        extra={
            "remaining": remaining,
            "reset_time": int(reset_time),
        },
    )

    return current_user
