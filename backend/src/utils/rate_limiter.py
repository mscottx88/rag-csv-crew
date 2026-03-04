"""Thread-safe rate limiting implementation using token bucket algorithm.

Implements:
- Token bucket rate limiter (100 requests/minute per user)
- Thread-safe operations with threading.Lock
- Automatic token refill based on elapsed time
- Rate limit status with remaining tokens and reset time

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations

Per FR-040: Rate limiting for API security
Per T209-POLISH: 100 requests/minute per user rate limit
"""

from dataclasses import dataclass
from threading import Lock
import time


@dataclass
class TokenBucket:
    """Token bucket for rate limiting a single user.

    Attributes:
        tokens: Current number of available tokens (float for smooth refill)
        capacity: Maximum token capacity (requests per window)
        refill_rate: Tokens added per second
        last_refill: Timestamp of last token refill (seconds since epoch)
        lock: Thread lock for atomic operations
    """

    tokens: float
    capacity: int
    refill_rate: float
    last_refill: float
    lock: Lock


class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm.

    Per T209-POLISH: 100 requests/minute per user
    Algorithm: Token bucket with smooth refill
    - Each user gets a bucket with `capacity` tokens (default: 100)
    - Tokens refill at `refill_rate` per second (default: 100/60 = 1.67/s)
    - Each request consumes 1 token
    - If bucket is empty, request is rate limited (429)

    Thread-Safety:
    - Per-user locks ensure atomic token operations
    - Global lock protects bucket creation/access

    Usage:
        limiter = RateLimiter(capacity=100, window_seconds=60)
        allowed, remaining, reset_time = limiter.check_limit("alice")
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    """

    def __init__(self, capacity: int = 100, window_seconds: int = 60) -> None:
        """Initialize rate limiter with token bucket parameters.

        Args:
            capacity: Maximum requests per window (default: 100)
            window_seconds: Time window in seconds (default: 60 = 1 minute)

        Per T209-POLISH: Default 100 requests/minute per user
        """
        self.capacity: int = capacity
        self.window_seconds: int = window_seconds
        self.refill_rate: float = capacity / window_seconds  # tokens per second
        self.buckets: dict[str, TokenBucket] = {}
        self.buckets_lock: Lock = Lock()

    def _get_or_create_bucket(self, user: str) -> TokenBucket:
        """Get existing token bucket for user or create a new one.

        Thread-safe bucket creation with global lock.

        Args:
            user: Username for rate limiting

        Returns:
            TokenBucket instance for the user
        """
        with self.buckets_lock:
            if user not in self.buckets:
                # Create new bucket with full capacity
                current_time: float = time.time()
                self.buckets[user] = TokenBucket(
                    tokens=float(self.capacity),
                    capacity=self.capacity,
                    refill_rate=self.refill_rate,
                    last_refill=current_time,
                    lock=Lock(),
                )
            bucket: TokenBucket = self.buckets[user]
            return bucket

    def _refill_tokens(self, bucket: TokenBucket) -> None:
        """Refill tokens based on elapsed time since last refill.

        Tokens are added proportionally to elapsed time:
        - tokens_to_add = elapsed_seconds * refill_rate
        - Capped at bucket capacity

        Args:
            bucket: Token bucket to refill (modified in-place)

        Note: Must be called while holding bucket.lock
        """
        current_time: float = time.time()
        elapsed_seconds: float = current_time - bucket.last_refill

        # Calculate tokens to add (proportional to elapsed time)
        tokens_to_add: float = elapsed_seconds * bucket.refill_rate

        # Refill tokens (capped at capacity)
        bucket.tokens = min(bucket.tokens + tokens_to_add, float(bucket.capacity))
        bucket.last_refill = current_time

    def check_limit(self, user: str, cost: int = 1) -> tuple[bool, int, float]:
        """Check if user is within rate limit and consume tokens if allowed.

        Thread-safe token consumption with automatic refill.

        Args:
            user: Username to check rate limit for
            cost: Number of tokens to consume (default: 1 request = 1 token)

        Returns:
            Tuple of (allowed, remaining_tokens, reset_time):
            - allowed: True if request is allowed, False if rate limited
            - remaining_tokens: Number of tokens remaining after this request
            - reset_time: Unix timestamp when bucket will be full again

        Per T209-POLISH: Rate limit check for FastAPI dependency
        """
        bucket: TokenBucket = self._get_or_create_bucket(user)

        with bucket.lock:
            # Refill tokens based on elapsed time
            self._refill_tokens(bucket)

            # Initialize return values
            allowed: bool
            remaining: int

            # Check if enough tokens available
            if bucket.tokens >= cost:
                # Consume tokens and allow request
                bucket.tokens -= cost
                remaining = int(bucket.tokens)
                allowed = True
            else:
                # Rate limit exceeded
                remaining = 0
                allowed = False

            # Calculate reset time (when bucket will be full)
            tokens_needed: float = float(bucket.capacity) - bucket.tokens
            seconds_until_full: float = tokens_needed / bucket.refill_rate
            reset_time: float = time.time() + seconds_until_full

            return allowed, remaining, reset_time

    def get_limit_info(self, user: str) -> tuple[int, int, float]:
        """Get current rate limit status for user without consuming tokens.

        Args:
            user: Username to check status for

        Returns:
            Tuple of (limit, remaining, reset_time):
            - limit: Maximum requests per window (capacity)
            - remaining: Current available tokens
            - reset_time: Unix timestamp when bucket will be full

        Usage: For adding X-RateLimit-* headers to responses
        """
        bucket: TokenBucket = self._get_or_create_bucket(user)

        with bucket.lock:
            # Refill tokens to get current status
            self._refill_tokens(bucket)

            remaining: int = int(bucket.tokens)
            tokens_needed: float = float(bucket.capacity) - bucket.tokens
            seconds_until_full: float = tokens_needed / bucket.refill_rate
            reset_time: float = time.time() + seconds_until_full

            return self.capacity, remaining, reset_time

    def reset_user(self, user: str) -> None:
        """Reset rate limit for a specific user (admin/testing use).

        Args:
            user: Username to reset rate limit for

        Note: Thread-safe bucket reset
        """
        with self.buckets_lock:
            if user in self.buckets:
                del self.buckets[user]

    def reset_all(self) -> None:
        """Reset rate limits for all users (admin/testing use).

        Note: Thread-safe global reset
        """
        with self.buckets_lock:
            self.buckets.clear()


# Global rate limiter instance (100 requests/minute per user)
# Per T209-POLISH: Shared across all FastAPI workers (single-process deployment)
_global_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance.

    Returns:
        Global RateLimiter instance (100 requests/minute)

    Per T209-POLISH: Global rate limiter for FastAPI dependency injection
    """
    # pylint: disable=global-statement  # JUSTIFICATION: Singleton limiter pattern requires module-level global
    global _global_rate_limiter  # noqa: PLW0603
    # pylint: enable=global-statement

    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(capacity=100, window_seconds=60)

    return _global_rate_limiter
