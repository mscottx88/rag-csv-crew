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

from psycopg import sql

from src.db.schemas import (
    COLUMN_MAPPINGS_DATASET_INDEX_SQL,
    COLUMN_MAPPINGS_EMBEDDING_INDEX_SQL,
    COLUMN_MAPPINGS_FULLTEXT_INDEX_SQL,
    COLUMN_MAPPINGS_TABLE_SQL,
    COLUMN_METADATA_DATASET_INDEX_SQL,
    COLUMN_METADATA_TABLE_SQL,
    COLUMN_METADATA_TOP_VALUES_INDEX_SQL,
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

    except Exception as e:  # pylint: disable=broad-exception-caught
        # TODO(pylint-refactor): Catch specific database exceptions (psycopg.errors.UndefinedTable, etc.)  # pylint: disable=line-too-long
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
    logger.info("Creating user schema: %s", schema_name)

    with conn.cursor() as cur:
        # Create user schema (T208-POLISH: SQL injection prevention)
        create_schema_sql: sql.Composed = sql.SQL("CREATE SCHEMA IF NOT EXISTS {schema}").format(
            schema=sql.Identifier(schema_name)
        )
        cur.execute(create_schema_sql)
        logger.debug("Created schema: %s", schema_name)

        # Create datasets table
        cur.execute(DATASETS_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.datasets table", schema_name)

        # Create datasets indexes
        cur.execute(DATASETS_UPLOADED_INDEX_SQL.format(schema_name=schema_name))
        cur.execute(DATASETS_FILENAME_INDEX_SQL.format(schema_name=schema_name))

        # Create column_mappings table with vector embedding column
        cur.execute(COLUMN_MAPPINGS_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.column_mappings table", schema_name)

        # Create column_mappings indexes
        cur.execute(COLUMN_MAPPINGS_DATASET_INDEX_SQL.format(schema_name=schema_name))

        # Create HNSW index for vector similarity search
        cur.execute(COLUMN_MAPPINGS_EMBEDDING_INDEX_SQL.format(schema_name=schema_name))

        # Create GIN index for full-text search
        cur.execute(COLUMN_MAPPINGS_FULLTEXT_INDEX_SQL.format(schema_name=schema_name))

        # Create cross_references table
        cur.execute(CROSS_REFERENCES_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.cross_references table", schema_name)

        # Create cross_references indexes
        cur.execute(CROSS_REFERENCES_SOURCE_INDEX_SQL.format(schema_name=schema_name))
        cur.execute(CROSS_REFERENCES_TARGET_INDEX_SQL.format(schema_name=schema_name))

        # Create queries table
        cur.execute(QUERIES_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.queries table", schema_name)

        # Create queries indexes
        cur.execute(QUERIES_SUBMITTED_INDEX_SQL.format(schema_name=schema_name))
        cur.execute(QUERIES_STATUS_INDEX_SQL.format(schema_name=schema_name))

        # Create responses table
        cur.execute(RESPONSES_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.responses table", schema_name)

        # Create responses indexes
        cur.execute(RESPONSES_QUERY_INDEX_SQL.format(schema_name=schema_name))
        cur.execute(RESPONSES_GENERATED_INDEX_SQL.format(schema_name=schema_name))

        # Create column_metadata table
        cur.execute(COLUMN_METADATA_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.column_metadata table", schema_name)

        # Create column_metadata indexes
        cur.execute(COLUMN_METADATA_DATASET_INDEX_SQL.format(schema_name=schema_name))
        cur.execute(COLUMN_METADATA_TOP_VALUES_INDEX_SQL.format(schema_name=schema_name))

    conn.commit()
    logger.info("User schema %s created successfully", schema_name)


def add_column_metadata_table(conn: "Connection", username: str) -> None:
    """Add column_metadata table to existing user schema.

    Migration function to add column_metadata table and indexes to schemas
    that were created before this feature was added.

    Args:
        conn: Database connection with active transaction
        username: Username for schema context

    Raises:
        psycopg.Error: On database operation failure
    """
    schema_name: str = f"{username}_schema"
    logger.info("Adding column_metadata table to schema: %s", schema_name)

    with conn.cursor() as cur:
        # Create column_metadata table
        cur.execute(COLUMN_METADATA_TABLE_SQL.format(schema_name=schema_name))
        logger.debug("Created %s.column_metadata table", schema_name)

        # Create column_metadata indexes
        cur.execute(COLUMN_METADATA_DATASET_INDEX_SQL.format(schema_name=schema_name))
        cur.execute(COLUMN_METADATA_TOP_VALUES_INDEX_SQL.format(schema_name=schema_name))
        logger.debug("Created column_metadata indexes for %s", schema_name)

    conn.commit()
    logger.info("column_metadata table added to %s successfully", schema_name)
