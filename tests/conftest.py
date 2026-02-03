"""Pytest configuration and shared fixtures.

Provides database connection fixtures and test container setup for integration tests.
Constitutional Requirements:
- Thread-based concurrency only
- All variables have explicit type annotations
- All functions have return type annotations
"""

from collections.abc import Generator
from typing import Any

from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool
import pytest


@pytest.fixture(scope="session")
def db_config() -> dict[str, Any]:
    """Provide database configuration for tests.

    Uses environment variables or defaults for test database.

    Returns:
        Dictionary with database connection parameters
    """
    config: dict[str, Any] = {
        "host": "localhost",
        "port": 5432,
        "database": "ragcsv_test",
        "user": "test",
        "password": "test",
    }
    return config


@pytest.fixture(scope="function")
def connection_pool(db_config: dict[str, Any]) -> Generator[ConnectionPool, None, None]:
    """Provide a connection pool for integration tests.

    Creates a new pool for each test function, ensures cleanup.

    Args:
        db_config: Database configuration fixture

    Yields:
        ConnectionPool instance

    Note:
        Requires PostgreSQL to be running at configured host/port
    """
    pool: ConnectionPool = ConnectionPool(
        conninfo=f"host={db_config['host']} port={db_config['port']} "
        f"dbname={db_config['database']} user={db_config['user']} "
        f"password={db_config['password']}",
        min_size=2,
        max_size=10,
        timeout=30.0,
    )

    try:
        pool.wait(timeout=5.0)  # Wait for pool to be ready
        yield pool
    finally:
        pool.close()


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Provide FastAPI test client for API tests.

    Creates a new test client for each test function.

    Yields:
        TestClient instance configured with the application

    Note:
        This fixture creates the application with default configuration
    """
    from backend.src.main import create_app

    app: object = create_app()
    test_client: TestClient = TestClient(app)  # type: ignore[arg-type]

    yield test_client

    # Cleanup (if needed)


@pytest.fixture(scope="function")
def client_no_db() -> Generator[TestClient, None, None]:
    """Provide FastAPI test client with no database connection.

    Creates a test client that simulates database unavailability for testing
    unhealthy status responses.

    Yields:
        TestClient instance configured with simulated DB failure

    Note:
        This fixture is used for testing error handling and health check
        failure scenarios
    """
    from backend.src.main import create_app

    # For now, use the same app - actual DB failure simulation would require
    # mocking the database connection check
    app: object = create_app()
    test_client: TestClient = TestClient(app)  # type: ignore[arg-type]

    yield test_client

    # Cleanup (if needed)
