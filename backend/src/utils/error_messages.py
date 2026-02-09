"""Standardized error messages for API endpoints.

Implements FR-002: Clear error messages requirement
Provides consistent error codes and user-friendly messages across all endpoints.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any

from fastapi import HTTPException, status


class ErrorCode:
    """Standard error codes for API responses.

    Format: CATEGORY_SPECIFIC_ISSUE
    Categories: AUTH, DATASET, QUERY, VALIDATION, SERVER
    """

    # Authentication Errors (401, 403)
    AUTH_MISSING_TOKEN: str = "AUTH_MISSING_TOKEN"
    AUTH_INVALID_TOKEN: str = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN: str = "AUTH_EXPIRED_TOKEN"
    AUTH_INVALID_USERNAME: str = "AUTH_INVALID_USERNAME"
    AUTH_SCHEMA_CREATION_FAILED: str = "AUTH_SCHEMA_CREATION_FAILED"

    # Dataset Errors (400, 404, 409)
    DATASET_NOT_FOUND: str = "DATASET_NOT_FOUND"
    DATASET_NO_FILENAME: str = "DATASET_NO_FILENAME"
    DATASET_FILENAME_CONFLICT: str = "DATASET_FILENAME_CONFLICT"
    DATASET_INVALID_CSV: str = "DATASET_INVALID_CSV"
    DATASET_UPLOAD_FAILED: str = "DATASET_UPLOAD_FAILED"
    DATASET_DELETE_FAILED: str = "DATASET_DELETE_FAILED"

    # Query Errors (400, 404, 409)
    QUERY_NOT_FOUND: str = "QUERY_NOT_FOUND"
    QUERY_EMPTY_TEXT: str = "QUERY_EMPTY_TEXT"
    QUERY_EXECUTION_FAILED: str = "QUERY_EXECUTION_FAILED"
    QUERY_TIMEOUT: str = "QUERY_TIMEOUT"
    QUERY_CANCELLED: str = "QUERY_CANCELLED"
    QUERY_INVALID_DATASET: str = "QUERY_INVALID_DATASET"
    QUERY_NO_DATASETS: str = "QUERY_NO_DATASETS"

    # Validation Errors (422)
    VALIDATION_FAILED: str = "VALIDATION_FAILED"
    VALIDATION_MISSING_FIELD: str = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_FORMAT: str = "VALIDATION_INVALID_FORMAT"

    # Server Errors (500, 503)
    SERVER_ERROR: str = "SERVER_ERROR"
    SERVER_DATABASE_ERROR: str = "SERVER_DATABASE_ERROR"
    SERVER_DATABASE_UNAVAILABLE: str = "SERVER_DATABASE_UNAVAILABLE"
    SERVER_LLM_ERROR: str = "SERVER_LLM_ERROR"


class APIError:
    """Factory for standardized API error responses with user-friendly messages."""

    @staticmethod
    def authentication_missing_token() -> HTTPException:
        """Raise when Authorization header is missing.

        Returns:
            HTTPException with 401 status code

        Example:
            >>> raise APIError.authentication_missing_token()
        """
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": ErrorCode.AUTH_MISSING_TOKEN,
                "message": "Authentication required. Please provide a valid access token in the Authorization header.",
                "hint": "Include 'Authorization: Bearer <token>' in your request headers.",
            },
        )

    @staticmethod
    def authentication_invalid_token(reason: str = "Invalid token format") -> HTTPException:
        """Raise when JWT token is invalid or malformed.

        Args:
            reason: Specific reason for token invalidity

        Returns:
            HTTPException with 401 status code
        """
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": ErrorCode.AUTH_INVALID_TOKEN,
                "message": f"Authentication failed: {reason}",
                "hint": "Please log in again to obtain a new access token.",
            },
        )

    @staticmethod
    def authentication_invalid_username(username: str) -> HTTPException:
        """Raise when username format is invalid.

        Args:
            username: The invalid username provided

        Returns:
            HTTPException with 400 status code
        """
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.AUTH_INVALID_USERNAME,
                "message": f"Invalid username: '{username}'",
                "hint": "Username must be 3-50 characters, start with a lowercase letter, and contain only lowercase letters, numbers, and underscores.",
            },
        )

    @staticmethod
    def dataset_not_found(dataset_id: str) -> HTTPException:
        """Raise when dataset does not exist.

        Args:
            dataset_id: The UUID of the dataset that was not found

        Returns:
            HTTPException with 404 status code
        """
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.DATASET_NOT_FOUND,
                "message": f"Dataset '{dataset_id}' not found",
                "hint": "Verify the dataset ID is correct and the dataset hasn't been deleted.",
            },
        )

    @staticmethod
    def dataset_no_filename() -> HTTPException:
        """Raise when uploaded file has no filename.

        Returns:
            HTTPException with 400 status code
        """
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.DATASET_NO_FILENAME,
                "message": "Uploaded file has no filename",
                "hint": "Ensure the file is properly attached to the upload request with a valid filename.",
            },
        )

    @staticmethod
    def dataset_filename_conflict(
        filename: str, suggested_filename: str, existing_dataset_id: str
    ) -> HTTPException:
        """Raise when uploaded filename already exists.

        Args:
            filename: The conflicting filename
            suggested_filename: System-suggested alternative filename
            existing_dataset_id: UUID of existing dataset with same filename

        Returns:
            HTTPException with 409 status code
        """
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ErrorCode.DATASET_FILENAME_CONFLICT,
                "message": f"A dataset named '{filename}' already exists",
                "hint": f"You can delete the existing dataset or rename your file to '{suggested_filename}'",
                "existing_dataset_id": existing_dataset_id,
                "suggested_filename": suggested_filename,
            },
        )

    @staticmethod
    def dataset_invalid_csv(error_message: str) -> HTTPException:
        """Raise when CSV file validation fails.

        Args:
            error_message: Specific validation error message from CSVValidator

        Returns:
            HTTPException with 400 status code
        """
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.DATASET_INVALID_CSV,
                "message": error_message,  # Already user-friendly from CSVValidator
                "hint": "Ensure your CSV file is properly formatted with consistent delimiters and encoding.",
            },
        )

    @staticmethod
    def query_not_found(query_id: str) -> HTTPException:
        """Raise when query does not exist.

        Args:
            query_id: The UUID of the query that was not found

        Returns:
            HTTPException with 404 status code
        """
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.QUERY_NOT_FOUND,
                "message": f"Query '{query_id}' not found",
                "hint": "Verify the query ID is correct. Queries may be deleted after a certain period.",
            },
        )

    @staticmethod
    def query_empty_text() -> HTTPException:
        """Raise when query text is empty.

        Returns:
            HTTPException with 400 status code
        """
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.QUERY_EMPTY_TEXT,
                "message": "Query text cannot be empty",
                "hint": "Please provide a question about your data (e.g., 'What are the top 10 sales by revenue?')",
            },
        )

    @staticmethod
    def query_no_datasets() -> HTTPException:
        """Raise when user has no datasets to query.

        Returns:
            HTTPException with 400 status code
        """
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.QUERY_NO_DATASETS,
                "message": "No datasets available to query",
                "hint": "Please upload at least one CSV file before submitting queries.",
            },
        )

    @staticmethod
    def query_invalid_dataset(dataset_id: str) -> HTTPException:
        """Raise when specified dataset does not exist.

        Args:
            dataset_id: The UUID of the invalid dataset

        Returns:
            HTTPException with 400 status code
        """
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.QUERY_INVALID_DATASET,
                "message": f"Dataset '{dataset_id}' does not exist or you don't have access to it",
                "hint": "Verify the dataset ID is correct and the dataset hasn't been deleted.",
            },
        )

    @staticmethod
    def query_timeout(timeout_seconds: int = 30) -> HTTPException:
        """Raise when query execution exceeds timeout.

        Args:
            timeout_seconds: The timeout limit that was exceeded

        Returns:
            HTTPException with 500 status code
        """
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": ErrorCode.QUERY_TIMEOUT,
                "message": f"Query execution exceeded {timeout_seconds} second timeout",
                "hint": "Try simplifying your question or querying smaller datasets. You can also cancel long-running queries.",
            },
        )

    @staticmethod
    def server_database_unavailable() -> HTTPException:
        """Raise when database connection is unavailable.

        Returns:
            HTTPException with 503 status code
        """
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": ErrorCode.SERVER_DATABASE_UNAVAILABLE,
                "message": "Database connection unavailable",
                "hint": "The database is temporarily unavailable. Please try again in a few moments.",
            },
        )

    @staticmethod
    def server_database_error(operation: str) -> HTTPException:
        """Raise when database operation fails.

        Args:
            operation: Description of the failed operation

        Returns:
            HTTPException with 500 status code
        """
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": ErrorCode.SERVER_DATABASE_ERROR,
                "message": f"Database error during {operation}",
                "hint": "An unexpected database error occurred. Please try again or contact support if the issue persists.",
            },
        )

    @staticmethod
    def server_llm_error(operation: str, details: str | None = None) -> HTTPException:
        """Raise when LLM API call fails.

        Args:
            operation: Description of the LLM operation that failed
            details: Optional additional details about the failure

        Returns:
            HTTPException with 500 status code
        """
        message: str = f"AI service error during {operation}"
        if details:
            message = f"{message}: {details}"

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": ErrorCode.SERVER_LLM_ERROR,
                "message": message,
                "hint": "The AI service is temporarily unavailable or experiencing high load. Please try again.",
            },
        )

    @staticmethod
    def validation_failed(errors: list[dict[str, Any]]) -> HTTPException:
        """Raise when request validation fails (Pydantic errors).

        Args:
            errors: List of validation error dictionaries

        Returns:
            HTTPException with 422 status code
        """
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": ErrorCode.VALIDATION_FAILED,
                "message": "Request validation failed",
                "errors": errors,
                "hint": "Check the 'errors' field for specific validation issues.",
            },
        )

    @staticmethod
    def generic_server_error(operation: str = "request processing") -> HTTPException:
        """Raise for generic server errors (fallback).

        Args:
            operation: Description of what was being attempted

        Returns:
            HTTPException with 500 status code
        """
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": ErrorCode.SERVER_ERROR,
                "message": f"An unexpected error occurred during {operation}",
                "hint": "Please try again. If the problem persists, contact support.",
            },
        )
