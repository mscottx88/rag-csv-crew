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
import threading
import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.src.api.dependencies import check_rate_limit
from backend.src.db.connection import get_global_pool
from backend.src.models.query import Query, QueryCreate, QueryHistory, QueryWithResponse
from backend.src.services.data_value_search import DataValueSearchService
from backend.src.services.hybrid_search import HybridSearchService
from backend.src.services.query_execution import QueryExecutionService
from backend.src.services.query_history import QueryHistoryService
from backend.src.services.response_generator import ResponseGenerator
from backend.src.services.result_fusion import ResultFusionService
from backend.src.services.strategy_dispatcher import StrategyDispatcherService
from backend.src.services.text_to_sql import TextToSQLService
from backend.src.utils.logging import log_event
from backend.src.utils.progress_tracker import ProgressTracker

# Configure logger
logger: logging.Logger = logging.getLogger(__name__)

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
    tracker: ProgressTracker,
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
        tracker: Progress timeline tracker
        username: Current username

    Returns:
        Query object with clarification response stored
    """
    tracker.update("Preparing clarification with top column matches...")

    clarification_response: dict[str, Any] = response_generator.generate_clarification_request(
        query_text=query_text, search_results=search_results
    )

    tracker.update("Formatting clarification response as HTML...")

    execution_time_ms: int = int((time.time() - start_time) * 1000)

    history_service.update_query_status(
        query_id,
        username,
        "completed",
        generated_sql=None,
        result_count=0,
        execution_time_ms=execution_time_ms,
        progress_message="Clarification request generated",
        progress_timeline=tracker.get_timeline_json(),
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


# pylint: disable=too-many-arguments,too-many-positional-arguments
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
    tracker: ProgressTracker,
    username: str,
) -> None:
    """Execute high-confidence SQL query and store response.

    Routes to multi-strategy or single-strategy path based on
    available indexes (FR-021). Multi-strategy uses parallel dispatch,
    RRF fusion, and attribution. Single-strategy preserves existing behavior.

    Args:
        query_id: Query UUID
        query_text: Original query text
        dataset_ids: Optional dataset UUIDs to query
        search_results: Column search results from hybrid search
        start_time: Query processing start timestamp
        pool: Database connection pool
        history_service: Query history service instance
        response_generator: Response generator instance
        tracker: Progress timeline tracker
        username: Current username
    """
    sql_service: TextToSQLService = TextToSQLService(pool)

    # Strategy dispatch: determine multi-strategy vs single-strategy (FR-021)
    dispatcher: StrategyDispatcherService = StrategyDispatcherService(pool)
    is_aggregation: bool = StrategyDispatcherService.detect_aggregation_intent(query_text)
    dispatch_plan: Any = dispatcher.plan_strategies(
        username=username,
        dataset_ids=dataset_ids,
        is_aggregation=is_aggregation,
    )

    log_event(
        logger,
        "info",
        "strategy_dispatch",
        None,
        {
            "query_id": str(query_id),
            "strategies": [s.value for s in dispatch_plan.strategies],
            "is_aggregation": is_aggregation,
            "strategy_count": len(dispatch_plan.strategies),
        },
    )

    # Single-strategy bypass (FR-021): len==1 → existing path
    if len(dispatch_plan.strategies) <= 1:
        _execute_single_strategy_path(
            query_id=query_id,
            query_text=query_text,
            dataset_ids=dataset_ids,
            search_results=search_results,
            start_time=start_time,
            pool=pool,
            sql_service=sql_service,
            history_service=history_service,
            response_generator=response_generator,
            tracker=tracker,
            username=username,
        )
        return

    # Multi-strategy path
    _execute_multi_strategy_path(
        query_id=query_id,
        query_text=query_text,
        dataset_ids=dataset_ids,
        search_results=search_results,
        start_time=start_time,
        pool=pool,
        sql_service=sql_service,
        dispatch_plan=dispatch_plan,
        history_service=history_service,
        response_generator=response_generator,
        tracker=tracker,
        username=username,
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
# JUSTIFICATION: Extracted from _execute_sql_query to separate single-strategy
# path. Needs same context (query data, services, user) plus sql_service.
# Locals inherited from original function for SQL gen, execution, and response.
def _execute_single_strategy_path(
    query_id: UUID,
    query_text: str,
    dataset_ids: list[UUID] | None,
    search_results: dict[str, Any],
    start_time: float,
    pool: Any,
    sql_service: TextToSQLService,
    *,
    history_service: QueryHistoryService,
    response_generator: ResponseGenerator,
    tracker: ProgressTracker,
    username: str,
) -> None:
    """Execute single-strategy SQL query (existing behavior).

    Args:
        query_id: Query UUID
        query_text: Original query text
        dataset_ids: Optional dataset UUIDs to query
        search_results: Column search results from hybrid search
        start_time: Query processing start timestamp
        pool: Database connection pool
        sql_service: Text-to-SQL service instance
        history_service: Query history service instance
        response_generator: Response generator instance
        tracker: Progress timeline tracker
        username: Current username
    """

    # Create progress callback for SQL generation
    def sql_generation_progress(message: str) -> None:
        """Progress callback for SQL generation service."""
        tracker.update(message)

    sql_result: dict[str, Any] = sql_service.generate_sql(
        query_text=query_text,
        dataset_ids=dataset_ids,
        username=username,
        search_results=search_results,
        use_schema_inspection=True,
        progress_callback=sql_generation_progress,
    )

    tracker.update("SQL query generated successfully, validating syntax...")

    tracker.update("Executing SQL query against database...")
    execution_service: QueryExecutionService = QueryExecutionService(pool)
    query_results: dict[str, Any] = execution_service.execute_query(
        query_sql=sql_result["sql"],
        params=sql_result["params"],
        username=username,
        timeout_seconds=300,
    )

    tracker.update(f"Query completed, processing {query_results['row_count']} rows...")

    tracker.update("Result Analyst Agent formatting results as HTML...")
    response_data: dict[str, Any] = response_generator.generate_html_response(
        query_text=query_text,
        query_results=query_results,
        _query_id=query_id,
    )

    execution_time_ms: int = int((time.time() - start_time) * 1000)

    history_service.update_query_status(
        query_id,
        username,
        "completed",
        generated_sql=sql_result["sql"],
        query_params=sql_result["params"],
        result_count=query_results["row_count"],
        execution_time_ms=execution_time_ms,
        progress_message="Completed successfully",
        agent_logs=sql_result.get("agent_logs"),
        progress_timeline=tracker.get_timeline_json(),
    )

    history_service.store_response(
        query_id=query_id,
        username=username,
        html_content=response_data["html_content"],
        plain_text=response_data["plain_text"],
        confidence_score=response_data.get("confidence_score"),
    )


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
# JUSTIFICATION: Multi-strategy orchestration requires: dispatch plan,
# SQL generation, parallel execution, fusion, and response assembly.
# Each step needs its own context variables. Splitting would fragment
# the pipeline without reducing complexity.
def _execute_multi_strategy_path(
    query_id: UUID,
    query_text: str,
    dataset_ids: list[UUID] | None,
    search_results: dict[str, Any],
    start_time: float,
    pool: Any,
    sql_service: TextToSQLService,
    dispatch_plan: Any,
    *,
    history_service: QueryHistoryService,
    response_generator: ResponseGenerator,
    tracker: ProgressTracker,
    username: str,
) -> None:
    """Execute multi-strategy query pipeline.

    Pipeline: dispatch → SQL generation → parallel execution →
    RRF fusion → HTML response with attribution.

    Args:
        query_id: Query UUID
        query_text: Original query text
        dataset_ids: Optional dataset UUIDs to query
        search_results: Column search results from hybrid search
        start_time: Query processing start timestamp
        pool: Database connection pool
        sql_service: Text-to-SQL service instance
        dispatch_plan: StrategyDispatchPlan from dispatcher
        history_service: Query history service instance
        response_generator: Response generator instance
        tracker: Progress timeline tracker
        username: Current username
    """
    strategy_count: int = len(dispatch_plan.strategies)

    # Step 1: Generate multi-strategy SQL (FR-023)
    tracker.update("Generating multi-strategy SQL...")

    def sql_progress(message: str) -> None:
        """Progress callback for multi-strategy SQL generation."""
        tracker.update(message)

    strategy_sqls: list[Any]
    agent_logs: str
    strategy_sqls, agent_logs = sql_service.generate_multi_strategy_sql(
        query_text=query_text,
        username=username,
        dataset_ids=dataset_ids,
        search_results=search_results,
        strategy_dispatch=dispatch_plan,
        progress_callback=sql_progress,
    )

    # Build combined SQL string for storage (FR-022)
    combined_sql: str = "\n\n".join(
        f"-- Strategy: {s.strategy_type.value}\n{s.sql}" for s in strategy_sqls
    )

    # Step 2: Parallel execution (FR-023)
    tracker.update(f"Executing {strategy_count} strategies in parallel...")
    execution_service: QueryExecutionService = QueryExecutionService(pool)
    strategy_results: list[Any] = execution_service.execute_strategies_parallel(
        strategies=strategy_sqls,
        username=username,
        timeout_seconds=30,
    )

    log_event(
        logger,
        "info",
        "strategy_execution_complete",
        None,
        {
            "query_id": str(query_id),
            "results": [
                {
                    "strategy": r.strategy_type.value,
                    "row_count": r.row_count,
                    "error": r.error,
                    "execution_time_ms": r.execution_time_ms,
                }
                for r in strategy_results
            ],
        },
    )

    # Step 3: Fuse results (FR-023)
    tracker.update(f"Fusing results from {strategy_count} strategies...")
    fusion_service: ResultFusionService = ResultFusionService()
    fused_result: Any = fusion_service.fuse(strategy_results)

    log_event(
        logger,
        "info",
        "fusion_complete",
        None,
        {
            "query_id": str(query_id),
            "total_rows": fused_result.total_row_count,
            "strategy_count": fused_result.strategy_count,
            "is_multi_strategy": fused_result.is_multi_strategy,
        },
    )

    # Build query_results dict for response generator
    query_results: dict[str, Any] = {
        "rows": [row.data for row in fused_result.rows],
        "columns": fused_result.columns,
        "row_count": fused_result.total_row_count,
    }

    # Step 4: Generate response (FR-023)
    tracker.update("Generating response...")
    response_data: dict[str, Any] = response_generator.generate_html_response(
        query_text=query_text,
        query_results=query_results,
        _query_id=query_id,
        fused_result=fused_result,
    )

    execution_time_ms: int = int((time.time() - start_time) * 1000)

    history_service.update_query_status(
        query_id,
        username,
        "completed",
        generated_sql=combined_sql,
        result_count=fused_result.total_row_count,
        execution_time_ms=execution_time_ms,
        progress_message="Completed successfully",
        agent_logs=agent_logs,
        progress_timeline=tracker.get_timeline_json(),
    )

    history_service.store_response(
        query_id=query_id,
        username=username,
        html_content=response_data["html_content"],
        plain_text=response_data["plain_text"],
        confidence_score=response_data.get("confidence_score"),
    )


def _process_query_background(  # pylint: disable=too-many-locals
    query_id: UUID,
    query_text: str,
    dataset_ids: list[UUID] | None,
    username: str,
) -> None:
    """Background worker to process query asynchronously.

    This function runs in a background thread to allow immediate API response
    while processing continues. Updates query status and progress in database.

    Args:
        query_id: Query UUID
        query_text: Natural language query text
        dataset_ids: Optional list of dataset UUIDs to query
        username: Username for schema context

    Constitutional Compliance:
        - Thread-based processing (function runs in Thread, not async)
        - All variables have explicit type annotations
        - All services use synchronous operations
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)
    tracker: ProgressTracker | None = None

    try:
        start_time: float = time.time()
        tracker = ProgressTracker(
            history_service=history_service,
            query_id=query_id,
            username=username,
            start_time=start_time,
        )

        # Update to processing status
        history_service.update_query_status(
            query_id, username, "processing", progress_message="Starting query processing..."
        )
        tracker.update("Starting query processing...")

        # Check if this is a metadata query (asking for available datasets/tables/columns)
        tracker.update("Analyzing query type...")
        sql_service: TextToSQLService = TextToSQLService(pool)
        if sql_service.is_metadata_query(query_text):
            # Retrieve and format metadata
            metadata: dict[str, Any] = sql_service.get_available_metadata(username)
            html_content: str = sql_service.format_metadata_as_html(metadata)
            plain_text: str = f"Found {metadata['total_datasets']} dataset(s)"

            execution_time_ms: int = int((time.time() - start_time) * 1000)

            tracker.update("Metadata retrieved")

            # Store metadata response
            history_service.update_query_status(
                query_id,
                username,
                "completed",
                generated_sql=None,
                result_count=metadata["total_datasets"],
                execution_time_ms=execution_time_ms,
                progress_message="Metadata retrieved",
                progress_timeline=tracker.get_timeline_json(),
            )

            history_service.store_response(
                query_id=query_id,
                username=username,
                html_content=html_content,
                plain_text=plain_text,
                confidence_score=1.0,  # Metadata queries always have 100% confidence
            )
            return

        # Run hybrid search to find relevant columns (semantic + keyword + exact match)
        # Get dataset/table names for progress reporting
        table_context: str = "all tables"
        if dataset_ids and len(dataset_ids) > 0:
            sql_service_temp: TextToSQLService = TextToSQLService(pool)
            schema_ctx: dict[str, Any] = sql_service_temp.get_schema_context(username, dataset_ids)
            tables_list: list[str] = schema_ctx.get("tables", [])
            if tables_list:
                if len(tables_list) <= 3:
                    table_context = f"tables: {', '.join(tables_list)}"
                else:
                    table_context = (
                        f"tables: {', '.join(tables_list[:3])} and {len(tables_list) - 3} more"
                    )

        tracker.update(f"Starting hybrid search across {table_context}...")
        hybrid_service: HybridSearchService = HybridSearchService(pool)
        # Convert UUID list to string list for hybrid search
        dataset_ids_str: list[str] | None = (
            [str(uuid) for uuid in dataset_ids] if dataset_ids is not None else None
        )

        # Create progress callback for hybrid search
        def hybrid_search_progress(message: str) -> None:
            """Progress callback for hybrid search service."""
            tracker.update(message)

        search_results: dict[str, Any] = hybrid_service.search(
            username=username,
            query_text=query_text,
            dataset_ids=dataset_ids_str,
            limit=10,
            progress_callback=hybrid_search_progress,
        )

        tracker.update(
            f"Hybrid search complete, found {len(search_results.get('fused_results', []))} matches"
        )

        # Calculate initial confidence score
        tracker.update("Analyzing search results and calculating confidence score...")
        response_generator: ResponseGenerator = ResponseGenerator()
        confidence_score: float = response_generator.calculate_confidence_score(search_results)

        logger.info(
            f"Hybrid search complete. Query: '{query_text}', "
            f"Confidence: {confidence_score:.2f}, "
            f"Fused results: {len(search_results.get('fused_results', []))}"
        )

        # If confidence is very low (<0.4), try data value search
        fused_results: list[dict[str, Any]] = search_results.get("fused_results", [])
        if confidence_score < 0.4:
            logger.info(f"Low confidence ({confidence_score:.2f}). Attempting data value search...")
            tracker.update(
                f"Low confidence ({confidence_score:.1%}) - searching actual data values..."
            )

            tracker.update("Extracting keywords from query for data value search...")

            # Search for query terms in actual data values
            data_value_service: DataValueSearchService = DataValueSearchService(pool)

            # Use table_context from earlier (recompute if needed for clarity)
            scan_context: str = f"Scanning {table_context} for matching data values..."
            tracker.update(scan_context)

            value_matches: list[dict[str, Any]] = data_value_service.search_data_values(
                username=username,
                query_text=query_text,
                dataset_ids=dataset_ids_str,
                sample_size=100,
                min_match_threshold=1,
            )

            logger.info(f"Data value search returned {len(value_matches)} matches")

            tracker.update(f"Data value search complete, found {len(value_matches)} matches")

            # If data value matches found, boost confidence and merge results
            if len(value_matches) > 0:
                tracker.update("Merging data value matches with column search results...")

                logger.info("Merging data value matches into fused results")
                for value_match in value_matches:
                    boosted_score: float = value_match["score"] * 0.8
                    logger.info(
                        f"  Data value match: {value_match['column_name']} "
                        f"(raw score: {value_match['score']:.3f}, "
                        f"boosted: {boosted_score:.3f}, "
                        f"matches: {value_match['match_count']})"
                    )
                    fused_results.append(
                        {
                            "column_name": value_match["column_name"],
                            "dataset_id": value_match["dataset_id"],
                            "combined_score": boosted_score,
                            "source": "data_values",
                            "match_count": value_match["match_count"],
                            "sample_values": value_match["sample_values"],
                        }
                    )

                # Sort fused results by score (descending)
                fused_results.sort(key=lambda x: x.get("combined_score", 0.0), reverse=True)

                # Debug: Log top 5 results after sorting
                logger.info("After sorting, top 5 fused_results:")
                for i, result in enumerate(fused_results[:5]):
                    logger.info(
                        f"  {i+1}. {result.get('column_name', '?')} "
                        f"(score: {result.get('combined_score', 0.0):.3f}, "
                        f"source: {result.get('source', 'hybrid')})"
                    )

                # Update search results with merged and sorted data
                search_results["fused_results"] = fused_results
                search_results["data_value_results"] = value_matches

                tracker.update("Recalculating confidence with data value matches...")

                # Recalculate confidence with data value matches
                confidence_score = response_generator.calculate_confidence_score(search_results)

                tracker.update(
                    f"Confidence improved to {confidence_score:.1%}, proceeding with SQL generation"
                )

                logger.info(
                    f"Data value matches found with confidence {confidence_score:.2f}. "
                    "Proceeding with SQL generation to retrieve actual data."
                )

        # If low confidence AND no data value matches, return clarification
        has_data_value_matches: bool = "data_value_results" in search_results
        if (
            response_generator.is_low_confidence(confidence_score, threshold=0.6)
            and not has_data_value_matches
        ):
            tracker.update(
                f"Confidence too low ({confidence_score:.1%}), generating clarification request..."
            )

            _handle_clarification_response(
                query_id=query_id,
                query_text=query_text,
                search_results=search_results,
                confidence_score=confidence_score,
                start_time=start_time,
                history_service=history_service,
                response_generator=response_generator,
                tracker=tracker,
                username=username,
            )
            return

        # High confidence: proceed with SQL generation and execution
        tracker.update("Generating SQL query with Schema Inspector Agent...")
        _execute_sql_query(
            query_id=query_id,
            query_text=query_text,
            dataset_ids=dataset_ids,
            search_results=search_results,
            start_time=start_time,
            pool=pool,
            history_service=history_service,
            response_generator=response_generator,
            tracker=tracker,
            username=username,
        )

    except Exception as e:
        # Update query as failed
        logger.error(f"Query processing failed for {query_id}: {e!s}", exc_info=True)
        timeline_json: str | None = None
        if tracker is not None:
            tracker.update(f"Query failed: {e!s}")
            timeline_json = tracker.get_timeline_json()
        history_service.update_query_status(
            query_id,
            username,
            "failed",
            progress_timeline=timeline_json,
        )


