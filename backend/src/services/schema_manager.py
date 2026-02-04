"""User schema manager for automatic per-user database schema provisioning.

Implements FR-020, FR-021:
- Auto-create user schema on first authentication
- Username-based schema isolation (username_schema)
- Idempotent schema creation
- Thread-safe operations

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from datetime import UTC, datetime

from psycopg import Connection, errors

from backend.src.db.schemas import (
    COLUMN_MAPPINGS_DATASET_INDEX_SQL,
    COLUMN_MAPPINGS_EMBEDDING_INDEX_SQL,
    COLUMN_MAPPINGS_TABLE_SQL,
    CROSS_REFERENCES_SOURCE_INDEX_SQL,
    CROSS_REFERENCES_TABLE_SQL,
    CROSS_REFERENCES_TARGET_INDEX_SQL,
    DATASETS_FILENAME_INDEX_SQL,
    DATASETS_TABLE_SQL,
    DATASETS_UPLOADED_INDEX_SQL,
    QUERIES_STATUS_INDEX_SQL,
    QUERIES_SUBMITTED_INDEX_SQL,
    QUERIES_TABLE_SQL,
    RESPONSES_GENERATED_INDEX_SQL,
    RESPONSES_QUERY_INDEX_SQL,
    RESPONSES_TABLE_SQL,
)


def ensure_user_schema_exists(conn: Connection[tuple[str, ...]], username: str) -> None:
    """Ensure user record and schema exist, create if missing.

    Creates:
    1. User record in public.users table
    2. User-specific PostgreSQL schema (username_schema)
    3. All required tables in user schema per data-model.md:
       - datasets
       - column_mappings
       - cross_references
       - queries
       - responses

    Args:
        conn: Active PostgreSQL connection (synchronous)
        username: User's username (lowercase, validated)

    Raises:
        psycopg.DatabaseError: If schema creation fails
        ValueError: If username is invalid

    Per FR-021: Auto-provision schema on first login
    Per FR-020: Username-based schema tenancy for isolation

    Note: This function is idempotent - safe to call multiple times
    for the same username without creating duplicates
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    if not username.islower():
        raise ValueError("Username must be lowercase")

    schema_name: str = f"{username}_schema"

    with conn.cursor() as cur:
        # Create user record if not exists (idempotent, thread-safe)
        # Handle both username and schema_name uniqueness constraints
        try:
            cur.execute(
                """
                INSERT INTO public.users (username, schema_name, created_at)
                VALUES (%s, %s, NOW())
                """,
                (username, schema_name),
            )
        except errors.UniqueViolation:
            # User already exists - rollback failed INSERT and verify schema_name matches
            conn.rollback()

            # Re-check if user exists with correct schema_name
            cur.execute(
                "SELECT schema_name FROM public.users WHERE username = %s",
                (username,),
            )
            row: tuple[str, ...] | None = cur.fetchone()
            if row and row[0] != schema_name:
                raise ValueError(
                    f"User '{username}' already exists with different schema name: "
                    f"expected '{schema_name}', found '{row[0]}'"
                )
            # Same username and schema_name - idempotent, continue

        # Create user schema if not exists (idempotent)
        schema_sql: str = f"CREATE SCHEMA IF NOT EXISTS {schema_name}"
        cur.execute(schema_sql)

        # Create datasets table
        datasets_sql: str = DATASETS_TABLE_SQL.format(schema_name=schema_name)
        cur.execute(datasets_sql)

        # Create indexes for datasets table
        datasets_uploaded_idx_sql: str = DATASETS_UPLOADED_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(datasets_uploaded_idx_sql)
        datasets_filename_idx_sql: str = DATASETS_FILENAME_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(datasets_filename_idx_sql)

        # Create column_mappings table
        column_mappings_sql: str = COLUMN_MAPPINGS_TABLE_SQL.format(schema_name=schema_name)
        cur.execute(column_mappings_sql)

        # Create indexes for column_mappings table
        col_map_dataset_idx_sql: str = COLUMN_MAPPINGS_DATASET_INDEX_SQL.format(
            schema_name=schema_name
        )
        cur.execute(col_map_dataset_idx_sql)
        col_map_embed_idx_sql: str = COLUMN_MAPPINGS_EMBEDDING_INDEX_SQL.format(
            schema_name=schema_name
        )
        cur.execute(col_map_embed_idx_sql)

        # Create cross_references table
        cross_references_sql: str = CROSS_REFERENCES_TABLE_SQL.format(schema_name=schema_name)
        cur.execute(cross_references_sql)

        # Create indexes for cross_references table
        cross_refs_source_idx_sql: str = CROSS_REFERENCES_SOURCE_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(cross_refs_source_idx_sql)
        cross_refs_target_idx_sql: str = CROSS_REFERENCES_TARGET_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(cross_refs_target_idx_sql)

        # Create queries table
        queries_sql: str = QUERIES_TABLE_SQL.format(schema_name=schema_name)
        cur.execute(queries_sql)

        # Create indexes for queries table
        queries_submitted_idx_sql: str = QUERIES_SUBMITTED_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(queries_submitted_idx_sql)
        queries_status_idx_sql: str = QUERIES_STATUS_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(queries_status_idx_sql)

        # Create responses table
        responses_sql: str = RESPONSES_TABLE_SQL.format(schema_name=schema_name)
        cur.execute(responses_sql)

        # Create indexes for responses table
        responses_query_idx_sql: str = RESPONSES_QUERY_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(responses_query_idx_sql)
        responses_generated_idx_sql: str = RESPONSES_GENERATED_INDEX_SQL.format(schema_name=schema_name)
        cur.execute(responses_generated_idx_sql)

    # Commit transaction
    conn.commit()


def update_last_login(conn: Connection[tuple[str, ...]], username: str) -> None:
    """Update user's last_login_at timestamp to current time.

    Args:
        conn: Active PostgreSQL connection (synchronous)
        username: User's username

    Raises:
        psycopg.DatabaseError: If update fails
        ValueError: If username doesn't exist

    Per FR-021: Track user authentication for observability
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    now: datetime = datetime.now(UTC)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.users
            SET last_login_at = %s
            WHERE username = %s
            """,
            (now, username),
        )

        # Verify update succeeded
        if cur.rowcount == 0:
            raise ValueError(f"User '{username}' not found")

    conn.commit()
