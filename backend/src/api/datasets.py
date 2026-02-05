"""Dataset management endpoints for CSV upload and listing.

Implements POST /datasets for CSV file upload per openapi.yaml.
Follows FR-013, FR-014, FR-015, FR-022.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- All route handlers use def (NOT async def)
"""
# pylint: disable=duplicate-code
# TODO(pylint-refactor): Exception handling patterns duplicated with auth.py
# Extract into shared utility function to eliminate code duplication

from io import BytesIO, StringIO
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg_pool import ConnectionPool

from src.api.dependencies import get_current_user
from src.api.utils import get_pool_with_error_handling
from src.db.connection import DatabaseConnectionPool
from src.models.dataset import ColumnSchema, Dataset, DatasetList
from src.services.ingestion import (  # pylint: disable=import-outside-toplevel
    check_filename_conflict,
    create_dataset_table,
    detect_csv_format,
    detect_csv_schema,
    generate_column_embeddings,
    ingest_csv_data,
    store_dataset_metadata,
)
from src.utils.logging import get_structured_logger, log_event

# Initialize router and logger
router: APIRouter = APIRouter(prefix="/datasets", tags=["Datasets"])
logger = get_structured_logger(__name__)

# Security scheme for Bearer token
bearer_scheme: HTTPBearer = HTTPBearer()


