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

import logging
import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

# Configure logger
logger: logging.Logger = logging.getLogger(__name__)

from src.api.dependencies import get_current_user
from src.db.connection import get_global_pool
from src.models.query import Query, QueryCreate, QueryHistory, QueryWithResponse
from src.services.data_value_search import DataValueSearchService
from src.services.hybrid_search import HybridSearchService
from src.services.query_execution import QueryExecutionService
from src.services.query_history import QueryHistoryService
from src.services.response_generator import ResponseGenerator
from src.services.text_to_sql import TextToSQLService

router: APIRouter = APIRouter(prefix="/queries", tags=["Queries"])


# pylint: disable=too-many-arguments
# JUSTIFICATION: Orchestration function needs to pass context (query data, services, user)
# to maintain clean separation of concerns. Reducing arguments would require over-engineering
# (wrapper objects) or tight coupling (accessing global state).
def _handle_clarification_response(
    query_id: UUID,
    query_text: str,
    search_results: dict[str, Any],
    confidence_score: float,
    start_time: float,
    *,
    history_service: QueryHistoryService,
    response_generator: ResponseGenerator,
    username: str,
) -> Query:
    """Handle low-confidence query by generating and storing clarification response.

    Args:
        query_id: Query UUID
        query_text: Original query text
        search_results: Results from hybrid search
        confidence_score: Calculated confidence score
        start_time: Query processing start timestamp
        history_service: Query history service instance
        response_generator: Response generator instance
        username: Current username

    Returns:
        Query object with clarification response stored
    """
    clarification_response: dict[str, Any] = response_generator.generate_clarification_request(
        query_text=query_text, search_results=search_results
    )

    execution_time_ms: int = int((time.time() - start_time) * 1000)

    history_service.update_query_status(
        query_id,
        username,
        "completed",
        generated_sql=None,
        result_count=0,
        execution_time_ms=execution_time_ms,
    )

    history_service.store_response(
        query_id=query_id,
        username=username,
        html_content=clarification_response["html_content"],
        plain_text=clarification_response["plain_text"],
        confidence_score=confidence_score,
    )

    query_obj: dict[str, Any] = history_service.get_query_by_id(query_id, username)
    return Query(**query_obj)


# pylint: disable=too-many-arguments
# JUSTIFICATION: Orchestration function needs to pass context (query data, services, user)
# to maintain clean separation of concerns. Reducing arguments would require over-engineering
# (wrapper objects) or tight coupling (accessing global state).
def _execute_sql_query(
    query_id: UUID,
    query_text: str,
    dataset_ids: list[UUID] | None,
    search_results: dict[str, Any],
    start_time: float,
    pool: Any,
    *,
    history_service: QueryHistoryService,
    response_generator: ResponseGenerator,
    username: str,
) -> None:
    """Execute high-confidence SQL query and store response.

    Args:
        query_id: Query UUID
        query_text: Original query text
        dataset_ids: Optional dataset UUIDs to query
        search_results: Column search results from hybrid search
        start_time: Query processing start timestamp
        pool: Database connection pool
        history_service: Query history service instance
        response_generator: Response generator instance
        username: Current username
    """
    sql_service: TextToSQLService = TextToSQLService(pool)
    sql_result: dict[str, Any] = sql_service.generate_sql(
        query_text=query_text,
        dataset_ids=dataset_ids,
        username=username,
        search_results=search_results,
    )

    execution_service: QueryExecutionService = QueryExecutionService(pool)
    query_results: dict[str, Any] = execution_service.execute_query(
        sql=sql_result["sql"],
        params=sql_result["params"],
        username=username,
        timeout_seconds=30,
    )

    response_data: dict[str, Any] = response_generator.generate_html_response(
        query_text=query_text, query_results=query_results, _query_id=query_id
    )

    execution_time_ms: int = int((time.time() - start_time) * 1000)

    history_service.update_query_status(
        query_id,
        username,
        "completed",
        generated_sql=sql_result["sql"],
        result_count=query_results["row_count"],
        execution_time_ms=execution_time_ms,
    )

    history_service.store_response(
        query_id=query_id,
        username=username,
        html_content=response_data["html_content"],
        plain_text=response_data["plain_text"],
        confidence_score=response_data.get("confidence_score"),
    )


