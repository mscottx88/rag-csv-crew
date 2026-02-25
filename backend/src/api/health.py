"""Health check endpoint for monitoring application status.

Implements:
- Health status endpoint for readiness and liveness probes
- Database connectivity check
- Thread-safe health checks

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response, status
from psycopg import OperationalError

from backend.src.db.connection import DatabaseConnectionPool, get_global_pool

# Create router
router: APIRouter = APIRouter()


@router.get("/health", tags=["health"])
def health_check(
    response: Response,
) -> dict[str, Any]:
    """Health check endpoint for monitoring and probing.

    Returns system health status with database connectivity check.

    Returns:
        Health status response with:
        - status: "healthy" or "unhealthy"
        - database: {connected: bool}
        - timestamp: ISO 8601 timestamp

    Status Codes:
        200: All systems operational
        503: Service unavailable (database connectivity issue)

    Per openapi.yaml: /health GET operation
    Usage: Kubernetes liveness/readiness probes, monitoring systems

    Note: This is a synchronous route handler per Constitution Principle VI
    """
    timestamp: datetime = datetime.now(UTC)
    timestamp_str: str = timestamp.isoformat()

    # Check database connectivity
    db_connected: bool = check_database_connection()

    # Determine overall health status
    is_healthy: bool = db_connected
    status_str: str = "healthy" if is_healthy else "unhealthy"

    # Set HTTP status code
    if is_healthy:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Build response
    health_response: dict[str, Any] = {
        "status": status_str,
        "database": {"connected": db_connected},
        "timestamp": timestamp_str,
    }

    return health_response


def check_database_connection() -> bool:
    """Check if database connection is available.

    Returns:
        True if database is reachable, False otherwise

    Note: This function attempts to connect but does not raise
    exceptions - returns False on any connection error
    """
    try:
        # Get connection pool
        pool: DatabaseConnectionPool = get_global_pool()

        # Try to acquire connection and execute simple query
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            result: tuple[int] | None = cur.fetchone()

            if result is None or result[0] != 1:
                return False

        return True

    except (OperationalError, RuntimeError):
        # Database connection error or pool not initialized means unhealthy
        return False
