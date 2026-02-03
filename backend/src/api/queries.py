"""Query API endpoints for natural language query processing.

Provides endpoints for submitting queries, checking status, viewing history,
and cancelling running queries per openapi.yaml.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
- Synchronous FastAPI handlers (def, not async def)
"""

import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.src.api.dependencies import get_current_user
from backend.src.db.connection import get_global_pool
from backend.src.models.query import Query, QueryCreate, QueryHistory, QueryWithResponse
from backend.src.models.user import User
from backend.src.services.query_execution import QueryExecutionService
from backend.src.services.query_history import QueryHistoryService
from backend.src.services.response_generator import ResponseGenerator
from backend.src.services.text_to_sql import TextToSQLService

router: APIRouter = APIRouter(prefix="/queries", tags=["Queries"])


@router.post("", response_model=Query, status_code=status.HTTP_201_CREATED)
def submit_query(
    query_create: QueryCreate, current_user: Annotated[User, Depends(get_current_user)]
) -> Query:
    """Submit a natural language query for processing.

    Args:
        query_create: Query submission request
        current_user: Authenticated user from JWT token

    Returns:
        Query object with pending status

    Raises:
        HTTPException: 400 if validation fails, 500 if processing fails

    Workflow:
    1. Store query in database with pending status
    2. Generate SQL using CrewAI
    3. Execute SQL query
    4. Generate HTML response
    5. Update query status to completed
    6. Store response

    Constitutional Compliance:
    - Synchronous handler (def, not async def)
    - Thread-based processing
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    # Store query as pending
    query_id: UUID = history_service.store_query(
        query_text=query_create.query_text, username=current_user.username, status="pending"
    )

    # Process query in synchronous manner
    # (In production, this would be done in background thread/worker)
    try:
        start_time: float = time.time()

        # Update to processing status
        history_service.update_query_status(query_id, current_user.username, "processing")

        # Generate SQL
        sql_service: TextToSQLService = TextToSQLService()
        sql_result: dict[str, Any] = sql_service.generate_sql(
            query_text=query_create.query_text,
            dataset_ids=query_create.dataset_ids,
            username=current_user.username,
        )

        # Execute SQL
        execution_service: QueryExecutionService = QueryExecutionService(pool)
        query_results: dict[str, Any] = execution_service.execute_query(
            sql=sql_result["sql"],
            params=sql_result["params"],
            username=current_user.username,
            timeout_seconds=30,
        )

        # Generate HTML response
        response_generator: ResponseGenerator = ResponseGenerator()
        response_data: dict[str, Any] = response_generator.generate_html_response(
            query_text=query_create.query_text, query_results=query_results, query_id=query_id
        )

        # Calculate execution time
        execution_time_ms: int = int((time.time() - start_time) * 1000)

        # Update query as completed
        history_service.update_query_status(
            query_id,
            current_user.username,
            "completed",
            generated_sql=sql_result["sql"],
            result_count=query_results["row_count"],
            execution_time_ms=execution_time_ms,
        )

        # Store response
        history_service.store_response(
            query_id=query_id,
            username=current_user.username,
            html_content=response_data["html_content"],
            plain_text=response_data["plain_text"],
            confidence_score=response_data.get("confidence_score"),
        )

    except Exception as e:
        # Update query as failed
        history_service.update_query_status(query_id, current_user.username, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {e!s}",
        )

    # Return query object
    query_obj: dict[str, Any] = history_service.get_query_by_id(query_id, current_user.username)
    return Query(**query_obj)


@router.get("/{query_id}", response_model=QueryWithResponse)
def get_query(
    query_id: UUID, current_user: Annotated[User, Depends(get_current_user)]
) -> QueryWithResponse:
    """Get query status and result by ID.

    Args:
        query_id: Query UUID
        current_user: Authenticated user from JWT token

    Returns:
        QueryWithResponse object with embedded response if available

    Raises:
        HTTPException: 404 if query not found
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    try:
        query_with_response: dict[str, Any] = history_service.get_query_with_response(
            query_id, current_user.username
        )
        return QueryWithResponse(**query_with_response)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Query {query_id} not found"
        )


@router.get("", response_model=QueryHistory)
def get_query_history(
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
) -> QueryHistory:
    """Get paginated query history for current user.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (1-100)
        status: Optional status filter
        current_user: Authenticated user from JWT token

    Returns:
        QueryHistory object with paginated queries

    Raises:
        HTTPException: 400 if pagination parameters invalid
    """
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page must be >= 1")

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Page size must be between 1 and 100"
        )

    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    history: dict[str, Any] = history_service.get_query_history(
        username=current_user.username, page=page, page_size=page_size, status=status
    )

    return QueryHistory(**history)


@router.post("/{query_id}/cancel", response_model=Query)
def cancel_query(query_id: UUID, current_user: Annotated[User, Depends(get_current_user)]) -> Query:
    """Cancel a running query.

    Args:
        query_id: Query UUID
        current_user: Authenticated user from JWT token

    Returns:
        Query object with cancelled status

    Raises:
        HTTPException: 404 if query not found, 400 if already completed

    Constitutional Compliance:
    - Cancellation completes within 1 second per SC-011
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    try:
        # Get current query
        query_obj: dict[str, Any] = history_service.get_query_by_id(query_id, current_user.username)

        # Check if query can be cancelled
        if query_obj["status"] in ["completed", "failed", "cancelled", "timeout"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel query with status: {query_obj['status']}",
            )

        # Update status to cancelled
        history_service.update_query_status(query_id, current_user.username, "cancelled")

        # Return updated query
        updated_query: dict[str, Any] = history_service.get_query_by_id(
            query_id, current_user.username
        )
        return Query(**updated_query)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Query {query_id} not found"
        )


@router.get("/examples", response_model=dict[str, Any])
def get_example_queries(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    """Get example queries to help users understand capabilities.

    Args:
        current_user: Authenticated user from JWT token

    Returns:
        Dictionary with examples array

    Examples per FR-017:
    - Generic questions that work with any dataset
    - Categorized by complexity (basic, aggregation, filtering, cross_dataset)
    """
    examples: list[dict[str, str]] = [
        {
            "question": "What are the top 10 rows?",
            "description": "Shows the first 10 rows of your data",
            "category": "basic",
        },
        {
            "question": "How many total records are there?",
            "description": "Counts all rows in the dataset",
            "category": "basic",
        },
        {
            "question": "What columns are available?",
            "description": "Lists all column names in the dataset",
            "category": "basic",
        },
        {
            "question": "What is the average value?",
            "description": "Calculates average for numeric columns",
            "category": "aggregation",
        },
        {
            "question": "Show me the highest values",
            "description": "Finds maximum values across columns",
            "category": "aggregation",
        },
        {
            "question": "Group the data by category",
            "description": "Groups and counts data by categorical columns",
            "category": "aggregation",
        },
        {
            "question": "Filter records where value is greater than 100",
            "description": "Applies filters to numeric columns",
            "category": "filtering",
        },
        {
            "question": "Show only recent records",
            "description": "Filters by date columns if available",
            "category": "filtering",
        },
        {
            "question": "Which categories have the most entries?",
            "description": "Finds most common values in categorical columns",
            "category": "filtering",
        },
        {
            "question": "Combine data from related files",
            "description": "Joins data across multiple uploaded datasets",
            "category": "cross_dataset",
        },
    ]

    return {"examples": examples}
