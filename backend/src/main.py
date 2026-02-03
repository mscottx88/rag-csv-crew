"""FastAPI application entry point with global configuration.

Implements:
- FastAPI app initialization
- CORS middleware configuration
- Global exception handlers
- Router registration
- Thread-safe synchronous route handlers only

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- All route handlers use def (NOT async def)
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.src.api.auth import router as auth_router
from backend.src.api.datasets import router as datasets_router
from backend.src.api.health import router as health_router
from backend.src.models.config import AppConfig
from backend.src.utils.logging import (
    get_structured_logger,
    log_error,
    log_event,
)

# Get logger
logger = get_structured_logger(__name__)


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException with structured error response.

    Args:
        request: FastAPI request object
        exc: HTTPException instance

    Returns:
        JSON response with error details

    Per FR-024: Structured error logging
    """
    # Log HTTP exception
    log_event(
        logger=logger,
        level="warning",
        event="http_exception",
        user=None,  # User not available in exception context
        extra={
            "status_code": exc.status_code,
            "detail": str(exc.detail),
            "path": str(request.url),
        },
    )

    # Return structured error response
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "status_code": exc.status_code,
            "detail": str(exc.detail),
            "path": str(request.url),
        },
    )


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with user-friendly messages.

    Args:
        request: FastAPI request object
        exc: RequestValidationError with validation details

    Returns:
        JSON response with validation error details

    Per FR-002: Clear error messages requirement
    """
    # Extract validation errors
    errors: list[dict[str, Any]] = []
    for error in exc.errors():
        field: str = " -> ".join(str(loc) for loc in error["loc"])
        message: str = error["msg"]
        error_type: str = error["type"]

        errors.append(
            {
                "field": field,
                "message": message,
                "type": error_type,
            }
        )

    # Log validation error
    log_event(
        logger=logger,
        level="warning",
        event="validation_error",
        user=None,
        extra={
            "path": str(request.url),
            "errors": errors,
        },
    )

    # Return structured validation error response
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "status_code": 422,
            "detail": "Request validation failed",
            "errors": errors,
            "path": str(request.url),
        },
    )


def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with generic error response.

    Args:
        request: FastAPI request object
        exc: Generic exception

    Returns:
        JSON response with generic error message

    Per FR-024: Error logging with stack trace
    Security: Does not expose internal error details to client
    """
    # Log error with stack trace
    log_error(
        logger=logger,
        event="unhandled_exception",
        user=None,
        error=exc,
    )

    # Return generic error response (don't expose internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "status_code": 500,
            "detail": "An unexpected error occurred. Please try again later.",
            "path": str(request.url),
        },
    )


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI app instance

    Configuration includes:
    - CORS middleware for frontend communication
    - Global exception handlers
    - API routers registration
    - OpenAPI documentation

    Per quickstart.md: Application setup and configuration
    """
    # Load configuration
    config: AppConfig = AppConfig()

    # Create FastAPI app instance
    fastapi_app: FastAPI = FastAPI(
        title="RAG CSV Crew API",
        version="0.1.0",
        description="Hybrid Search RAG for CSV Data with Multi-Agent Orchestration",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register global exception handlers
    fastapi_app.add_exception_handler(
        HTTPException, http_exception_handler
    )  # type: ignore[arg-type]
    fastapi_app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )  # type: ignore[arg-type]
    fastapi_app.add_exception_handler(Exception, generic_exception_handler)

    # Register API routers
    fastapi_app.include_router(auth_router, prefix="", tags=["auth"])
    fastapi_app.include_router(datasets_router, prefix="", tags=["datasets"])
    fastapi_app.include_router(health_router, prefix="", tags=["health"])

    # Log application startup
    log_event(
        logger=logger,
        level="info",
        event="app_startup",
        user=None,
        extra={
            "title": fastapi_app.title,
            "version": fastapi_app.version,
            "cors_origins": config.cors_origins,
        },
    )

    return fastapi_app


# Create app instance (for uvicorn/gunicorn)
app: FastAPI = create_app()


if __name__ == "__main__":
    import uvicorn

    # Run development server (synchronous WSGI server)
    # Per Constitution Principle VI: No async event loops
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        workers=1,  # Single worker for development
    )
