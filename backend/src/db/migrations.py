"""Database schema initialization and migrations.

Implements database initialization per data-model.md:
- System schema (public): users, query_log tables
- Per-user schemas: datasets, queries, responses, column_mappings, cross_references
- pgvector extension for semantic search
- Indexes and constraints per specifications

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import Connection

logger: logging.Logger = logging.getLogger(__name__)


def initialize_database(conn: "Connection") -> None:
    """Initialize system schema and tables in public schema.

    Creates:
    - pgvector extension
    - public.users table
    - public.query_log table
    - All required indexes and constraints

    Idempotent: Safe to run multiple times.

    Args:
        conn: Database connection

    Raises:
        psycopg.Error: On database operation failure
    """
    logger.info("Initializing database system schema")

    with conn.cursor() as cur:
        # Enable pgvector extension for semantic search
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.debug("pgvector extension enabled")

        # Create public.users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.users (
                username VARCHAR(50) PRIMARY KEY,
                schema_name VARCHAR(63) NOT NULL UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                last_login_at TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,

                CONSTRAINT username_format CHECK (username ~ '^[a-z][a-z0-9_]{2,49}$')
            )
        """)
        logger.debug("Created public.users table")

        # Create index on active users
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_active
            ON public.users (is_active)
            WHERE is_active = TRUE
        """)

        # Create public.query_log table for cross-user analytics
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.query_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(50) NOT NULL REFERENCES public.users(username) ON DELETE CASCADE,
                query_text TEXT NOT NULL,
                submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                execution_time_ms INTEGER,
                status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'timeout')),
                result_count INTEGER,
                error_message TEXT,

                CONSTRAINT positive_execution_time CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
                CONSTRAINT positive_result_count CHECK (result_count IS NULL OR result_count >= 0)
            )
        """)
        logger.debug("Created public.query_log table")

        # Create query_log indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_log_user_time
            ON public.query_log (username, submitted_at DESC)
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_log_status
            ON public.query_log (status)
            WHERE status IN ('pending', 'processing')
        """)

    conn.commit()
    logger.info("Database system schema initialized successfully")


def verify_database(conn: "Connection") -> bool:
    """Verify database schema integrity.

    Checks existence of required system tables:
    - public.users
    - public.query_log
    - pgvector extension

    Args:
        conn: Database connection

    Returns:
        True if schema valid, False if incomplete
    """
    logger.info("Verifying database schema integrity")

    try:
        with conn.cursor() as cur:
            # Check pgvector extension
            cur.execute("""
                SELECT extname
                FROM pg_extension
                WHERE extname = 'vector'
            """)
            if cur.fetchone() is None:
                logger.error("pgvector extension not found")
                return False

            # Check public.users table
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'users'
            """)
            if cur.fetchone() is None:
                logger.error("public.users table not found")
                return False

            # Check public.query_log table
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'query_log'
            """)
            if cur.fetchone() is None:
                logger.error("public.query_log table not found")
                return False

        logger.info("Database schema verification passed")
        return True

    except Exception as e:
        logger.error(
            "Database schema verification failed",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        return False


def create_user_schema(conn: "Connection", username: str) -> None:
    """Create per-user schema with all required tables.

    Creates schema: {username}_schema
    Tables:
    - datasets: Metadata for uploaded CSV files
    - column_mappings: Semantic understanding of columns (with vector embeddings)
    - cross_references: Detected relationships between datasets
    - queries: Per-user query history
    - responses: Cached query responses

    Idempotent: Safe to run multiple times.

    Args:
        conn: Database connection
        username: Username for schema creation

    Raises:
        psycopg.Error: On database operation failure
    """
    schema_name: str = f"{username}_schema"
    logger.info(f"Creating user schema: {schema_name}")

    with conn.cursor() as cur:
        # Create user schema
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        logger.debug(f"Created schema: {schema_name}")

        # Create datasets table
        cur.execute(f"""
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
        """)
        logger.debug(f"Created {schema_name}.datasets table")

        # Create datasets indexes
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_datasets_uploaded
            ON {schema_name}.datasets (uploaded_at DESC)
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_datasets_filename
            ON {schema_name}.datasets (filename)
        """)

        # Create column_mappings table with vector embedding column
        cur.execute(f"""
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
        """)
        logger.debug(f"Created {schema_name}.column_mappings table")

        # Create column_mappings indexes
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_column_mappings_dataset
            ON {schema_name}.column_mappings (dataset_id)
        """)

        # Create HNSW index for vector similarity search
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_column_mappings_embedding
            ON {schema_name}.column_mappings
            USING hnsw (embedding vector_cosine_ops)
        """)

        # Create cross_references table
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.cross_references (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
                source_column VARCHAR(255) NOT NULL,
                target_dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
                target_column VARCHAR(255) NOT NULL,
                relationship_type VARCHAR(50) NOT NULL CHECK (relationship_type IN ('foreign_key', 'shared_values', 'similar_values')),
                confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
                detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

                UNIQUE (source_dataset_id, source_column, target_dataset_id, target_column)
            )
        """)
        logger.debug(f"Created {schema_name}.cross_references table")

        # Create cross_references indexes
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_cross_refs_source
            ON {schema_name}.cross_references (source_dataset_id)
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_cross_refs_target
            ON {schema_name}.cross_references (target_dataset_id)
        """)

        # Create queries table
        cur.execute(f"""
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
        """)
        logger.debug(f"Created {schema_name}.queries table")

        # Create queries indexes
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_queries_submitted
            ON {schema_name}.queries (submitted_at DESC)
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_queries_status
            ON {schema_name}.queries (status)
            WHERE status IN ('pending', 'processing')
        """)

        # Create responses table
        cur.execute(f"""
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
        """)
        logger.debug(f"Created {schema_name}.responses table")

        # Create responses indexes
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_responses_query
            ON {schema_name}.responses (query_id)
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_responses_generated
            ON {schema_name}.responses (generated_at DESC)
        """)

    conn.commit()
    logger.info(f"User schema {schema_name} created successfully")
