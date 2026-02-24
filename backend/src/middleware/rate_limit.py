"""Rate limiting middleware for API endpoints.

Implements per-user rate limiting to prevent abuse (100 requests/minute per user).

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from collections import defaultdict
import time

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware tracking requests per user."""

    def __init__(self, app: ASGIApp, requests_per_minute: int = 100) -> None:
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests allowed per minute per user
        """
        super().__init__(app)
        self.requests_per_minute: int = requests_per_minute
        self.request_counts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request with rate limiting check.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response from next middleware or 429 error if rate limit exceeded
        """
        # Extract user identifier from Authorization header or IP address
        user_id: str = self._get_user_id(request)

        # Clean old timestamps (older than 1 minute)
        current_time: float = time.time()
        cutoff_time: float = current_time - 60.0  # 60 seconds = 1 minute

        # Filter out requests older than 1 minute
        self.request_counts[user_id] = [
            ts for ts in self.request_counts[user_id] if ts > cutoff_time
        ]

        # Check if user has exceeded rate limit
        if len(self.request_counts[user_id]) >= self.requests_per_minute:
            # Rate limit exceeded
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RateLimitExceeded",
                    "status_code": 429,
                    "detail": (
                        f"Rate limit exceeded. Maximum {self.requests_per_minute} "
                        "requests per minute allowed."
                    ),
                    "retry_after": 60,  # seconds
                },
                headers={"Retry-After": "60"},
            )

        # Record this request
        self.request_counts[user_id].append(current_time)

        # Continue to next middleware
        response: Response = await call_next(request)
        return response

    def _get_user_id(self, request: Request) -> str:
        """Extract user identifier from request.

        Args:
            request: HTTP request object

        Returns:
            User identifier string (username or IP address)
        """
        # Try to extract username from Authorization header (JWT token)
        auth_header: str | None = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # For simplicity, use the token itself as identifier
            # In production, decode JWT to extract username
            token: str = auth_header[7:]  # Remove "Bearer " prefix
            return f"token:{token[:16]}"  # Use first 16 chars of token

        # Fallback to client IP address
        client_host: str | None = None
        if request.client:
            client_host = request.client.host
        return f"ip:{client_host or 'unknown'}"
