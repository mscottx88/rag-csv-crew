"""Query execution service with timeout and cancellation support.

Executes SQL queries against PostgreSQL with 30-second timeout and
cancellation capability per FR-025.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Event
from typing import Any

from psycopg import sql
from psycopg_pool import ConnectionPool


class QueryExecutionService:
    """Service for executing SQL queries with timeout and cancellation."""

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize query execution service.

        Args:
            pool: Database connection pool
        """
        self.pool: ConnectionPool = pool

    def execute_query(  # pylint: disable=too-many-positional-arguments
        # TODO(pylint-refactor): Refactor to use config object or keyword-only args
        self,
        query_sql: str,
        params: list[Any],
        username: str,
        timeout_seconds: int = 30,
        cancel_event: Event | None = None,
    ) -> dict[str, Any]:
        """Execute SQL query with timeout and cancellation support.

        Args:
            query_sql: SQL query string with %s placeholders
            params: Query parameters for placeholders
            username: Username for schema context
            timeout_seconds: Maximum execution time (default: 30s per FR-025)
            cancel_event: Optional event to signal cancellation

        Returns:
            Dictionary with rows, row_count, and columns

        Raises:
            TimeoutError: If query exceeds timeout_seconds
            Exception: If query execution fails or is cancelled

        Constitutional Compliance:
        - Thread-based execution (ThreadPoolExecutor)
        - Cancellation via Event (not async)

        Note:
            Handles literal % characters in SQL (e.g., date format strings like %A,
            LIKE patterns) by escaping them appropriately. When parameters are empty,
            all % are escaped. When parameters exist, only non-placeholder % are escaped.
        """

        # Escape literal % characters for psycopg parameter style
        # psycopg uses % as placeholder prefix, so literal % must be escaped as %%
        if "%" in query_sql:
            if not params:
                # No parameters: all % are literal, escape them all
                query_sql = query_sql.replace("%", "%%")
            else:
                # Has parameters: escape % that are not part of %s placeholders
                # Replace all % first, then restore %s placeholders
                query_sql = query_sql.replace("%", "%%").replace("%%s", "%s")

        def run_query() -> dict[str, Any]:
            """Execute query in thread with cancellation check."""
            with self.pool.connection() as conn:
                # Set search path to user schema using Identifier for SQL injection protection
                user_schema: str = f"{username}_schema"
                with conn.cursor() as cur:
                    set_path_sql: sql.Composed = sql.SQL(
                        "SET search_path TO {schema}, public"
                    ).format(schema=sql.Identifier(user_schema))
                    cur.execute(set_path_sql)

                # Check cancellation before execution
                if cancel_event and cancel_event.is_set():
                    # TODO(pylint-refactor): Create QueryCancelledException class
                    raise Exception("Query cancelled before execution")  # pylint: disable=broad-exception-raised

                # Execute query
                with conn.cursor() as cur:
                    cur.execute(query_sql, params)

                    # Check cancellation after execution starts
                    if cancel_event and cancel_event.is_set():
                        # Cancel the running query
                        conn.cancel()
                        # TODO(pylint-refactor): Create QueryCancelledException class
                        raise Exception("Query cancelled during execution")  # pylint: disable=broad-exception-raised

                    # Fetch results
                    rows: list[tuple[Any, ...]] = cur.fetchall()
                    columns: list[str] = (
                        [desc[0] for desc in cur.description] if cur.description else []
                    )

                    # Convert rows to list of dicts
                    result_rows: list[dict[str, Any]] = [
                        dict(zip(columns, row, strict=False)) for row in rows
                    ]

                    return {"rows": result_rows, "row_count": len(result_rows), "columns": columns}

        # Execute query in thread pool with timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future: Any = executor.submit(run_query)

            try:
                result: dict[str, Any] = future.result(timeout=timeout_seconds)
                return result
            except FuturesTimeoutError as exc:
                # Cancel the query on timeout
                if cancel_event:
                    cancel_event.set()
                # TODO(pylint-refactor): Create QueryTimeoutException class
                raise Exception(f"Query exceeded {timeout_seconds} second timeout") from exc  # pylint: disable=broad-exception-raised
            except Exception as e:
                raise e
