"""PostgreSQL connection pool management.

This module provides synchronous connection pooling using psycopg3
per Constitution Principle VI (thread-based concurrency only).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import logging
from typing import TYPE_CHECKING

from psycopg import Connection
from psycopg.pool import ConnectionPool  # type: ignore[import-not-found]
from psycopg.rows import dict_row

if TYPE_CHECKING:
    from ..models.config import DatabaseConfig

logger: logging.Logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Manages PostgreSQL connection pool with thread-safe access.

    Uses psycopg3 synchronous ConnectionPool for thread-based concurrency.
    Provides context managers for safe connection acquisition and release.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        """Initialize connection pool with configuration.

        Args:
            config: Database configuration with connection parameters
        """
        self.config: DatabaseConfig = config
        self._pool: ConnectionPool | None = None
        logger.info(
            "Initializing database connection pool",
            extra={
                "host": config.host,
                "port": config.port,
                "database": config.database,
                "pool_min_size": config.pool_min_size,
                "pool_max_size": config.pool_max_size,
            },
        )

    def initialize(self) -> None:
        """Create and open the connection pool.

        Must be called before using the pool. Thread-safe.
        """
        if self._pool is not None:
            logger.warning("Connection pool already initialized")
            return

        conninfo: str = (
            f"host={self.config.host} "
            f"port={self.config.port} "
            f"dbname={self.config.database} "
            f"user={self.config.user} "
            f"password={self.config.password} "
            f"options='-c statement_timeout={self.config.statement_timeout}'"
        )

        self._pool = ConnectionPool(
            conninfo=conninfo,
            min_size=self.config.pool_min_size,
            max_size=self.config.pool_max_size,
            open=True,
        )

        logger.info("Database connection pool initialized successfully")

    def close(self) -> None:
        """Close the connection pool and release all connections.

        Should be called during application shutdown. Thread-safe.
        """
        if self._pool is None:
            logger.warning("Connection pool not initialized, nothing to close")
            return

        self._pool.close()
        self._pool = None
        logger.info("Database connection pool closed")

    @contextmanager
    def connection(self, autocommit: bool = False) -> Generator[Connection]:
        """Acquire a connection from the pool.

        Usage:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users")
                    results = cur.fetchall()

        Args:
            autocommit: If True, enable autocommit mode

        Yields:
            Connection object from the pool

        Raises:
            RuntimeError: If pool not initialized
        """
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized. Call initialize() first.")

        conn: Connection
        with self._pool.connection() as conn:
            if autocommit:
                conn.autocommit = True
            try:
                yield conn
            finally:
                if not autocommit and not conn.closed and conn.info.transaction_status == 2:
                    # Ensure transaction is either committed or rolled back (INTRANS)
                    conn.rollback()

    @contextmanager
    def cursor(
        self,
        row_factory: type = dict_row,  # type: ignore[assignment]
    ) -> Generator[Connection.cursor]:  # type: ignore[valid-type]
        """Acquire a connection and cursor from the pool.

        Convenience method that combines connection + cursor acquisition.

        Usage:
            with pool.cursor() as cur:
                cur.execute("SELECT * FROM users")
                results = cur.fetchall()  # Returns list of dicts

        Args:
            row_factory: Row factory for cursor (default: dict_row)

        Yields:
            Cursor object with dict_row factory

        Raises:
            RuntimeError: If pool not initialized
        """
        with self.connection() as conn, conn.cursor(row_factory=row_factory) as cur:
            yield cur

    def health_check(self) -> bool:
        """Check if database connection is healthy.

        Executes a simple query to verify connectivity.

        Returns:
            True if connection is healthy, False otherwise
        """
        if self._pool is None:
            logger.error("Health check failed: pool not initialized")
            return False

        try:
            with self.cursor() as cur:
                cur.execute("SELECT 1 AS health")
                result: dict[str, int] | None = cur.fetchone()
                if result and result.get("health") == 1:
                    logger.debug("Database health check passed")
                    return True
                logger.error("Health check failed: unexpected result")
                return False
        except Exception as e:
            logger.error(
                "Database health check failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return False

    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized.

        Returns:
            True if pool is initialized and open
        """
        return self._pool is not None and not self._pool.closed


# Global pool instance (initialized during application startup)
_global_pool: DatabaseConnectionPool | None = None


def initialize_global_pool(config: DatabaseConfig) -> None:
    """Initialize the global connection pool.

    Should be called once during application startup.

    Args:
        config: Database configuration
    """
    global _global_pool  # noqa: PLW0603
    if _global_pool is not None:
        logger.warning("Global pool already initialized")
        return

    _global_pool = DatabaseConnectionPool(config)
    _global_pool.initialize()
    logger.info("Global database connection pool initialized")


def get_global_pool() -> DatabaseConnectionPool:
    """Get the global connection pool instance.

    Returns:
        Global connection pool

    Raises:
        RuntimeError: If global pool not initialized
    """
    if _global_pool is None:
        raise RuntimeError(
            "Global connection pool not initialized. Call initialize_global_pool() first."
        )
    return _global_pool


def close_global_pool() -> None:
    """Close the global connection pool.

    Should be called during application shutdown.
    """
    global _global_pool  # noqa: PLW0603
    if _global_pool is None:
        logger.warning("Global pool not initialized, nothing to close")
        return

    _global_pool.close()
    _global_pool: DatabaseConnectionPool | None = None
    logger.info("Global database connection pool closed")