@router.post("", response_model=Query, status_code=status.HTTP_201_CREATED)
def submit_query(
    response: Response,
    query_create: QueryCreate,
    current_username: Annotated[str, Depends(check_rate_limit)],
) -> Query:
    """Submit a natural language query for processing.

    Returns immediately with pending query while processing continues in background thread.
    Clients should poll GET /queries/{query_id} for status updates and results.

    Args:
        query_create: Query submission request
        current_username: Username from authenticated JWT token

    Returns:
        Query object with pending status

    Raises:
        HTTPException: 400 if validation fails

    Workflow:
    1. Store query in database with pending status
    2. Start background thread to process query
    3. Return immediately with pending query
    4. Background thread updates progress and completes query

    Background Processing (in _process_query_background):
    - Run hybrid search (exact match + full-text + semantic vector search)
    - Calculate confidence score based on search results
    - If low confidence (<0.6): Generate clarification request
    - If high confidence (>=0.6): Generate and execute SQL
    - Update query status to completed/failed

    Constitutional Compliance:
    - Synchronous handler (def, not async def)
    - Thread-based background processing (threading.Thread)
    - All database operations remain synchronous
    """
    pool: Any = get_global_pool()
    history_service: QueryHistoryService = QueryHistoryService(pool)

    # Store query as pending (persist dataset_ids for later retrieval)
    dataset_id_strs: list[str] | None = (
        [str(uid) for uid in query_create.dataset_ids] if query_create.dataset_ids else None
    )
    query_id: UUID = history_service.store_query(
        query_text=query_create.query_text,
        username=current_username,
        status="pending",
        dataset_ids=dataset_id_strs,
    )

    # Start background thread to process query
    # This allows immediate API response while processing continues
    worker_thread: threading.Thread = threading.Thread(
        target=_process_query_background,
        args=(query_id, query_create.query_text, query_create.dataset_ids, current_username),
        daemon=True,  # Thread will not prevent application shutdown
        name=f"query-worker-{query_id}",
    )
    worker_thread.start()

    logger.info(
        f"Query {query_id} submitted and background processing "
        f"started in thread {worker_thread.name}"
    )

    # Return pending query immediately for client to poll
    query_obj: dict[str, Any] = history_service.get_query_by_id(query_id, current_username)
    return Query(**query_obj)


@router.get("/examples", response_model=dict[str, Any])
def get_example_queries(
    response: Response,
    _current_username: Annotated[str, Depends(check_rate_limit)],
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


@router.get("/history", response_model=QueryHistory)
def get_query_history(
    response: Response,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    current_username: str = Depends(check_rate_limit),
) -> QueryHistory:
    """Get paginated query history for current user.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (1-100)
        status_filter: Optional status filter
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
        username=current_username, page=page, page_size=page_size, status=status_filter
    )

    return QueryHistory(**history)


@router.get("/{query_id}", response_model=QueryWithResponse)
def get_query(
    response: Response,
    query_id: UUID,
    current_username: Annotated[str, Depends(check_rate_limit)],
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


@router.post("/{query_id}/cancel", response_model=Query)
def cancel_query(
    response: Response,
    query_id: UUID,
    current_username: Annotated[str, Depends(check_rate_limit)],
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