@router.post("", response_model=Query, status_code=status.HTTP_201_CREATED)
def submit_query(  # pylint: disable=too-many-locals
    query_create: QueryCreate, current_username: Annotated[str, Depends(get_current_user)]
) -> Query:
    """Submit a natural language query for processing.

    Args:
        query_create: Query submission request
        current_username: Username from authenticated JWT token

    Returns:
        Query object with pending status

    Raises:
        HTTPException: 400 if validation fails, 500 if processing fails

    Workflow:
    1. Store query in database with pending status
    2. Run hybrid search (exact match + full-text + semantic vector search)
    3. Calculate confidence score based on search results
    4. If low confidence (<0.6): Return clarification request with alternatives
    5. If high confidence (>=0.6): Generate SQL using CrewAI
    6. Execute SQL query
    7. Generate HTML response
    8. Update query status to completed
    9. Store response

    Constitutional Compliance:
    - Synchronous handler (def, not async def)
    - Thread-based processing (HybridSearchService uses ThreadPoolExecutor)
    - Confidence threshold: 0.6 per FR-038
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    # Store query as pending
    query_id: UUID = history_service.store_query(
        query_text=query_create.query_text, username=current_username, status="pending"
    )

    # Process query in synchronous manner
    # (In production, this would be done in background thread/worker)
    try:
        start_time: float = time.time()

        # Update to processing status
        history_service.update_query_status(query_id, current_username, "processing")

        # Check if this is a metadata query (asking for available datasets/tables/columns)
        sql_service: TextToSQLService = TextToSQLService(pool)
        if sql_service.is_metadata_query(query_create.query_text):
            # Retrieve and format metadata
            metadata: dict[str, Any] = sql_service.get_available_metadata(current_username)
            html_content: str = sql_service.format_metadata_as_html(metadata)
            plain_text: str = f"Found {metadata['total_datasets']} dataset(s)"

            execution_time_ms: int = int((time.time() - start_time) * 1000)

            # Store metadata response
            history_service.update_query_status(
                query_id,
                current_username,
                "completed",
                generated_sql=None,
                result_count=metadata["total_datasets"],
                execution_time_ms=execution_time_ms,
            )

            history_service.store_response(
                query_id=query_id,
                username=current_username,
                html_content=html_content,
                plain_text=plain_text,
                confidence_score=1.0,  # Metadata queries always have 100% confidence
            )

            metadata_query_obj: dict[str, Any] = history_service.get_query_by_id(
                query_id, current_username
            )
            return Query(**metadata_query_obj)

        # Run hybrid search to find relevant columns (semantic + keyword + exact match)
        hybrid_service: HybridSearchService = HybridSearchService(pool)
        # Convert UUID list to string list for hybrid search
        dataset_ids_str: list[str] | None = (
            [str(uuid) for uuid in query_create.dataset_ids]
            if query_create.dataset_ids is not None
            else None
        )
        search_results: dict[str, Any] = hybrid_service.search(
            username=current_username,
            query_text=query_create.query_text,
            dataset_ids=dataset_ids_str,
            limit=10,
        )

        # Calculate initial confidence score
        response_generator: ResponseGenerator = ResponseGenerator()
        confidence_score: float = response_generator.calculate_confidence_score(search_results)

        logger.info(
            f"Hybrid search complete. Query: '{query_create.query_text}', "
            f"Confidence: {confidence_score:.2f}, "
            f"Fused results: {len(search_results.get('fused_results', []))}"
        )

        # If confidence is very low (<0.4) and no column matches, try data value search
        fused_results: list[dict[str, Any]] = search_results.get("fused_results", [])
        if confidence_score < 0.4 and len(fused_results) == 0:
            logger.info(
                f"Low confidence ({confidence_score:.2f}) and no column matches. "
                "Attempting data value search..."
            )

            # Search for query terms in actual data values
            data_value_service: DataValueSearchService = DataValueSearchService(pool)
            value_matches: list[dict[str, Any]] = data_value_service.search_data_values(
                username=current_username,
                query_text=query_create.query_text,
                dataset_ids=dataset_ids_str,
                sample_size=100,
                min_match_threshold=1,
            )

            logger.info(f"Data value search returned {len(value_matches)} matches")

            # If data value matches found, boost confidence and merge results
            if len(value_matches) > 0:
                logger.info("Merging data value matches into fused results")
                # Convert value matches to column format for fused_results
                for value_match in value_matches:
                    fused_results.append(
                        {
                            "column_name": value_match["column_name"],
                            "dataset_id": value_match["dataset_id"],
                            # Boost score to indicate strong match
                            "combined_score": value_match["score"] * 0.8,
                            "source": "data_values",
                            "match_count": value_match["match_count"],
                            "sample_values": value_match["sample_values"],
                        }
                    )

                # Update search results with merged data
                search_results["fused_results"] = fused_results
                search_results["data_value_results"] = value_matches

                # Recalculate confidence with data value matches
                confidence_score = response_generator.calculate_confidence_score(search_results)

        # If low confidence, return clarification request instead of SQL execution
        if response_generator.is_low_confidence(confidence_score, threshold=0.6):
            return _handle_clarification_response(
                query_id=query_id,
                query_text=query_create.query_text,
                search_results=search_results,
                confidence_score=confidence_score,
                start_time=start_time,
                history_service=history_service,
                response_generator=response_generator,
                username=current_username,
            )

        # High confidence: proceed with SQL generation and execution
        _execute_sql_query(
            query_id=query_id,
            query_text=query_create.query_text,
            dataset_ids=query_create.dataset_ids,
            search_results=search_results,
            start_time=start_time,
            pool=pool,
            history_service=history_service,
            response_generator=response_generator,
            username=current_username,
        )

    except Exception as e:
        # Update query as failed
        history_service.update_query_status(query_id, current_username, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {e!s}",
        ) from e

    # Return query object (type annotation required by constitution, even though mypy
    # sees this as redefinition from clarification branch - both paths don't execute together)
    query_obj: dict[str, Any] = history_service.get_query_by_id(query_id, current_username)
    return Query(**query_obj)


@router.get("/examples", response_model=dict[str, Any])
def get_example_queries(
    _current_username: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get example queries to help users understand capabilities.

    Returns:
        Dictionary with examples array

    Examples per FR-017:
    - Generic questions that work with any dataset
    - Categorized by complexity (basic, aggregation, filtering, cross_dataset)

    Note: _current_username parameter is required for authentication but not used in function body.
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


@router.get("/{query_id}", response_model=QueryWithResponse)
def get_query(
    query_id: UUID, current_username: Annotated[str, Depends(get_current_user)]
) -> QueryWithResponse:
    """Get query status and result by ID.

    Args:
        query_id: Query UUID
        current_username: Username from authenticated JWT token

    Returns:
        QueryWithResponse object with embedded response if available

    Raises:
        HTTPException: 404 if query not found
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    try:
        query_with_response: dict[str, Any] = history_service.get_query_with_response(
            query_id, current_username
        )
        return QueryWithResponse(**query_with_response)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Query {query_id} not found"
        ) from exc


@router.get("/history", response_model=QueryHistory)
def get_query_history(
    page: int = 1,
    page_size: int = 50,
    query_status: str | None = None,
    current_username: str = Depends(get_current_user),
) -> QueryHistory:
    """Get paginated query history for current user.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (1-100)
        query_status: Optional status filter
        current_username: Username from authenticated JWT token

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
        username=current_username, page=page, page_size=page_size, status=query_status
    )

    return QueryHistory(**history)


@router.post("/{query_id}/cancel", response_model=Query)
def cancel_query(
    query_id: UUID, current_username: Annotated[str, Depends(get_current_user)]
) -> Query:
    """Cancel a running query.

    Args:
        query_id: Query UUID
        current_username: Username from authenticated JWT token

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
        query_obj: dict[str, Any] = history_service.get_query_by_id(query_id, current_username)

        # Check if query can be cancelled
        if query_obj["status"] in {"completed", "failed", "cancelled", "timeout"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel query with status: {query_obj['status']}",
            )

        # Update status to cancelled
        history_service.update_query_status(query_id, current_username, "cancelled")

        # Return updated query
        updated_query: dict[str, Any] = history_service.get_query_by_id(query_id, current_username)
        return Query(**updated_query)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Query {query_id} not found"
        ) from exc
