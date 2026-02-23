"""Migration script to add progress_message column to queries tables.

Adds progress_message TEXT column to all existing user schema queries tables
to support real-time progress feedback during query processing.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import logging
import os
from typing import Any

from dotenv import load_dotenv
from psycopg import Connection
from psycopg_pool import ConnectionPool

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger: logging.Logger = logging.getLogger(__name__)


def add_progress_message_column(pool: ConnectionPool) -> None:
    """Add progress_message column to all existing user schema queries tables.

    Args:
        pool: Database connection pool
    """
    logger.info("Starting migration: Adding progress_message column to queries tables")

    with pool.connection() as conn:
        conn: Connection
        with conn.cursor() as cur:
            # Get list of all user schemas
            cur.execute("""
                SELECT schema_name
                FROM public.users
                WHERE is_active = TRUE
            """)
            user_schemas: list[tuple[str, ...]] = cur.fetchall()

            if not user_schemas:
                logger.info("No user schemas found. Migration complete.")
                return

            logger.info(f"Found {len(user_schemas)} user schema(s) to migrate")

            # Add progress_message column to each user's queries table
            for row in user_schemas:
                schema_name: str = row[0]
                logger.info(f"Migrating schema: {schema_name}")

                try:
                    # Check if column already exists
                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s
                        AND table_name = 'queries'
                        AND column_name = 'progress_message'
                        """,
                        (schema_name,),
                    )
                    column_exists: tuple[Any, ...] | None = cur.fetchone()

                    if column_exists:
                        logger.info(
                            f"Column progress_message already exists in {schema_name}.queries"
                        )
                        continue

                    # Add progress_message column
                    # pylint: disable=consider-using-f-string
                    cur.execute(
                        f"""
                        ALTER TABLE {schema_name}.queries
                        ADD COLUMN progress_message TEXT
                        """
                    )
                    conn.commit()

                    logger.info(f"Added progress_message column to {schema_name}.queries")

                except Exception as e:
                    logger.error(f"Failed to migrate schema {schema_name}: {e!s}", exc_info=True)
                    conn.rollback()
                    raise

    logger.info("Migration complete: progress_message column added successfully")


def main() -> None:
    """Run migration script."""
    try:
        # Get database URL from environment
        database_url: str = os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_csv_crew"
        )

        # Create connection pool
        pool: ConnectionPool = ConnectionPool(
            conninfo=database_url, min_size=1, max_size=2, timeout=30.0
        )

        # Run migration
        add_progress_message_column(pool)

        # Close pool
        pool.close()

        logger.info("Migration script completed successfully")

    except Exception as e:
        logger.error(f"Migration script failed: {e!s}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
