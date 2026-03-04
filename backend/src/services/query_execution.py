"""Query execution service with timeout and cancellation support.

Executes SQL queries against PostgreSQL with 30-second timeout and
cancellation capability per FR-025. Supports parallel multi-strategy
execution for 004-parallel-query-fusion.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from concurrent.futures import ALL_COMPLETED, Future, ThreadPoolExecutor, wait
from concurrent.futures import TimeoutError as FuturesTimeoutError
import re
from threading import Event
import time
from typing import Any

from psycopg import sql
from psycopg_pool import ConnectionPool

from backend.src.models.fusion import StrategyResult, StrategySQL, StrategyType
from backend.src.utils.logging import get_structured_logger

logger = get_structured_logger(__name__)

_VECTOR_PLACEHOLDER_RE: re.Pattern[str] = re.compile(r"%s::vector")


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

    # pylint: disable=too-many-locals
    # JUSTIFICATION: Parallel orchestration requires: futures dict, executor,
    # per-strategy iteration vars (strategy, future, future_ref), wait timeout,
    # grace_timeout, result construction. Splitting would fragment the
    # submit-wait-collect pipeline.
    def execute_strategies_parallel(
        self,
        strategies: list[StrategySQL],
        username: str,
        timeout_seconds: int = 30,
        cancel_event: Event | None = None,
    ) -> list[StrategyResult]:
        """Execute multiple strategy SQL queries in parallel.

        Each strategy is executed in its own thread with its own
        database connection. Per-strategy timeout enforced via
        concurrent.futures.wait().

        Args:
            strategies: List of StrategySQL objects to execute.
            username: For schema isolation (SET search_path).
            timeout_seconds: Per-strategy timeout (NFR-002).
            cancel_event: Optional event for external cancellation.

        Returns:
            List of StrategyResult objects, one per input strategy.
            Order matches input strategies list.
        """
        if not strategies:
            return []

        max_workers: int = len(strategies)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[StrategyType, Future[StrategyResult]] = {}
            for strategy in strategies:
                future: Future[StrategyResult] = executor.submit(
                    self._execute_single_strategy,
                    strategy=strategy,
                    username=username,
                    timeout_seconds=timeout_seconds,
                    cancel_event=cancel_event,
                )
                futures[strategy.strategy_type] = future

            # Wait with grace period
            grace_timeout: int = timeout_seconds + 5
            wait(
                futures.values(),
                timeout=grace_timeout,
                return_when=ALL_COMPLETED,
            )

        results: list[StrategyResult] = []
        for strategy in strategies:
            future_ref: Future[StrategyResult] = futures[strategy.strategy_type]
            if future_ref.done() and not future_ref.cancelled():
                try:
                    result: StrategyResult = future_ref.result()
                    results.append(result)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    # JUSTIFICATION: Future.result() re-raises any exception from
                    # the worker thread; must catch all to build error StrategyResult.
                    results.append(
                        StrategyResult(
                            strategy_type=strategy.strategy_type,
                            error=str(exc),
                        )
                    )
            else:
                results.append(
                    StrategyResult(
                        strategy_type=strategy.strategy_type,
                        error="Strategy timed out",
                    )
                )

        return results

    # pylint: enable=too-many-locals

    # pylint: disable=too-many-locals
    # JUSTIFICATION: Single-strategy execution requires: SQL prep (query_sql,
    # params, resolved vectors), DB ops (conn, cur, set_path_sql), result
    # extraction (rows, columns, result_rows, row_count), timing (start_time,
    # elapsed_ms), and error handling. Splitting would fragment the linear flow.
    def _execute_single_strategy(
        self,
        strategy: StrategySQL,
        username: str,
        timeout_seconds: int,
        cancel_event: Event | None,
    ) -> StrategyResult:
        """Execute a single strategy's SQL with timeout and cancellation.

        Args:
            strategy: StrategySQL to execute.
            username: For schema isolation.
            timeout_seconds: Execution timeout (sets statement_timeout).
            cancel_event: Optional cancellation event.

        Returns:
            StrategyResult with rows/error populated.
        """
        start_time: float = time.monotonic()
        # Convert to milliseconds for PostgreSQL statement_timeout
        timeout_ms: int = timeout_seconds * 1000

        try:
            # Check cancellation before starting
            if cancel_event and cancel_event.is_set():
                return StrategyResult(
                    strategy_type=strategy.strategy_type,
                    error="Cancelled before execution",
                )

            query_sql: str = strategy.sql
            params: list[Any] = list(strategy.parameters)

            # Resolve vector parameters if needed
            if _VECTOR_PLACEHOLDER_RE.search(query_sql):
                from backend.src.services.vector_search import (  # pylint: disable=import-outside-toplevel
                    VectorSearchService,
                )
                # JUSTIFICATION: VectorSearchService depends on external
                # API keys; importing at module level causes errors in
                # test environments without API keys configured.

                vs_service: VectorSearchService = VectorSearchService()
                # Extract query text from first param if available
                query_text: str = str(params[0]).strip("%") if params else ""
                embedding: list[float] = vs_service.generate_embedding(query_text)
                # Replace %s::vector with %s
                vector_count: int = len(_VECTOR_PLACEHOLDER_RE.findall(query_sql))
                query_sql = _VECTOR_PLACEHOLDER_RE.sub("%s", query_sql)
                # Replace string params with embeddings for vector slots
                vector_params: list[list[float]] = [embedding] * vector_count
                params = vector_params

            # Escape literal % characters
            if "%" in query_sql:
                if not params:
                    query_sql = query_sql.replace("%", "%%")
                else:
                    query_sql = query_sql.replace("%", "%%").replace("%%s", "%s")

            # Execute SQL
            with self.pool.connection() as conn:
                user_schema: str = f"{username}_schema"
                with conn.cursor() as cur:
                    set_path_sql: sql.Composed = sql.SQL(
                        "SET search_path TO {schema}, public"
                    ).format(schema=sql.Identifier(user_schema))
                    cur.execute(set_path_sql)
                    cur.execute(
                        "SET statement_timeout = %s",
                        (timeout_ms,),
                    )

                if cancel_event and cancel_event.is_set():
                    return StrategyResult(
                        strategy_type=strategy.strategy_type,
                        error="Cancelled before execution",
                    )

                with conn.cursor() as cur:
                    cur.execute(query_sql, params)
                    rows: list[tuple[Any, ...]] = cur.fetchall()
                    columns: list[str] = (
                        [desc[0] for desc in cur.description] if cur.description else []
                    )

                    result_rows: list[dict[str, Any]] = [
                        dict(zip(columns, row, strict=False)) for row in rows
                    ]

                    # Server-side row limit enforcement (FR-011)
                    row_limit: int = 50
                    if len(result_rows) > row_limit:
                        result_rows = result_rows[:row_limit]

                    row_count: int = len(result_rows)

            elapsed_ms: float = (time.monotonic() - start_time) * 1000.0

            return StrategyResult(
                strategy_type=strategy.strategy_type,
                rows=result_rows,
                columns=columns,
                row_count=row_count,
                execution_time_ms=elapsed_ms,
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            # JUSTIFICATION: Strategy execution catches all exceptions to return
            # StrategyResult with error rather than propagating to parent thread.
            # Database errors, cancellation, and vector resolution failures
            # are all converted to error results for graceful degradation (FR-012).
            elapsed_ms_err: float = (time.monotonic() - start_time) * 1000.0
            return StrategyResult(
                strategy_type=strategy.strategy_type,
                error=str(exc),
                execution_time_ms=elapsed_ms_err,
            )

    # pylint: enable=too-many-locals