def get_current_username(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    """Extract username from JWT token.

    Args:
        credentials: HTTPAuthorizationCredentials from bearer_scheme

    Returns:
        Username from validated token

    Raises:
        HTTPException: 401 if token is invalid
    """
    username: str = get_current_user(credentials=credentials)
    return username


@router.post("/", response_model=Dataset, status_code=status.HTTP_201_CREATED)
# pylint: disable=too-complex  # TODO(T225): Refactor to reduce McCabe complexity
def upload_dataset(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    # TODO(pylint-refactor): Complex function - refactor into: file_validation, csv_processing, conflict_handling, metadata_storage  # pylint: disable=line-too-long
    file: UploadFile = File(...),
    username: str = Depends(get_current_username),
) -> Dataset | JSONResponse:
    """Upload CSV file and create dataset.

    Performs:
    1. File validation
    2. Format detection (delimiter, encoding)
    3. Schema inference (types, nullability)
    4. Filename conflict check
    5. Table creation
    6. Data ingestion via COPY
    7. Metadata storage

    Args:
        file: Uploaded CSV file
        username: Current authenticated user

    Returns:
        Dataset with metadata

    Raises:
        HTTPException 400: Invalid CSV format
        HTTPException 409: Filename conflict
        HTTPException 500: Server error during ingestion

    Per openapi.yaml POST /datasets:
    - Request: multipart/form-data with file field
    - Response 201: Dataset schema
    - Response 400: Invalid CSV
    - Response 409: Filename conflict
    """
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Extract filename (remove .csv extension if present)
    filename: str = file.filename
    if filename.lower().endswith(".csv"):
        filename_without_ext: str = filename[:-4]
    else:
        filename_without_ext = filename

    log_event(
        logger=logger,
        level="info",
        event="csv_upload_start",
        user=username,
        extra={"filename": filename},
    )

    # Read file content
    try:
        file_content: bytes = file.file.read()
        file_size: int = len(file_content)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file",
            )
    except Exception as e:
        log_event(
            logger=logger,
            level="error",
            event="file_read_failed",
            user=username,
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e!s}",
        ) from e

    # Get database connection
    pool: DatabaseConnectionPool = get_pool_with_error_handling(
        logger=logger, event_name="upload_failed", user=username
    )

    with pool.connection() as conn:
        # Check filename conflict
        try:
            conflict_info: dict[str, Any] = check_filename_conflict(
                conn, username, filename_without_ext
            )

            if conflict_info["conflict"]:
                log_event(
                    logger=logger,
                    level="warning",
                    event="filename_conflict",
                    user=username,
                    extra={"filename": filename_without_ext},
                )
                # Return FilenameConflictResponse per openapi.yaml
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content={
                        "error": "filename_conflict",
                        "message": f"Filename '{filename_without_ext}' already exists",
                        "existing_dataset_id": "00000000-0000-0000-0000-000000000000",  # Placeholder UUID  # pylint: disable=line-too-long
                        "suggested_filename": conflict_info["suggested_filename"],
                    },
                )
        except HTTPException:  # pylint: disable=duplicate-code
            # TODO(pylint-refactor): Extract common exception handling pattern into utility function
            raise
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="conflict_check_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check filename conflict",
            ) from e

        # Detect CSV format
        try:
            csv_file_bytes: BytesIO = BytesIO(file_content)
            format_info: dict[str, Any] = detect_csv_format(csv_file_bytes)
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="format_detection_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to detect CSV format: {e!s}",
            ) from e

        # Decode CSV for schema detection
        try:
            encoding: str = format_info["encoding"]
            csv_text: str = file_content.decode(encoding)

            # Strip BOM if present
            if csv_text.startswith("\ufeff"):
                csv_text = csv_text[1:]

            csv_file_string: StringIO = StringIO(csv_text)
        except (UnicodeDecodeError, LookupError) as e:
            log_event(
                logger=logger,
                level="error",
                event="encoding_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decode CSV: {e!s}",
            ) from e

        # Detect schema
        try:
            schema: dict[str, Any] = detect_csv_schema(csv_file_string)

            if not schema.get("columns"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CSV has no columns",
                )

            # Validate column names don't contain invalid characters
            for col in schema["columns"]:
                col_name: str = col["name"]
                if not col_name or not col_name.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CSV contains empty column names",
                    )
                # Check for null bytes or other problematic characters
                if "\x00" in col_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CSV contains invalid column names (null bytes)",
                    )

            column_count: int = len(schema["columns"])
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="schema_detection_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to detect CSV schema: {e!s}",
            ) from e

        # Create dataset table
        try:
            table_name: str = create_dataset_table(conn, username, filename_without_ext, schema)
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="table_creation_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create dataset table: {e!s}",
            ) from e

        # Normalize schema types to match ColumnSchema pattern
        # Valid types: text|integer|bigint|numeric|boolean|date|timestamp
        type_mapping: dict[str, str] = {
            "TEXT": "text",
            "INTEGER": "integer",
            "BIGINT": "bigint",
            "FLOAT": "numeric",  # Map FLOAT to numeric
            "DECIMAL": "numeric",
            "NUMERIC": "numeric",
            "BOOLEAN": "boolean",
            "DATE": "date",
            "TIMESTAMP": "timestamp",
        }

        normalized_columns: list[dict[str, Any]] = []
        for col in schema["columns"]:
            col_type_upper: str = col["type"].upper()
            normalized_type: str = type_mapping.get(col_type_upper, "text")  # Default to text

            normalized_col: dict[str, Any] = {
                "name": col["name"],
                "inferred_type": normalized_type,
                "nullable": col.get("nullable", False),
            }
            normalized_columns.append(normalized_col)

        # Store metadata first to get dataset_id
        try:
            metadata: dict[str, Any] = {
                "filename": filename_without_ext,
                "original_filename": filename,
                "table_name": table_name,
                "row_count": 0,  # Will update after ingestion
                "column_count": column_count,
                "file_size_bytes": file_size,
                "schema_json": {"columns": normalized_columns},  # Keep original structure for DB
            }

            dataset_id: str = store_dataset_metadata(conn, username, metadata)
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="metadata_storage_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store dataset metadata: {e!s}",
            ) from e

        # Ingest data
        try:
            csv_file_bytes.seek(0)
            row_count: int = ingest_csv_data(conn, username, table_name, csv_file_bytes, dataset_id)

            # Update row count in metadata
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {username}_schema.datasets SET row_count = %s WHERE id = %s",
                    (row_count, dataset_id),
                )
            conn.commit()
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="data_ingestion_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to ingest CSV data: {e!s}",
            ) from e

        # Generate embeddings for semantic search
        try:
            # Access underlying ConnectionPool from DatabaseConnectionPool wrapper
            underlying_pool: ConnectionPool | None = pool._pool  # pylint: disable=protected-access
            if underlying_pool is None:
                raise RuntimeError("Connection pool not initialized")
            generate_column_embeddings(
                pool=underlying_pool,
                username=username,
                dataset_id=dataset_id,
                columns=schema["columns"],
            )
            log_event(
                logger=logger,
                level="info",
                event="embeddings_generated",
                user=username,
                extra={"dataset_id": dataset_id, "column_count": column_count},
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            # JUSTIFICATION: Embedding generation is optional - we intentionally catch all
            # exceptions (API failures, network issues, database errors) to prevent blocking
            # CSV upload. Dataset will be functional without embeddings (no semantic search).
            log_event(
                logger=logger,
                level="warning",
                event="embedding_generation_failed",
                user=username,
                extra={"dataset_id": dataset_id, "error": str(e)},
            )
            # Don't fail the upload if embeddings fail - log and continue
            # Semantic search won't work for this dataset, but basic functionality will

        # Detect cross-references with existing datasets
        try:
            underlying_pool_for_xref: ConnectionPool | None = pool._pool  # pylint: disable=protected-access
            if underlying_pool_for_xref is None:
                raise RuntimeError("Connection pool not initialized")

            from src.services.ingestion import (  # pylint: disable=import-outside-toplevel
                IngestionService,
            )

            ingestion_service: IngestionService = IngestionService(underlying_pool_for_xref)
            ref_count: int = ingestion_service.detect_and_store_cross_references(
                username=username,
                new_dataset_id=dataset_id,
            )
            log_event(
                logger=logger,
                level="info",
                event="cross_references_detected",
                user=username,
                extra={"dataset_id": dataset_id, "reference_count": ref_count},
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            # JUSTIFICATION: Cross-reference detection is optional - we intentionally catch all
            # exceptions to prevent blocking CSV upload. Dataset will be functional without
            # cross-references (no automatic JOIN generation for multi-table queries).
            log_event(
                logger=logger,
                level="warning",
                event="cross_reference_detection_failed",
                user=username,
                extra={"dataset_id": dataset_id, "error": str(e)},
            )
            # Don't fail the upload if cross-reference detection fails

        # Fetch complete dataset record
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, filename, original_filename, table_name, uploaded_at,
                           row_count, column_count, file_size_bytes, schema_json
                    FROM {username}_schema.datasets
                    WHERE id = %s
                    """,
                    (dataset_id,),
                )
                row: tuple[Any, ...] | None = cur.fetchone()

                if row is None:
                    raise ValueError("Dataset not found after creation")

                # Extract columns list from schema_json (stored as {"columns": [...]})
                schema_json_db: dict[str, Any] = row[8]
                columns_list: list[ColumnSchema] = [
                    ColumnSchema(**col) for col in schema_json_db.get("columns", [])
                ]

                dataset: Dataset = Dataset(
                    id=row[0],
                    filename=row[1],
                    original_filename=row[2],
                    table_name=row[3],
                    uploaded_at=row[4],
                    row_count=row[5],
                    column_count=row[6],
                    file_size_bytes=row[7],
                    schema_json=columns_list,  # Pass list of ColumnSchema dicts
                )
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="dataset_fetch_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve dataset information",
            ) from e

        log_event(
            logger=logger,
            level="info",
            event="csv_upload_success",
            user=username,
            extra={
                "filename": filename,
                "dataset_id": dataset_id,
                "row_count": row_count,
            },
        )

        return dataset


@router.get("/", response_model=DatasetList, status_code=status.HTTP_200_OK)
def list_datasets(  # pylint: disable=too-many-locals
    # TODO(pylint-refactor): Extract SQL generation and result processing into helper methods
    page: int = 1,
    page_size: int = 50,
    username: str = Depends(get_current_username),
) -> DatasetList:
    """List datasets for authenticated user with pagination.

    Retrieves all datasets uploaded by the current user with
    pagination support per openapi.yaml GET /datasets.

    Args:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (1-100, default 50)
        username: Current authenticated user

    Returns:
        DatasetList with datasets array and pagination metadata

    Raises:
        HTTPException 500: Server error during retrieval

    Per openapi.yaml GET /datasets:
    - Response 200: DatasetList schema
    - Pagination via query params
    - Ordered by uploaded_at DESC
    """
    log_event(
        logger=logger,
        level="info",
        event="datasets_list_request",
        user=username,
        extra={"page": page, "page_size": page_size},
    )

    # Validate pagination params
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be >= 1",
        )
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be between 1 and 100",
        )

    pool: DatabaseConnectionPool = get_pool_with_error_handling(
        logger=logger, event_name="list_failed", user=username
    )

    with pool.connection() as conn:
        try:
            # Get total count
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {username}_schema.datasets",
                )
                total_result: tuple[int] | None = cur.fetchone()
                total_count: int = total_result[0] if total_result else 0

            # Calculate offset
            offset: int = (page - 1) * page_size

            # Fetch paginated datasets
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, filename, original_filename, table_name, uploaded_at,
                           row_count, column_count, file_size_bytes, schema_json
                    FROM {username}_schema.datasets
                    ORDER BY uploaded_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (page_size, offset),
                )
                rows: list[tuple[Any, ...]] = cur.fetchall()

            # Build Dataset objects
            datasets: list[Dataset] = []
            for row in rows:
                schema_json_db: dict[str, Any] = row[8]
                columns_list: list[ColumnSchema] = [
                    ColumnSchema(**col) for col in schema_json_db.get("columns", [])
                ]

                dataset: Dataset = Dataset(
                    id=row[0],
                    filename=row[1],
                    original_filename=row[2],
                    table_name=row[3],
                    uploaded_at=row[4],
                    row_count=row[5],
                    column_count=row[6],
                    file_size_bytes=row[7],
                    schema_json=columns_list,
                )
                datasets.append(dataset)

            log_event(
                logger=logger,
                level="info",
                event="datasets_list_success",
                user=username,
                extra={
                    "total_count": total_count,
                    "page": page,
                    "returned_count": len(datasets),
                },
            )

            return DatasetList(
                datasets=datasets,
                total_count=total_count,
                page=page,
                page_size=page_size,
            )

        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="datasets_list_failed",
                user=username,
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve datasets",
            ) from e


@router.get("/{dataset_id}", response_model=Dataset, status_code=status.HTTP_200_OK)
def get_dataset(
    dataset_id: str,
    username: str = Depends(get_current_username),
) -> Dataset:
    """Get single dataset by ID for authenticated user.

    Retrieves full metadata for a specific dataset including
    schema information per openapi.yaml GET /datasets/{dataset_id}.

    Args:
        dataset_id: UUID of the dataset
        username: Current authenticated user

    Returns:
        Dataset with all metadata fields

    Raises:
        HTTPException 404: Dataset not found or not owned by user
        HTTPException 500: Server error during retrieval

    Per openapi.yaml GET /datasets/{dataset_id}:
    - Response 200: Dataset schema
    - Response 404: Dataset not found
    """
    log_event(
        logger=logger,
        level="info",
        event="dataset_get_request",
        user=username,
        extra={"dataset_id": dataset_id},
    )

    pool: DatabaseConnectionPool = get_pool_with_error_handling(
        logger=logger, event_name="get_failed", user=username
    )

    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, filename, original_filename, table_name, uploaded_at,
                           row_count, column_count, file_size_bytes, schema_json
                    FROM {username}_schema.datasets
                    WHERE id = %s
                    """,
                    (dataset_id,),
                )
                row: tuple[Any, ...] | None = cur.fetchone()

                if row is None:
                    log_event(
                        logger=logger,
                        level="warning",
                        event="dataset_not_found",
                        user=username,
                        extra={"dataset_id": dataset_id},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Dataset {dataset_id} not found",
                    )

                # Extract columns from schema_json
                schema_json_db: dict[str, Any] = row[8]
                columns_list: list[ColumnSchema] = [
                    ColumnSchema(**col) for col in schema_json_db.get("columns", [])
                ]

                dataset: Dataset = Dataset(
                    id=row[0],
                    filename=row[1],
                    original_filename=row[2],
                    table_name=row[3],
                    uploaded_at=row[4],
                    row_count=row[5],
                    column_count=row[6],
                    file_size_bytes=row[7],
                    schema_json=columns_list,
                )

                log_event(
                    logger=logger,
                    level="info",
                    event="dataset_get_success",
                    user=username,
                    extra={"dataset_id": dataset_id},
                )

                return dataset

        except HTTPException:  # pylint: disable=duplicate-code
            # TODO(pylint-refactor): Extract common exception handling pattern into utility function
            raise
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="dataset_get_failed",
                user=username,
                extra={"dataset_id": dataset_id, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve dataset",
            ) from e


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
    # pylint: disable=redundant-returns-doc
def delete_dataset(
    dataset_id: str,
    username: str = Depends(get_current_username),
) -> None:
    """Delete dataset and associated data for authenticated user.

    Removes dataset metadata and drops the associated data table
    per openapi.yaml DELETE /datasets/{dataset_id}.

    Args:
        dataset_id: UUID of the dataset to delete
        username: Current authenticated user

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 404: Dataset not found or not owned by user
        HTTPException 500: Server error during deletion

    Per openapi.yaml DELETE /datasets/{dataset_id}:
    - Response 204: No Content (successful deletion)
    - Response 404: Dataset not found
    - Cascade: Drops dataset table and removes metadata
    """
    log_event(
        logger=logger,
        level="info",
        event="dataset_delete_request",
        user=username,
        extra={"dataset_id": dataset_id},
    )

    pool: DatabaseConnectionPool = get_pool_with_error_handling(
        logger=logger, event_name="delete_failed", user=username
    )

    with pool.connection() as conn:
        try:
            # First, get the table_name for the dataset
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT table_name
                    FROM {username}_schema.datasets
                    WHERE id = %s
                    """,
                    (dataset_id,),
                )
                row: tuple[Any, ...] | None = cur.fetchone()

                if row is None:
                    log_event(
                        logger=logger,
                        level="warning",
                        event="dataset_not_found_for_delete",
                        user=username,
                        extra={"dataset_id": dataset_id},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Dataset {dataset_id} not found",
                    )

                table_name: str = row[0]

            # Drop the data table
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {username}_schema.{table_name} CASCADE")

            # Delete the dataset metadata
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    DELETE FROM {username}_schema.datasets
                    WHERE id = %s
                    """,
                    (dataset_id,),
                )

            conn.commit()

            log_event(
                logger=logger,
                level="info",
                event="dataset_delete_success",
                user=username,
                extra={"dataset_id": dataset_id, "table_name": table_name},
            )

        except HTTPException:  # pylint: disable=duplicate-code
            # TODO(pylint-refactor): Extract common exception handling pattern into utility function
            raise
        except Exception as e:
            log_event(
                logger=logger,
                level="error",
                event="dataset_delete_failed",
                user=username,
                extra={"dataset_id": dataset_id, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete dataset",
            ) from e
