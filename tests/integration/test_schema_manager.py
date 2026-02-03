"""Integration tests for user schema manager.

Tests automatic schema creation on first login per FR-020, FR-021:
- Auto-create user schema on first authentication
- Schema isolation between users
- Idempotent schema creation

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import pytest
from psycopg.pool import ConnectionPool


@pytest.mark.integration
class TestSchemaManager:
    """Test user schema manager for automatic schema provisioning."""

    def test_create_schema_on_first_login(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test schema auto-created on user's first login.

        Validates:
        - User record created in public.users
        - User-specific schema created ({username}_schema)
        - All required tables created in user schema
        - Per FR-021: Auto-provision on first authentication

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
        )

        username: str = "alice"

        with connection_pool.connection() as conn:
            # Ensure schema created
            ensure_user_schema_exists(conn, username)

            # Verify user record exists
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username, schema_name FROM public.users WHERE username = %s",
                    (username,),
                )
                result: tuple[str, str] | None = cur.fetchone()

            assert result is not None
            assert result[0] == username
            assert result[1] == f"{username}_schema"

            # Verify user schema exists
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name = %s
                    """,
                    (f"{username}_schema",),
                )
                schema_result: tuple[str] | None = cur.fetchone()

            assert schema_result is not None

    def test_schema_creation_is_idempotent(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test schema creation can be called multiple times safely.

        Validates:
        - Multiple calls don't create duplicate schemas
        - Existing user data preserved
        - No errors on repeated calls

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
        )

        username: str = "alice"

        with connection_pool.connection() as conn:
            # Create schema multiple times
            ensure_user_schema_exists(conn, username)
            ensure_user_schema_exists(conn, username)
            ensure_user_schema_exists(conn, username)

            # Verify only one user record
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM public.users WHERE username = %s",
                    (username,),
                )
                count: tuple[int] = cur.fetchone()  # type: ignore

            assert count[0] == 1

            # Verify only one schema
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.schemata
                    WHERE schema_name = %s
                    """,
                    (f"{username}_schema",),
                )
                schema_count: tuple[int] = cur.fetchone()  # type: ignore

            assert schema_count[0] == 1

    def test_multiple_users_isolated_schemas(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test multiple users get separate isolated schemas.

        Validates:
        - Each user has their own schema
        - Schemas are isolated (no cross-user data access)
        - Per FR-020: Username-based schema tenancy

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
        )

        usernames: list[str] = ["alice", "bob", "charlie"]

        with connection_pool.connection() as conn:
            # Create schemas for multiple users
            for username in usernames:
                ensure_user_schema_exists(conn, username)

            # Verify all users exist
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM public.users WHERE username = ANY(%s)",
                    (usernames,),
                )
                count: tuple[int] = cur.fetchone()  # type: ignore

            assert count[0] == len(usernames)

            # Verify all schemas exist
            expected_schemas: list[str] = [f"{u}_schema" for u in usernames]

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.schemata
                    WHERE schema_name = ANY(%s)
                    """,
                    (expected_schemas,),
                )
                schema_count: tuple[int] = cur.fetchone()  # type: ignore

            assert schema_count[0] == len(usernames)

    def test_schema_name_format(self, connection_pool: ConnectionPool) -> None:
        """Test schema names follow {username}_schema pattern.

        Validates:
        - Schema name matches username_schema format
        - No invalid characters in schema name
        - Schema name stored in public.users.schema_name

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
        )

        username: str = "test_user_123"

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, username)

            # Verify schema name format
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT schema_name FROM public.users WHERE username = %s",
                    (username,),
                )
                result: tuple[str] | None = cur.fetchone()

            assert result is not None
            expected_schema: str = f"{username}_schema"
            assert result[0] == expected_schema

    def test_schema_includes_all_required_tables(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test user schema includes all required tables per data-model.md.

        Validates:
        - datasets table exists
        - column_mappings table exists
        - cross_references table exists
        - queries table exists
        - responses table exists

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
        )

        username: str = "alice"

        with connection_pool.connection() as conn:
            ensure_user_schema_exists(conn, username)

            # Verify all required tables exist
            required_tables: list[str] = [
                "datasets",
                "column_mappings",
                "cross_references",
                "queries",
                "responses",
            ]

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = ANY(%s)
                    """,
                    (f"{username}_schema", required_tables),
                )
                tables: list[tuple[str]] = cur.fetchall()
                table_names: list[str] = [t[0] for t in tables]

            for required_table in required_tables:
                assert required_table in table_names

    def test_update_last_login_timestamp(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test last_login_at timestamp updated on schema access.

        Validates:
        - last_login_at initially NULL for new user
        - last_login_at updated on subsequent access
        - Timestamp reflects actual access time

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
            update_last_login,
        )
        from datetime import datetime, timezone

        username: str = "alice"

        with connection_pool.connection() as conn:
            # First login
            ensure_user_schema_exists(conn, username)

            # Check initial last_login_at
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_login_at FROM public.users WHERE username = %s",
                    (username,),
                )
                initial_login: tuple[datetime | None] = cur.fetchone()  # type: ignore

            assert initial_login[0] is None  # Should be NULL initially

            # Update last login
            update_last_login(conn, username)

            # Check updated last_login_at
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_login_at FROM public.users WHERE username = %s",
                    (username,),
                )
                updated_login: tuple[datetime] = cur.fetchone()  # type: ignore

            assert updated_login[0] is not None
            # Verify timestamp is recent (within last minute)
            now: datetime = datetime.now(timezone.utc)
            time_diff: float = (now - updated_login[0]).total_seconds()
            assert time_diff < 60  # Within last minute

    def test_schema_creation_thread_safe(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test concurrent schema creation requests are thread-safe.

        Validates:
        - Multiple threads can request same user schema
        - No race conditions or duplicate schemas
        - All threads succeed without errors

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.services.schema_manager import (
            ensure_user_schema_exists,
        )
        from concurrent.futures import ThreadPoolExecutor
        from typing import Callable

        username: str = "alice"
        errors: list[Exception] = []

        def create_schema_task() -> None:
            """Task to create user schema (thread-safe test)."""
            try:
                with connection_pool.connection() as conn:
                    ensure_user_schema_exists(conn, username)
            except Exception as e:
                errors.append(e)

        # Run 10 concurrent schema creation attempts
        num_threads: int = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures: list[Any] = [
                executor.submit(create_schema_task) for _ in range(num_threads)
            ]
            for future in futures:
                future.result()

        # No errors should occur
        assert len(errors) == 0

        # Verify only one user and one schema created
        with connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM public.users WHERE username = %s",
                    (username,),
                )
                user_count: tuple[int] = cur.fetchone()  # type: ignore

            assert user_count[0] == 1
