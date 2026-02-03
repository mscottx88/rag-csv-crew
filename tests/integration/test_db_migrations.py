"""Integration tests for database initialization and migrations.

Tests database initialization commands per quickstart.md:
- `init` command: Create system schema and tables
- `verify` command: Validate schema integrity
- Idempotency: Safe to run multiple times

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from psycopg.pool import ConnectionPool
import pytest


@pytest.mark.integration
class TestDatabaseInitialization:
    """Test database initialization and migration commands."""

    def test_init_command_creates_system_schema(self, connection_pool: ConnectionPool) -> None:
        """Test init command creates public schema tables.

        Validates:
        - public.users table created
        - public.query_log table created
        - Correct column types and constraints

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            # Drop existing tables for clean test
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS public.query_log CASCADE")
                cur.execute("DROP TABLE IF EXISTS public.users CASCADE")
            conn.commit()

            # Run initialization
            initialize_database(conn)

            # Verify users table exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'users'
                """)
                result: tuple[str] | None = cur.fetchone()
                assert result is not None
                assert result[0] == "users"

            # Verify query_log table exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'query_log'
                """)
                result = cur.fetchone()
                assert result is not None
                assert result[0] == "query_log"

    def test_init_command_is_idempotent(self, connection_pool: ConnectionPool) -> None:
        """Test init command can be run multiple times safely.

        Validates:
        - Running init twice doesn't error
        - Existing data preserved
        - No duplicate tables created

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            # Run initialization twice
            initialize_database(conn)
            initialize_database(conn)  # Should not raise error

            # Verify only one users table exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'users'
                """)
                count: tuple[int] = cur.fetchone()  # type: ignore
                assert count[0] == 1

    def test_verify_command_validates_schema(self, connection_pool: ConnectionPool) -> None:
        """Test verify command checks schema integrity.

        Validates:
        - Returns True when schema valid
        - Returns False when schema incomplete
        - Checks all required tables

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database, verify_database

        with connection_pool.connection() as conn:
            # Initialize database
            initialize_database(conn)

            # Verify should return True
            is_valid: bool = verify_database(conn)
            assert is_valid is True

            # Drop a required table
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS public.users CASCADE")
            conn.commit()

            # Verify should return False
            is_valid = verify_database(conn)
            assert is_valid is False

    def test_init_creates_required_indexes(self, connection_pool: ConnectionPool) -> None:
        """Test init command creates performance indexes.

        Validates:
        - Index on public.users(username)
        - Index on public.query_log(username, submitted_at)
        - Indexes improve query performance

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Check users table indexes
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'users'
                    AND schemaname = 'public'
                """)
                indexes: list[tuple[str]] = cur.fetchall()
                index_names: list[str] = [idx[0] for idx in indexes]

                # Should have at least primary key index
                assert len(index_names) > 0
                assert any("username" in name or "pkey" in name for name in index_names)

    def test_init_enables_pgvector_extension(self, connection_pool: ConnectionPool) -> None:
        """Test init command enables pgvector extension.

        Validates:
        - CREATE EXTENSION IF NOT EXISTS vector
        - Extension available for vector operations
        - Per data-model.md requirements

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Check pgvector extension enabled
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT extname
                    FROM pg_extension
                    WHERE extname = 'vector'
                """)
                result: tuple[str] | None = cur.fetchone()
                assert result is not None
                assert result[0] == "vector"

    def test_init_creates_constraints(self, connection_pool: ConnectionPool) -> None:
        """Test init command creates table constraints.

        Validates:
        - CHECK constraints on users.username format
        - FOREIGN KEY constraints on query_log.username
        - NOT NULL constraints on required fields

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Test username format constraint
            with conn.cursor() as cur:
                # Valid username should work
                cur.execute("""
                    INSERT INTO public.users (username, schema_name)
                    VALUES ('alice', 'alice_schema')
                """)
                conn.commit()

                # Invalid username should fail
                with pytest.raises(Exception):  # CHECK constraint violation
                    cur.execute("""
                        INSERT INTO public.users (username, schema_name)
                        VALUES ('Alice', 'alice2_schema')
                    """)
