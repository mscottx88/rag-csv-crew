"""Pytest configuration and shared fixtures for backend tests.

Provides database connection pools, test schemas, and common test utilities.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import os
import uuid
from typing import Any, Generator

import pytest
from psycopg import Connection, sql
from psycopg_pool import ConnectionPool

from src.models.config import DatabaseConfig


@pytest.fixture(scope="session")
def test_database_config() -> DatabaseConfig:
    """Create database configuration for tests.

    Uses environment variables with TEST_DATABASE_ prefix, falling back to
    DATABASE_ prefix if not set. Allows running tests against a separate
    test database or the main database with test schemas.

    Returns:
        DatabaseConfig configured for test environment
    """
    # Use TEST_DATABASE_* env vars if available, otherwise fall back to DATABASE_*
    config: DatabaseConfig = DatabaseConfig(
        host=os.getenv("TEST_DATABASE_HOST", os.getenv("DATABASE_HOST", "localhost")),
        port=int(os.getenv("TEST_DATABASE_PORT", os.getenv("DATABASE_PORT", "5432"))),
        database=os.getenv("TEST_DATABASE_DATABASE", os.getenv("DATABASE_DATABASE", "ragcsv")),
        user=os.getenv("TEST_DATABASE_USER", os.getenv("DATABASE_USER", "postgres")),
        password=os.getenv("TEST_DATABASE_PASSWORD", os.getenv("DATABASE_PASSWORD", "")),
        pool_min_size=2,
        pool_max_size=5,
        statement_timeout=30000,
    )
    return config


@pytest.fixture(scope="session")
def db_pool_session(test_database_config: DatabaseConfig) -> Generator[ConnectionPool, None, None]:
    """Create session-scoped database connection pool.

    Creates a single connection pool shared across all tests in the session.
    Automatically closes pool after all tests complete.

    Args:
        test_database_config: Test database configuration

    Yields:
        ConnectionPool for test database

    Cleanup:
        Closes pool and releases all connections
    """
    conninfo: str = (
        f"host={test_database_config.host} "
        f"port={test_database_config.port} "
        f"dbname={test_database_config.database} "
        f"user={test_database_config.user} "
        f"password={test_database_config.password} "
        f"options='-c statement_timeout={test_database_config.statement_timeout}'"
    )

    pool: ConnectionPool = ConnectionPool(
        conninfo=conninfo,
        min_size=test_database_config.pool_min_size,
        max_size=test_database_config.pool_max_size,
        open=True,
    )

    yield pool

    # Cleanup: close pool after all tests
    pool.close()


@pytest.fixture
def db_pool(db_pool_session: ConnectionPool) -> ConnectionPool:
    """Function-scoped alias for session-scoped pool.

    Provides test-level access to the session pool without recreating it.
    Tests use this fixture to get database connections.

    Args:
        db_pool_session: Session-scoped connection pool

    Returns:
        ConnectionPool for test database
    """
    return db_pool_session


@pytest.fixture
def test_username() -> str:
    """Generate unique test username for schema isolation.

    Creates a unique username for each test to ensure complete isolation
    between tests. Each username gets its own schema (username_schema).

    Returns:
        Unique test username (e.g., "test_user_abc123")
    """
    username: str = f"test_user_{uuid.uuid4().hex[:8]}"
    return username


@pytest.fixture
def test_schema(db_pool: ConnectionPool, test_username: str) -> Generator[str, None, None]:
    """Create and cleanup test schema for a test.

    Creates a user-specific schema before the test runs, then drops it after.
    Ensures complete isolation between tests.

    Args:
        db_pool: Database connection pool
        test_username: Unique test username

    Yields:
        Schema name (username_schema format)

    Cleanup:
        Drops schema and all objects CASCADE after test completes
    """
    schema_name: str = f"{test_username}_schema"

    # Setup: create schema
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            # Create schema
            cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema_name)))

            # Create required tables in schema
            cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema_name)))

            # Create datasets table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    username VARCHAR(255) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, filename)
                )
            """)

            # Create column_mappings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS column_mappings (
                    id SERIAL PRIMARY KEY,
                    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    column_name VARCHAR(255) NOT NULL,
                    data_type VARCHAR(50) NOT NULL,
                    sample_values TEXT[],
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(dataset_id, column_name)
                )
            """)

            # Add embedding column if pgvector available
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("""
                    ALTER TABLE column_mappings
                    ADD COLUMN IF NOT EXISTS embedding vector(1536)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_column_mappings_embedding
                    ON column_mappings USING hnsw (embedding vector_cosine_ops)
                """)
            except Exception:
                # pgvector not available, skip embedding column
                pass

            # Create cross_references table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cross_references (
                    id SERIAL PRIMARY KEY,
                    source_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    source_column VARCHAR(255) NOT NULL,
                    target_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    target_column VARCHAR(255) NOT NULL,
                    relationship_type VARCHAR(50) NOT NULL,
                    confidence_score REAL NOT NULL,
                    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_dataset_id, source_column, target_dataset_id, target_column)
                )
            """)

        conn.commit()

    yield schema_name

    # Cleanup: drop schema after test
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name))
            )
        conn.commit()


@pytest.fixture
def test_connection(
    db_pool: ConnectionPool, test_schema: str
) -> Generator[Connection[Any], None, None]:
    """Create test database connection with schema set.

    Provides a single connection for a test with search_path set to the test schema.
    Automatically commits or rolls back based on test outcome.

    Args:
        db_pool: Database connection pool
        test_schema: Test schema name

    Yields:
        Database connection with test schema in search path

    Cleanup:
        Commits if test passed, rolls back if test failed
    """
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(test_schema)))
        yield conn
        # Auto-commit on test success (connection context manager handles this)
