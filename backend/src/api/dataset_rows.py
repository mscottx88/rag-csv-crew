"""Dataset row retrieval endpoint for the Dataset Inspector.

Implements GET /datasets/{dataset_id}/rows for paginated row fetching
to power the frontend DataTable component.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- All route handlers use def (NOT async def)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from psycopg import sql

from backend.src.api.dependencies import check_rate_limit
from backend.src.api.utils import get_pool_with_error_handling
from backend.src.db.connection import DatabaseConnectionPool
from backend.src.models.dataset_rows import DatasetRowsResponse
from backend.src.services.ingestion import sanitize_column_name
from backend.src.utils.logging import get_structured_logger, log_event

# Initialize router and logger
router: APIRouter = APIRouter(prefix="/datasets", tags=["Datasets"])
logger = get_structured_logger(__name__)


def _serialize_cell(value: Any) -> Any:
    """Convert a database cell value to a JSON-safe type.

    Handles datetime, date, Decimal, UUID, and memoryview conversions
    so Pydantic can serialise the response to JSON.

    Args:
        value: Raw cell value from psycopg cursor

    Returns:
        JSON-serialisable value (str, int, float, bool, or None)
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        # Preserve integer-looking decimals as int
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, memoryview):
        return bytes(value).decode("utf-8", errors="replace")
    return value


@router.get(
    "/{dataset_id}/rows",
    response_model=DatasetRowsResponse,
    status_code=status.HTTP_200_OK,
)
def get_dataset_rows(
    response: Response,
    dataset_id: str,
    offset: int = 0,
    limit: int = 50,
    username: str = Depends(check_rate_limit),
) -> DatasetRowsResponse:
    """Retrieve paginated rows from a dataset table.

    Fetches actual data rows for display in the Dataset Inspector.
    Only user-facing columns are returned (metadata columns excluded).

    Args:
        response: FastAPI response object
        dataset_id: UUID of the dataset to inspect
        offset: Row offset for pagination (default 0)
        limit: Maximum rows to return (1-500, default 50)
        username: Current authenticated user (injected)

    Returns:
        DatasetRowsResponse with columns, rows, and pagination metadata

    Raises:
        HTTPException 400: Invalid offset or limit
        HTTPException 404: Dataset not found
        HTTPException 500: Server error during retrieval
    """
    log_event(
        logger=logger,
        level="info",
        event="dataset_rows_request",
        user=username,
        extra={"dataset_id": dataset_id, "offset": offset, "limit": limit},
    )

    # Validate pagination params
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offset must be >= 0",
        )
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 500",
        )

    pool: DatabaseConnectionPool = get_pool_with_error_handling(
        logger=logger, event_name="dataset_rows_failed", user=username
    )

    with pool.connection() as conn:
        try:
            # Look up dataset metadata
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT table_name, row_count, schema_json "
                    f"FROM {username}_schema.datasets "
                    f"WHERE id = %s",
                    (dataset_id,),
                )
                meta_row: tuple[Any, ...] | None = cur.fetchone()

            if meta_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dataset {dataset_id} not found",
                )

            table_name: str = meta_row[0]
            row_count: int = meta_row[1]
            schema_json_db: dict[str, Any] = meta_row[2]

            # Extract user-facing column names from schema_json
            # Sanitize names to match actual PostgreSQL columns (handles legacy data
            # where schema_json may contain original mixed-case CSV header names)
            columns_raw: list[dict[str, Any]] = schema_json_db.get("columns", [])
            column_names: list[str] = [
                sanitize_column_name(col["name"]) for col in columns_raw
            ]

            if not column_names:
                return DatasetRowsResponse(
                    dataset_id=dataset_id,
                    table_name=table_name,
                    columns=[],
                    rows=[],
                    total_row_count=row_count,
                    offset=offset,
                    limit=limit,
                    has_more=False,
                )

            # Build SELECT with safe identifiers
            col_identifiers: sql.Composed = sql.SQL(", ").join(
                sql.Identifier(name) for name in column_names
            )
            table_ident: sql.Identifier = sql.Identifier(table_name)
            schema_ident: sql.Identifier = sql.Identifier(f"{username}_schema")

            query: sql.Composed = sql.SQL(
                "SELECT {cols} FROM {schema}.{table} "
                "ORDER BY _row_id LIMIT %s OFFSET %s"
            ).format(
                cols=col_identifiers,
                schema=schema_ident,
                table=table_ident,
            )

            with conn.cursor() as cur:
                cur.execute(query, (limit, offset))
                raw_rows: list[tuple[Any, ...]] = cur.fetchall()

            # Serialize cell values for JSON
            rows: list[list[Any]] = [
                [_serialize_cell(cell) for cell in row]
                for row in raw_rows
            ]

            has_more: bool = offset + limit < row_count

            log_event(
                logger=logger,
                level="info",
                event="dataset_rows_success",
                user=username,
                extra={
                    "dataset_id": dataset_id,
                    "returned_rows": len(rows),
                    "offset": offset,
                    "has_more": has_more,
                },
            )

            return DatasetRowsResponse(
                dataset_id=dataset_id,
                table_name=table_name,
                columns=column_names,
                rows=rows,
                total_row_count=row_count,
                offset=offset,
                limit=limit,
                has_more=has_more,
            )

        except HTTPException:
            raise
        except Exception as exc:
            log_event(
                logger=logger,
                level="error",
                event="dataset_rows_failed",
                user=username,
                extra={"dataset_id": dataset_id, "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve dataset rows",
            ) from exc
