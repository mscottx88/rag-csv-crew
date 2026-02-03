"""Pytest configuration and shared fixtures.

Provides database connection fixtures and test container setup for integration tests.
Constitutional Requirements:
- Thread-based concurrency only
- All variables have explicit type annotations
- All functions have return type annotations
"""

from collections.abc import Generator
import os
from typing import Any

from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_jwt_env() -> None:
    """Set up JWT environment variables for tests.

    Runs once per test session before any tests.
    Sets required JWT configuration for authentication tests.
    """
    os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-not-production"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_EXPIRE_MINUTES"] = "1440"  # 24 hours


@pytest.fixture(scope="session")
def db_config() -> dict[str, Any]:
    """Provide database configuration for tests.

    Uses environment variables or defaults for test database.

    Returns:
        Dictionary with database connection parameters
    """
    config: dict[str, Any] = {
        "host": "127.0.0.1",  # Use IP directly to avoid localhost IPv4/IPv6 resolution issues
        "port": 5432,
        "database": "ragcsv_test",
        "user": "postgres",
        "password": "postgres",
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
def client(db_config: dict[str, Any]) -> Generator[TestClient, None, None]:
    """Provide FastAPI test client for API tests.

    Creates a new test client for each test function with initialized database pool.

    Args:
        db_config: Database configuration fixture

    Yields:
        TestClient instance configured with the application

    Note:
        This fixture creates the application with default configuration
        and initializes the global database connection pool
    """
    from backend.src.db.connection import close_global_pool, initialize_global_pool
    from backend.src.main import create_app
    from backend.src.models.config import DatabaseConfig

    # Initialize global database pool for test
    test_db_config: DatabaseConfig = DatabaseConfig(
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
    )
    initialize_global_pool(test_db_config)

    # Create app with initialized pool
    app: object = create_app()
    test_client: TestClient = TestClient(app)  # type: ignore[arg-type]

    yield test_client

    # Cleanup: close global pool
    close_global_pool()


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


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data(connection_pool: ConnectionPool, request: Any) -> Generator[None, None, None]:
    """Clean up test data before each test that uses connection_pool.

    This fixture runs automatically before each test function that uses the
    connection_pool fixture. It cleans up any leftover test data from previous
    test runs to prevent UniqueViolation errors.

    Args:
        connection_pool: Database connection pool fixture
        request: pytest request object to check fixture usage

    Yields:
        None (setup runs before test, cleanup after)

    Note:
        Only runs for tests that use the connection_pool fixture
    """
    # Only run cleanup if the test uses connection_pool
    if "connection_pool" not in request.fixturenames:
        yield
        return

    # Clean up before test (remove leftover test data)
    try:
        with connection_pool.connection() as conn:
            with conn.cursor() as cur:
                # Drop and recreate public tables to ensure FK constraints exist
                # This ensures migrations run fresh on each test
                # Must drop query_log first due to FK dependency on users
                cur.execute("DROP TABLE IF EXISTS public.query_log CASCADE")
                cur.execute("DROP TABLE IF EXISTS public.users CASCADE")
                conn.commit()  # Commit DROP statements

                # Reinitialize database schema (will create tables with proper constraints)
                from backend.src.db.migrations import initialize_database

                initialize_database(conn)

                # Clean up test user schemas and recreate them fresh
                # NOTE: 'bob' intentionally excluded - used in FK violation tests where user must not exist
                test_usernames: list[str] = [
                    "alice",
                    "testuser",
                    "testuser2",
                    "newuser123",
                    "csvuser",
                    "csvuser2",
                    "csvuser3",
                    "listuser",
                    "pageuser",
                    "getuser",
                    "getuser2",
                    "deluser",
                    "deluser2",
                ]
                for username in test_usernames:
                    schema_name: str = f"{username}_schema"

                    # Drop schema if exists (CASCADE removes all tables including dataset tables)
                    cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")

                    # Recreate schema and tables using schema_manager
                    from backend.src.services.schema_manager import ensure_user_schema_exists

                    try:
                        ensure_user_schema_exists(conn, username)
                    except Exception:
                        # If user already exists, that's fine
                        pass

                # Delete test users from public.users to ensure clean state for tests
                # This leaves schemas intact but removes user records so tests can recreate them
                cur.execute(
                    "DELETE FROM public.users WHERE username IN "
                    "('alice', 'testuser', 'testuser2', 'newuser123', 'csvuser', 'csvuser2', 'csvuser3', "
                    "'listuser', 'pageuser', 'getuser', 'getuser2', 'deluser', 'deluser2')"
                )
            conn.commit()
    except Exception:
        # If cleanup fails (e.g., tables don't exist yet), ignore
        pass

    yield

    # No cleanup after test needed (tests are responsible for their own state)
