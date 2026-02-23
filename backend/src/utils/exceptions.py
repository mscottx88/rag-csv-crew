"""Custom exception classes for RAG CSV Crew application.

Provides specific exception types for better error handling and clarity.
Replaces generic Exception usage per T227-REFACTOR.

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- Thread-based operations only (no async/await)
"""


class QueryNotFoundException(Exception):
    """Raised when a query is not found in the database.

    Used in QueryHistoryService when attempting to access a non-existent query.

    Attributes:
        query_id: UUID of the query that was not found
        username: Username attempting to access the query
    """

    def __init__(self, query_id: str, username: str) -> None:
        """Initialize QueryNotFoundException.

        Args:
            query_id: UUID of the query not found
            username: Username attempting access
        """
        self.query_id: str = query_id
        self.username: str = username
        super().__init__(f"Query {query_id} not found for user {username}")


class ResponseNotFoundException(Exception):
    """Raised when a response is not found for a given query.

    Used when a query has no associated response in the responses table.

    Attributes:
        query_id: UUID of the query with missing response
        username: Username attempting to access the response
    """

    def __init__(self, query_id: str, username: str) -> None:
        """Initialize ResponseNotFoundException.

        Args:
            query_id: UUID of the query with missing response
            username: Username attempting access
        """
        self.query_id: str = query_id
        self.username: str = username
        super().__init__(f"No response found for query {query_id} (user: {username})")


class QueryCancelledException(Exception):
    """Raised when a query is cancelled during execution.

    Used in QueryExecutionService when a query is cancelled by user request
    or timeout.

    Attributes:
        query_id: UUID of the cancelled query
        reason: Reason for cancellation (user request, timeout, etc.)
    """

    def __init__(self, query_id: str, reason: str = "user request") -> None:
        """Initialize QueryCancelledException.

        Args:
            query_id: UUID of cancelled query
            reason: Cancellation reason (default: "user request")
        """
        self.query_id: str = query_id
        self.reason: str = reason
        super().__init__(f"Query {query_id} cancelled: {reason}")


class QueryTimeoutException(Exception):
    """Raised when a query exceeds the maximum execution time.

    Used when SQL query execution exceeds the configured timeout limit
    (default: 30 seconds per FR-025).

    Attributes:
        query_id: UUID of the timed-out query
        timeout_seconds: Timeout limit that was exceeded
    """

    def __init__(self, query_id: str, timeout_seconds: int) -> None:
        """Initialize QueryTimeoutException.

        Args:
            query_id: UUID of timed-out query
            timeout_seconds: Timeout limit in seconds
        """
        self.query_id: str = query_id
        self.timeout_seconds: int = timeout_seconds
        super().__init__(
            f"Query {query_id} exceeded timeout of {timeout_seconds} seconds"
        )


class DatasetNotFoundException(Exception):
    """Raised when a dataset is not found in the database.

    Used when attempting to access a dataset that doesn't exist or
    doesn't belong to the current user.

    Attributes:
        dataset_id: UUID of the dataset not found
        username: Username attempting to access the dataset
    """

    def __init__(self, dataset_id: str, username: str) -> None:
        """Initialize DatasetNotFoundException.

        Args:
            dataset_id: UUID of dataset not found
            username: Username attempting access
        """
        self.dataset_id: str = dataset_id
        self.username: str = username
        super().__init__(f"Dataset {dataset_id} not found for user {username}")


class UserNotFoundException(Exception):
    """Raised when a user is not found in the database.

    Used in authentication and user management operations.

    Attributes:
        username: Username that was not found
    """

    def __init__(self, username: str) -> None:
        """Initialize UserNotFoundException.

        Args:
            username: Username not found
        """
        self.username: str = username
        super().__init__(f"User '{username}' not found")


class CSVValidationError(Exception):
    """Raised when CSV file validation fails.

    Used by CSVValidator for detailed validation error reporting
    per FR-002.

    Attributes:
        message: User-friendly error message
        error_code: Machine-readable error code
        details: Additional error details dictionary
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        details: dict[str, str | int] | None = None,
    ) -> None:
        """Initialize CSVValidationError.

        Args:
            message: User-friendly error message
            error_code: Machine-readable error code
            details: Optional additional error details
        """
        self.message: str = message
        self.error_code: str = error_code
        self.details: dict[str, str | int] = details if details is not None else {}
        super().__init__(message)


class EmbeddingGenerationError(Exception):
    """Raised when embedding generation fails.

    Used when OpenAI/Gemini API calls fail during semantic embedding generation.

    Attributes:
        text: Text that failed to generate embedding
        provider: Embedding provider (openai, google)
        reason: Failure reason
    """

    def __init__(self, text: str, provider: str, reason: str) -> None:
        """Initialize EmbeddingGenerationError.

        Args:
            text: Text that failed embedding generation
            provider: Provider name (openai, google)
            reason: Failure reason
        """
        self.text: str = text
        self.provider: str = provider
        self.reason: str = reason
        super().__init__(
            f"Failed to generate embedding for text '{text[:50]}...' "
            f"using {provider}: {reason}"
        )


class SchemaInferenceError(Exception):
    """Raised when CSV schema inference fails.

    Used when detect_csv_schema cannot determine column types or structure.

    Attributes:
        filename: CSV filename
        reason: Failure reason
    """

    def __init__(self, filename: str, reason: str) -> None:
        """Initialize SchemaInferenceError.

        Args:
            filename: CSV filename
            reason: Failure reason
        """
        self.filename: str = filename
        self.reason: str = reason
        super().__init__(f"Failed to infer schema for '{filename}': {reason}")
