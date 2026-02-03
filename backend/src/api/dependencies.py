"""FastAPI dependency functions for route protection and shared resources.

Implements:
- JWT authentication dependency for route protection
- Current user extraction from Bearer token
- Thread-safe operations

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError  # type: ignore[import-untyped]

from backend.src.services.auth import validate_jwt_token


def get_current_user(
    credentials: HTTPAuthorizationCredentials,
    secret_key: str,
    algorithm: str,
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
        secret_key: JWT secret key for token validation
        algorithm: JWT algorithm (e.g., "HS256")

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
