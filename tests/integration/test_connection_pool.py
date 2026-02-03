"""Integration tests for PostgreSQL connection pool.

Tests synchronous connection pooling with psycopg[pool] 3.x per FR-016.
Validates pool creation, connection acquisition, thread safety, and reuse.

Constitutional Requirements:
- Thread-based concurrency only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from psycopg_pool import ConnectionPool
import pytest


@pytest.mark.integration
class TestConnectionPool:
    """Test connection pool functionality with thread-based concurrency."""

    def test_pool_creation(self, db_config: dict[str, Any]) -> None:
        """Test connection pool creation with correct parameters.

        Validates:
        - Pool initializes with min_size and max_size
        - Pool timeout configuration
        - Pool can be opened and closed cleanly

        Args:
            db_config: Database configuration fixture
        """
        pool: ConnectionPool = ConnectionPool(
            conninfo=f"host={db_config['host']} port={db_config['port']} "
            f"dbname={db_config['database']} user={db_config['user']} "
            f"password={db_config['password']}",
            min_size=2,
            max_size=10,
            timeout=30.0,
        )

        try:
            pool.wait()  # Wait for pool to be ready
            assert pool.min_size == 2
            assert pool.max_size == 10
        finally:
            pool.close()

    def test_connection_acquisition(self, connection_pool: ConnectionPool) -> None:
        """Test acquiring and releasing connections from pool.

        Validates:
        - Connections can be acquired using context manager
        - Connections are automatically returned to pool
        - Pool statistics update correctly

        Args:
            connection_pool: Connection pool fixture
        """
        initial_size: int = connection_pool.get_stats()["pool_available"]

        with connection_pool.connection() as conn:
            # Connection should be acquired
            assert conn is not None
            current_size: int = connection_pool.get_stats()["pool_available"]
            assert current_size == initial_size - 1

        # Connection should be returned after context exit
        final_size: int = connection_pool.get_stats()["pool_available"]
        assert final_size == initial_size

    def test_thread_safety(self, connection_pool: ConnectionPool) -> None:
        """Test connection pool is thread-safe for concurrent access.

        Validates:
        - Multiple threads can acquire connections simultaneously
        - No connection conflicts or deadlocks
        - All connections properly returned to pool

        Args:
            connection_pool: Connection pool fixture
        """
        results: list[bool] = []
        errors: list[Exception] = []

        def acquire_and_query(thread_id: int) -> None:
            """Acquire connection and execute simple query.

            Args:
                thread_id: Thread identifier for tracking
            """
            try:
                with connection_pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1 as value")
                        row: tuple[int] | None = cur.fetchone()
                        assert row is not None
                        assert row[0] == 1
                        results.append(True)
            except Exception as e:
                errors.append(e)

        # Spawn 20 threads to stress test pool (max_size=10)
        num_threads: int = 20
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures: list[Any] = [executor.submit(acquire_and_query, i) for i in range(num_threads)]
            for future in futures:
                future.result()  # Wait for completion

        # All operations should succeed
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == num_threads

    def test_connection_reuse(self, connection_pool: ConnectionPool) -> None:
        """Test connections are reused from pool (not recreated).

        Validates:
        - Connection backend PIDs are reused
        - Pool avoids connection creation overhead

        Args:
            connection_pool: Connection pool fixture
        """
        pid1: int
        pid2: int

        with connection_pool.connection() as conn1:
            pid1 = conn1.info.backend_pid

        # After first connection released, acquire again
        with connection_pool.connection() as conn2:
            pid2 = conn2.info.backend_pid

        # Should reuse same backend connection
        assert pid1 == pid2

    def test_pool_exhaustion_timeout(self, connection_pool: ConnectionPool) -> None:
        """Test pool behavior when all connections are in use.

        Validates:
        - Requests wait for available connection (up to timeout)
        - Timeout raises appropriate exception

        Args:
            connection_pool: Connection pool fixture with small max_size
        """
        # Acquire max_size connections and hold them
        max_size: int = connection_pool.max_size
        connections: list[Any] = []

        try:
            for _ in range(max_size):
                conn: Any = connection_pool.getconn()
                connections.append(conn)

            # Pool exhausted - next acquisition should timeout
            with pytest.raises(Exception):  # PoolTimeout or similar
                connection_pool.getconn(timeout=1.0)
        finally:
            # Release all connections
            for conn in connections:
                connection_pool.putconn(conn)
