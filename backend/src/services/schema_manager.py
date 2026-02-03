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

from psycopg import Connection


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
        # Create user record if not exists (idempotent)
        cur.execute(
            """
            INSERT INTO public.users (username, schema_name, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (username) DO NOTHING
            """,
            (username, schema_name),
        )

        # Create user schema if not exists (idempotent)
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

        # Create datasets table
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.datasets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255) NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                table_name VARCHAR(63) NOT NULL UNIQUE,
                uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                row_count BIGINT NOT NULL,
                column_count INTEGER NOT NULL,
                file_size_bytes BIGINT NOT NULL,
                schema_json JSONB NOT NULL,

                CONSTRAINT positive_row_count CHECK (row_count >= 0),
                CONSTRAINT positive_column_count CHECK (column_count > 0),
                CONSTRAINT positive_file_size CHECK (file_size_bytes > 0),
                CONSTRAINT valid_table_name CHECK (table_name ~ '^[a-z][a-z0-9_]{{0,62}}$')
            )
            """
        )

        # Create indexes for datasets table
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_datasets_uploaded
            ON {schema_name}.datasets (uploaded_at DESC)
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_datasets_filename
            ON {schema_name}.datasets (filename)
            """
        )

        # Create column_mappings table
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.column_mappings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
                column_name VARCHAR(255) NOT NULL,
                inferred_type VARCHAR(50) NOT NULL,
                semantic_type VARCHAR(100),
                description TEXT,
                embedding vector(1536),

                UNIQUE (dataset_id, column_name)
            )
            """
        )

        # Create indexes for column_mappings table
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_column_mappings_dataset
            ON {schema_name}.column_mappings (dataset_id)
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_column_mappings_embedding
            ON {schema_name}.column_mappings USING hnsw (embedding vector_cosine_ops)
            """
        )

        # Create cross_references table
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.cross_references (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_dataset_id UUID NOT NULL
                    REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
                source_column VARCHAR(255) NOT NULL,
                target_dataset_id UUID NOT NULL
                    REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
                target_column VARCHAR(255) NOT NULL,
                relationship_type VARCHAR(50) NOT NULL CHECK (relationship_type IN ('foreign_key', 'shared_values', 'similar_values')),
                confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
                detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

                UNIQUE (source_dataset_id, source_column, target_dataset_id, target_column)
            )
            """
        )

        # Create indexes for cross_references table
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_cross_refs_source
            ON {schema_name}.cross_references (source_dataset_id)
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_cross_refs_target
            ON {schema_name}.cross_references (target_dataset_id)
            """
        )

        # Create queries table
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.queries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                query_text TEXT NOT NULL,
                submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'timeout')),
                generated_sql TEXT,
                result_count INTEGER,
                execution_time_ms INTEGER,

                CONSTRAINT positive_execution_time CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
                CONSTRAINT positive_result_count CHECK (result_count IS NULL OR result_count >= 0)
            )
            """
        )

        # Create indexes for queries table
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_queries_submitted
            ON {schema_name}.queries (submitted_at DESC)
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_queries_status
            ON {schema_name}.queries (status) WHERE status IN ('pending', 'processing')
            """
        )

        # Create responses table
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.responses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                query_id UUID NOT NULL REFERENCES {schema_name}.queries(id) ON DELETE CASCADE,
                html_content TEXT NOT NULL,
                plain_text TEXT NOT NULL,
                confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
                generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                data_snapshot JSONB,

                UNIQUE (query_id)
            )
            """
        )

        # Create indexes for responses table
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_responses_query
            ON {schema_name}.responses (query_id)
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_responses_generated
            ON {schema_name}.responses (generated_at DESC)
            """
        )

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
