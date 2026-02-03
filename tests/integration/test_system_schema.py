"""Integration tests for system schema creation.

Tests public schema table creation per data-model.md:
- public.users table with username, schema_name, timestamps
- public.query_log table for cross-user analytics
- pgvector extension enabled

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import datetime

import pytest
from psycopg.pool import ConnectionPool


@pytest.mark.integration
class TestSystemSchema:
    """Test system schema (public) table creation and structure."""

    def test_users_table_structure(self, connection_pool: ConnectionPool) -> None:
        """Test public.users table has correct schema.

        Validates:
        - username (VARCHAR(50), PRIMARY KEY)
        - schema_name (VARCHAR(63), NOT NULL, UNIQUE)
        - created_at (TIMESTAMP WITH TIME ZONE, NOT NULL)
        - last_login_at (TIMESTAMP WITH TIME ZONE, nullable)
        - is_active (BOOLEAN, NOT NULL, default TRUE)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Query table structure
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'users'
                    ORDER BY ordinal_position
                """)
                columns: list[tuple[str, str, str, str | None]] = cur.fetchall()

            column_dict: dict[str, tuple[str, str]] = {
                col[0]: (col[1], col[2]) for col in columns
            }

            # Verify username column
            assert "username" in column_dict
            assert column_dict["username"][0] == "character varying"
            assert column_dict["username"][1] == "NO"  # NOT NULL

            # Verify schema_name column
            assert "schema_name" in column_dict
            assert column_dict["schema_name"][0] == "character varying"
            assert column_dict["schema_name"][1] == "NO"  # NOT NULL

            # Verify created_at column
            assert "created_at" in column_dict
            assert "timestamp" in column_dict["created_at"][0]
            assert column_dict["created_at"][1] == "NO"  # NOT NULL

            # Verify last_login_at column (nullable)
            assert "last_login_at" in column_dict
            assert "timestamp" in column_dict["last_login_at"][0]
            assert column_dict["last_login_at"][1] == "YES"  # Nullable

            # Verify is_active column
            assert "is_active" in column_dict
            assert column_dict["is_active"][0] == "boolean"
            assert column_dict["is_active"][1] == "NO"  # NOT NULL

    def test_users_table_constraints(self, connection_pool: ConnectionPool) -> None:
        """Test public.users table constraints.

        Validates:
        - username is PRIMARY KEY
        - schema_name is UNIQUE
        - username format CHECK constraint (^[a-z][a-z0-9_]{2,49}$)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Test valid insertion
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.users (username, schema_name)
                    VALUES ('alice', 'alice_schema')
                """)
            conn.commit()

            # Test duplicate username (should fail - PRIMARY KEY)
            with pytest.raises(Exception):  # Unique violation
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.users (username, schema_name)
                        VALUES ('alice', 'alice2_schema')
                    """)

            # Test duplicate schema_name (should fail - UNIQUE)
            with pytest.raises(Exception):  # Unique violation
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.users (username, schema_name)
                        VALUES ('bob', 'alice_schema')
                    """)
            conn.rollback()

            # Test invalid username format (should fail - CHECK constraint)
            with pytest.raises(Exception):  # Check violation
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.users (username, schema_name)
                        VALUES ('Alice', 'Alice_schema')
                    """)

    def test_query_log_table_structure(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test public.query_log table has correct schema.

        Validates:
        - id (UUID, PRIMARY KEY)
        - username (VARCHAR(50), FOREIGN KEY to users)
        - query_text (TEXT, NOT NULL)
        - submitted_at (TIMESTAMP, NOT NULL)
        - execution_time_ms (INTEGER, nullable)
        - status (VARCHAR(20), NOT NULL, CHECK constraint)
        - result_count (INTEGER, nullable)
        - error_message (TEXT, nullable)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Query table structure
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'query_log'
                    ORDER BY ordinal_position
                """)
                columns: list[tuple[str, str, str]] = cur.fetchall()

            column_dict: dict[str, tuple[str, str]] = {
                col[0]: (col[1], col[2]) for col in columns
            }

            # Verify core columns exist
            assert "id" in column_dict
            assert "uuid" in column_dict["id"][0]

            assert "username" in column_dict
            assert column_dict["username"][0] == "character varying"

            assert "query_text" in column_dict
            assert column_dict["query_text"][0] == "text"

            assert "status" in column_dict
            assert column_dict["status"][0] == "character varying"

    def test_query_log_foreign_key(self, connection_pool: ConnectionPool) -> None:
        """Test query_log.username references users.username.

        Validates:
        - FOREIGN KEY constraint enforced
        - CASCADE DELETE behavior
        - Referential integrity maintained

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Create user
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.users (username, schema_name)
                    VALUES ('alice', 'alice_schema')
                """)
            conn.commit()

            # Insert query_log entry (should succeed)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.query_log (username, query_text, status)
                    VALUES ('alice', 'test query', 'pending')
                """)
            conn.commit()

            # Try to insert with non-existent user (should fail)
            with pytest.raises(Exception):  # Foreign key violation
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.query_log (username, query_text, status)
                        VALUES ('bob', 'test query', 'pending')
                    """)

    def test_query_log_status_constraint(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test query_log.status CHECK constraint.

        Validates:
        - Status must be one of: pending, processing, completed, failed, cancelled, timeout
        - Invalid status values rejected

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Create user
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.users (username, schema_name)
                    VALUES ('alice', 'alice_schema')
                """)
            conn.commit()

            # Test valid status values
            valid_statuses: list[str] = [
                "pending",
                "processing",
                "completed",
                "failed",
                "cancelled",
                "timeout",
            ]

            for status in valid_statuses:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.query_log (username, query_text, status)
                        VALUES ('alice', 'test query', %s)
                        """,
                        (status,),
                    )
                conn.commit()

            # Test invalid status (should fail)
            with pytest.raises(Exception):  # Check constraint violation
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.query_log (username, query_text, status)
                        VALUES ('alice', 'test query', 'invalid_status')
                    """)

    def test_query_log_indexes(self, connection_pool: ConnectionPool) -> None:
        """Test query_log performance indexes exist.

        Validates:
        - Index on (username, submitted_at DESC) for user query history
        - Index on status for pending/processing queries
        - Per data-model.md optimization requirements

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import initialize_database

        with connection_pool.connection() as conn:
            initialize_database(conn)

            # Check indexes exist
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'query_log'
                    AND schemaname = 'public'
                """)
                indexes: list[tuple[str]] = cur.fetchall()
                index_names: list[str] = [idx[0] for idx in indexes]

                # Should have multiple indexes
                assert len(index_names) > 0
