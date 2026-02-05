"""Query history storage service.

Manages persistence of queries and responses in PostgreSQL user schemas
per data-model.md.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg_pool import ConnectionPool


class QueryHistoryService:
    """Service for storing and retrieving query history."""

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize query history service.

        Args:
            pool: Database connection pool
        """
        self.pool: ConnectionPool = pool

    def store_query(self, query_text: str, username: str, status: str = "pending") -> UUID:
        """Store a new query in the database.

        Args:
            query_text: Natural language question
            username: Username for schema context
            status: Initial query status (default: "pending")

        Returns:
            UUID of the created query

        Table: {username}_schema.queries
        """
        query_id: UUID = uuid4()
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            cur.execute(
                """
                    INSERT INTO queries (id, query_text, status, submitted_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                (query_id, query_text, status, datetime.now(UTC)),
            )
            conn.commit()

        return query_id

    def update_query_status(  # pylint: disable=too-many-positional-arguments
        # TODO(pylint-refactor): Refactor to use QueryUpdate dataclass or keyword-only args
        self,
        query_id: UUID,
        username: str,
        status: str,
        generated_sql: str | None = None,
        result_count: int | None = None,
        execution_time_ms: int | None = None,
    ) -> None:
        """Update query status and optional fields.

        Args:
            query_id: Query UUID
            username: Username for schema context
            status: New status value
            generated_sql: Optional SQL that was generated
            result_count: Optional number of results
            execution_time_ms: Optional execution time in milliseconds
        """
        user_schema: str = f"{username}_schema"
        completed_at: datetime | None = datetime.now(UTC) if status == "completed" else None

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            cur.execute(
                """
                    UPDATE queries
                    SET status = %s,
                        completed_at = %s,
                        generated_sql = %s,
                        result_count = %s,
                        execution_time_ms = %s
                    WHERE id = %s
                    """,
                (
                    status,
                    completed_at,
                    generated_sql,
                    result_count,
                    execution_time_ms,
                    query_id,
                ),
            )
            conn.commit()

    def get_query_by_id(self, query_id: UUID, username: str) -> dict[str, Any]:
        """Retrieve query by ID.

        Args:
            query_id: Query UUID
            username: Username for schema context

        Returns:
            Dictionary with query fields

        Raises:
            Exception: If query not found
        """
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            cur.execute(
                """
                    SELECT id, query_text, submitted_at, completed_at, status,
                           generated_sql, result_count, execution_time_ms
                    FROM queries
                    WHERE id = %s
                    """,
                (query_id,),
            )
            row: tuple[Any, ...] | None = cur.fetchone()

            if not row:
                # TODO(pylint-refactor): Create QueryNotFoundException class
                raise Exception(f"Query {query_id} not found")  # pylint: disable=broad-exception-raised

            return {
                "id": row[0],
                "query_text": row[1],
                "submitted_at": row[2],
                "completed_at": row[3],
                "status": row[4],
                "generated_sql": row[5],
                "result_count": row[6],
                "execution_time_ms": row[7],
            }

    def store_response(  # pylint: disable=too-many-positional-arguments
        # TODO(pylint-refactor): Refactor to use ResponseData dataclass or keyword-only args
        self,
        query_id: UUID,
        username: str,
        html_content: str,
        plain_text: str,
        confidence_score: float | None = None,
    ) -> UUID:
        """Store a response for a query.

        Args:
            query_id: Query UUID
            username: Username for schema context
            html_content: HTML formatted response
            plain_text: Plain text version
            confidence_score: Optional confidence score (0.0-1.0)

        Returns:
            UUID of the created response

        Table: {username}_schema.responses
        """
        response_id: UUID = uuid4()
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            cur.execute(
                """
                    INSERT INTO responses (
                        id, query_id, html_content, plain_text, confidence_score, generated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                (
                    response_id,
                    query_id,
                    html_content,
                    plain_text,
                    confidence_score,
                    datetime.now(UTC),
                ),
            )
            conn.commit()

        return response_id

    def get_response_by_query_id(self, query_id: UUID, username: str) -> dict[str, Any]:
        """Retrieve response by query ID.

        Args:
            query_id: Query UUID
            username: Username for schema context

        Returns:
            Dictionary with response fields

        Raises:
            Exception: If response not found
        """
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            cur.execute(
                """
                    SELECT id, query_id, html_content, plain_text, confidence_score, generated_at
                    FROM responses
                    WHERE query_id = %s
                    """,
                (query_id,),
            )
            row: tuple[Any, ...] | None = cur.fetchone()

            if not row:
                # TODO(pylint-refactor): Create ResponseNotFoundException class
                raise Exception(f"Response for query {query_id} not found")  # pylint: disable=broad-exception-raised

            return {
                "id": row[0],
                "query_id": row[1],
                "html_content": row[2],
                "plain_text": row[3],
                "confidence_score": row[4],
                "generated_at": row[5],
            }

    def get_query_with_response(self, query_id: UUID, username: str) -> dict[str, Any]:
        """Retrieve query with embedded response (QueryWithResponse model).

        Args:
            query_id: Query UUID
            username: Username for schema context

        Returns:
            Dictionary with query and optional response
        """
        query: dict[str, Any] = self.get_query_by_id(query_id, username)

        # Try to get response (may not exist yet)
        try:
            response: dict[str, Any] = self.get_response_by_query_id(query_id, username)
            query["response"] = response
        except Exception:  # pylint: disable=broad-exception-caught
            # TODO(pylint-refactor): Catch specific exceptions (ResponseNotFoundException, DatabaseError)  # pylint: disable=line-too-long
            query["response"] = None

        return query

    def get_query_history(  # pylint: disable=too-many-locals
        # TODO(pylint-refactor): Extract helper methods to reduce local variables (e.g., build_query, fetch_results)  # pylint: disable=line-too-long
        self, username: str, page: int = 1, page_size: int = 50, status: str | None = None
    ) -> dict[str, Any]:
        """Retrieve paginated query history.

        Args:
            username: Username for schema context
            page: Page number (1-indexed)
            page_size: Number of items per page
            status: Optional status filter

        Returns:
            Dictionary with queries, total_count, page, page_size
        """
        user_schema: str = f"{username}_schema"
        offset: int = (page - 1) * page_size

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            # Build query with optional status filter
            where_clause: str = "WHERE status = %s" if status else ""
            params: tuple[Any, ...] = (status, page_size, offset) if status else (page_size, offset)

            # Get total count
            count_query: str = f"SELECT COUNT(*) FROM queries {where_clause}"
            cur.execute(count_query, (status,) if status else ())
            total_count: int = cur.fetchone()[0]  # type: ignore[index]

            # Get paginated queries
            query_sql: str = f"""
                    SELECT id, query_text, submitted_at, completed_at, status,
                           generated_sql, result_count, execution_time_ms
                    FROM queries
                    {where_clause}
                    ORDER BY submitted_at DESC
                    LIMIT %s OFFSET %s
                """
            cur.execute(query_sql, params)
            rows: list[tuple[Any, ...]] = cur.fetchall()

            queries: list[dict[str, Any]] = [
                {
                    "id": row[0],
                    "query_text": row[1],
                    "submitted_at": row[2],
                    "completed_at": row[3],
                    "status": row[4],
                    "generated_sql": row[5],
                    "result_count": row[6],
                    "execution_time_ms": row[7],
                }
                for row in rows
            ]

            return {
                "queries": queries,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
            }

    def delete_query(self, query_id: UUID, username: str) -> None:
        """Delete query (and cascade delete response).

        Args:
            query_id: Query UUID
            username: Username for schema context
        """
        user_schema: str = f"{username}_schema"

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {user_schema}, public")

            cur.execute("DELETE FROM queries WHERE id = %s", (query_id,))
            conn.commit()
