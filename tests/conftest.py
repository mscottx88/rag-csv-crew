"""Pytest configuration and shared fixtures.

Provides database connection fixtures and test container setup for integration tests.
Constitutional Requirements:
- Thread-based concurrency only
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any, Generator

import pytest
from psycopg.pool import ConnectionPool


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
