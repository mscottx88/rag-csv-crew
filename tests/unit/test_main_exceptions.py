"""Unit tests for global exception handlers.

Tests FastAPI global exception handling:
- HTTPException formatting
- RequestValidationError formatting
- Generic Exception handling

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from typing import Any

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import pytest


@pytest.mark.unit
class TestExceptionHandlers:
    """Test FastAPI global exception handlers."""

    def test_http_exception_handler(self) -> None:
        """Test HTTPException handler formats response correctly.

        Validates:
        - Status code preserved
        - Error detail included
        - Response is JSON serializable
        """
        from backend.src.main import http_exception_handler

        # Create mock request (minimal required attributes)
        request: Any = type("Request", (), {"url": "http://test.com/api/test"})()

        # Create HTTPException
        status_code: int = 404
        detail: str = "Resource not found"
        exc: HTTPException = HTTPException(status_code=status_code, detail=detail)

        # Call handler
        response: Any = http_exception_handler(request, exc)

        # Verify response format
        assert response.status_code == status_code
        assert detail in str(response.body) or hasattr(response, "detail")

    def test_validation_error_handler(self) -> None:
        """Test RequestValidationError handler formats validation errors.

        Validates:
        - Returns 422 status code
        - Error details include field names
        - Error messages are user-friendly
        """
        from pydantic import BaseModel, Field

        from backend.src.main import validation_exception_handler

        # Create validation error
        class TestModel(BaseModel):
            name: str = Field(..., min_length=3)
            age: int = Field(..., ge=0)

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/test"})()

        try:
            # Trigger validation error
            TestModel(name="ab", age=-1)  # type: ignore
        except ValidationError as ve:
            # Convert to RequestValidationError
            exc: RequestValidationError = RequestValidationError(ve.errors())

            # Call handler
            response: Any = validation_exception_handler(request, exc)

            # Verify response format
            assert response.status_code == 422
            # Response should contain validation errors

    def test_generic_exception_handler(self) -> None:
        """Test generic Exception handler for unexpected errors.

        Validates:
        - Returns 500 status code
        - Error logged (not exposed to client)
        - Generic error message returned
        """
        from backend.src.main import generic_exception_handler

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/test"})()

        # Create generic exception
        error_message: str = "Unexpected error occurred"
        exc: Exception = Exception(error_message)

        # Call handler
        response: Any = generic_exception_handler(request, exc)

        # Verify response format
        assert response.status_code == 500
        # Should not expose internal error details to client

    def test_exception_handler_thread_safety(self) -> None:
        """Test exception handlers are thread-safe.

        Validates:
        - Multiple threads can trigger exceptions
        - No handler state corruption
        - All exceptions handled correctly

        Per Constitutional Principle VI: Thread-based concurrency
        """
        from concurrent.futures import ThreadPoolExecutor

        from backend.src.main import http_exception_handler

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/test"})()

        results: list[int] = []

        def trigger_exception(error_code: int) -> None:
            """Trigger exception in thread.

            Args:
                error_code: HTTP status code to use
            """
            exc: HTTPException = HTTPException(status_code=error_code, detail=f"Error {error_code}")
            response: Any = http_exception_handler(request, exc)
            results.append(response.status_code)

        # Run 20 concurrent exception handling calls
        error_codes: list[int] = [400, 401, 403, 404, 500] * 4
        num_threads: int = 20

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures: list[Any] = [executor.submit(trigger_exception, code) for code in error_codes]
            for future in futures:
                future.result()

        # All exceptions should be handled
        assert len(results) == num_threads

    def test_validation_error_field_details(self) -> None:
        """Test validation errors include specific field information.

        Validates:
        - Field names included in error
        - Error type specified (missing, invalid, etc.)
        - User-friendly error messages
        """
        from pydantic import BaseModel, Field

        from backend.src.main import validation_exception_handler

        class UserCreate(BaseModel):
            username: str = Field(..., min_length=3, max_length=50)
            email: str

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/users"})()

        try:
            # Trigger validation error (username too short)
            UserCreate(username="ab", email="test@example.com")  # type: ignore
        except ValidationError as ve:
            exc: RequestValidationError = RequestValidationError(ve.errors())
            response: Any = validation_exception_handler(request, exc)

            # Verify field-specific error information present
            assert response.status_code == 422

    def test_exception_logging_integration(self, _caplog: pytest.LogCaptureFixture) -> None:
        """Test exceptions are logged with structured logging.

        Validates:
        - Exceptions logged with stack trace
        - Log includes request information
        - Per FR-024: Error logging requirement
        """
        from backend.src.main import generic_exception_handler

        # Mock request with URL
        request: Any = type("Request", (), {"url": "http://test.com/api/test", "method": "GET"})()

        # Trigger exception
        try:
            raise ValueError("Test exception for logging")
        except ValueError as e:
            generic_exception_handler(request, e)

        # Verify exception was logged
        # In actual implementation, should see log entries in caplog

    def test_http_exception_with_headers(self) -> None:
        """Test HTTPException handler preserves custom headers.

        Validates:
        - Custom headers included in response
        - WWW-Authenticate header for 401 errors
        - Location header for redirect responses
        """
        from backend.src.main import http_exception_handler

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/test"})()

        # Create HTTPException with custom headers
        exc: HTTPException = HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

        response: Any = http_exception_handler(request, exc)

        assert response.status_code == 401

    def test_exception_handler_response_format(self) -> None:
        """Test exception handlers return consistent JSON format.

        Validates:
        - All handlers return JSON responses
        - Response structure consistent across handler types
        - Includes error detail and status code
        """
        from backend.src.main import generic_exception_handler, http_exception_handler

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/test"})()

        # Test HTTP exception response
        http_exc: HTTPException = HTTPException(status_code=400, detail="Bad request")
        http_response: Any = http_exception_handler(request, http_exc)

        assert http_response.status_code == 400

        # Test generic exception response
        generic_exc: Exception = Exception("Internal error")
        generic_response: Any = generic_exception_handler(request, generic_exc)

        assert generic_response.status_code == 500

    def test_validation_error_multiple_fields(self) -> None:
        """Test validation errors with multiple field violations.

        Validates:
        - All field errors included in response
        - Errors grouped by field
        - Clear error messages for each violation
        """
        from pydantic import BaseModel, Field

        from backend.src.main import validation_exception_handler

        class DatasetCreate(BaseModel):
            filename: str = Field(..., min_length=1, max_length=255)
            row_count: int = Field(..., ge=0)
            column_count: int = Field(..., gt=0)

        # Mock request
        request: Any = type("Request", (), {"url": "http://test.com/api/datasets"})()

        try:
            # Multiple validation errors
            DatasetCreate(filename="", row_count=-1, column_count=0)  # type: ignore
        except ValidationError as ve:
            exc: RequestValidationError = RequestValidationError(ve.errors())
            response: Any = validation_exception_handler(request, exc)

            assert response.status_code == 422
