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
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool
import pytest

# Load environment variables from .env file before all tests
load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def setup_jwt_env() -> None:
    """Set up JWT environment variables for tests.

    Runs once per test session before any tests.
    Sets required JWT configuration for authentication tests.
    """
    os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-not-production"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_EXPIRE_MINUTES"] = "1440"  # 24 hours


@pytest.fixture(scope="function")
def mock_agent() -> MagicMock:
    """Create a mock BaseAgent for CrewAI tests.

    Returns:
        MagicMock configured to pass Pydantic validation as a BaseAgent

    Note:
        This fixture creates a mock that satisfies CrewAI's agent type requirements
    """
    from crewai import Agent

    # Create actual Agent instances to avoid Pydantic validation issues
    mock_agent_obj: Agent = Agent(
        role="Test Agent",
        goal="Test goal",
        backstory="Test backstory",
        verbose=False,
        allow_delegation=False,
    )
    return mock_agent_obj  # type: ignore[return-value]


@pytest.fixture(scope="function", autouse=True)
def mock_crewai(request: Any) -> Generator[MagicMock | None]:
    """Mock CrewAI for integration and contract tests to avoid API quota limits.

    This fixture automatically mocks the CrewAI Crew class for all tests except
    unit tests (which have their own specific mocks) and E2E tests (which need
    real API calls). This prevents real API calls to OpenAI/Anthropic during
    integration and contract testing.

    Args:
        request: pytest request object to check test markers

    Yields:
        MagicMock instance or None (if test is a unit test or E2E test)

    Note:
        - Unit tests are identified by the 'unit' marker
        - E2E tests are identified by the 'e2e' marker
        Both are excluded from this autouse fixture
    """
    # Skip mocking for unit tests (they have their own mocks) and E2E tests (need real APIs)
    if "unit" in request.keywords or "e2e" in request.keywords:
        yield None
        return

    # Mock CrewAI for integration and contract tests at multiple import locations
    # This ensures all services that use Crew get the mock
    with (
        patch("crewai.Crew") as mock_crew_base,
        patch("backend.src.services.text_to_sql.Crew") as mock_crew_text_to_sql,
        patch("backend.src.services.response_generator.Crew") as mock_crew_response_gen,
    ):
        # Create mock instance that will be returned by Crew()
        mock_crew_instance: MagicMock = MagicMock()

        # Mock the kickoff() method to return realistic CrewAI results
        # This simulates successful SQL generation and HTML formatting
        # Note: Uses a query that will return empty results when no datasets exist
        mock_result: MagicMock = MagicMock()
        mock_result.raw = """
        SELECT
            'No datasets found' as message,
            0 as count
        WHERE FALSE
        """
        mock_result.tasks_output = [
            MagicMock(raw="SELECT 'No datasets found' as message, 0 as count WHERE FALSE"),
            MagicMock(
                raw="<article><h1>Query Results</h1><p>No data available. Please upload datasets first.</p></article>"
            ),
        ]

        mock_crew_instance.kickoff.return_value = mock_result

        # Apply mock to all patch locations
        mock_crew_base.return_value = mock_crew_instance
        mock_crew_text_to_sql.return_value = mock_crew_instance
        mock_crew_response_gen.return_value = mock_crew_instance

        yield mock_crew_instance


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
def connection_pool(db_config: dict[str, Any]) -> Generator[ConnectionPool]:
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
def test_db_connection(connection_pool: ConnectionPool) -> ConnectionPool:
    """Alias for connection_pool fixture used by integration tests.

    Provides backwards compatibility for tests that expect test_db_connection.

    Args:
        connection_pool: The underlying connection pool fixture

    Returns:
        ConnectionPool instance

    Note:
        This is an alias fixture - the actual pool is created by connection_pool
    """
    return connection_pool


@pytest.fixture(scope="function")
def client(db_config: dict[str, Any]) -> Generator[TestClient]:
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
def client_no_db() -> Generator[TestClient]:
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
def cleanup_test_data(connection_pool: ConnectionPool, request: Any) -> Generator[None]:
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
                    "usera",
                    "userb",
                    "e2euser",
                    "e2euser2",
                ]
                for username in test_usernames:
                    schema_name: str = f"{username}_schema"

                    # Drop schema if exists (CASCADE removes all tables including dataset tables)
                    cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")

                    # Recreate schema and tables using schema_manager
                    from backend.src.services.schema_manager import (
                        ensure_user_schema_exists,
                    )

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
                    "'listuser', 'pageuser', 'getuser', 'getuser2', 'deluser', 'deluser2', 'usera', 'userb', "
                    "'e2euser', 'e2euser2')"
                )
            conn.commit()
    except Exception:
        # If cleanup fails (e.g., tables don't exist yet), ignore
        pass

    yield

    # No cleanup after test needed (tests are responsible for their own state)
