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

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables from .env file at project root
# Use explicit path to ensure .env is found regardless of working directory
# Path: backend/src/main.py -> backend/src/ -> backend/ -> project_root/
env_path: Path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Import after load_dotenv() to ensure environment variables are available
# pylint: disable=wrong-import-position
# pylint: enable=wrong-import-position
# Setup application logging (configurable via LOG_LEVEL environment variable)
import os  # noqa: E402

# JUSTIFICATION: load_dotenv() must run before these imports to ensure env vars are available
from backend.src.api.auth import router as auth_router  # noqa: E402
from backend.src.api.dataset_rows import router as dataset_rows_router  # noqa: E402
from backend.src.api.datasets import router as datasets_router  # noqa: E402
from backend.src.api.health import router as health_router  # noqa: E402
from backend.src.api.queries import router as queries_router  # noqa: E402
from backend.src.db.connection import close_global_pool, initialize_global_pool  # noqa: E402
from backend.src.models.config import AppConfig  # noqa: E402
from backend.src.utils.logging import (  # noqa: E402
    get_structured_logger,
    log_error,
    log_event,
    setup_application_logging,
)

log_level: str = os.getenv("LOG_LEVEL", "INFO")
setup_application_logging(log_level=log_level)

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
    Per T200-POLISH: Standardized error messages with error codes
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

    # Return standardized validation error response (T200-POLISH)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_FAILED",
            "message": "Request validation failed. Please check the 'errors' field for details.",
            "errors": errors,
            "hint": "Ensure all required fields are provided with correct data types.",
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

    # Create FastAPI app instance with comprehensive API documentation (T215-POLISH)
    fastapi_app: FastAPI = FastAPI(
        title="RAG CSV Crew API",
        version="0.1.0",
        description="""
## Intelligent Natural Language Query System for CSV Data

Convert natural language questions into SQL queries using hybrid search
(exact + full-text + semantic vector) and CrewAI multi-agent orchestration.

### Key Features

- **Natural Language Queries**: Ask questions in plain English about CSV data
- **Hybrid Search**: Combines exact matching, full-text search (ts_rank), and semantic similarity (pgvector)
- **Cross-Dataset JOINs**: Automatic relationship detection via value overlap analysis
- **Intelligent Clarification**: Confidence scoring triggers clarification for ambiguous queries
- **SQL Injection Prevention**: Parameterized queries with automatic escaping
- **Rate Limiting**: 100 requests/minute per user with token bucket algorithm
- **JWT Authentication**: Secure user-based schema isolation

### Documentation

- **Swagger UI**: Interactive API documentation at `/docs`
- **ReDoc**: Alternative documentation at `/redoc`
- **OpenAPI Schema**: JSON specification at `/openapi.json`

### Example Workflow

1. **Login**: `POST /auth/login` with username (no password required for demo)
2. **Upload CSV**: `POST /datasets/` with multipart form data
3. **Submit Query**: `POST /queries` with natural language question
4. **Poll Results**: `GET /queries/{query_id}` to check status and retrieve HTML response

### Security

- JWT tokens expire after 30 minutes (configurable)
- Rate limit: 100 requests/minute per user
- CORS: Explicit origin whitelisting
- SQL injection protection via parameterized queries
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={
            "name": "RAG CSV Crew Team",
            "url": "https://github.com/nearform/rag-csv-crew",
        },
        license_info={
            "name": "MIT",
        },
    )

    # Configure CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Note: Rate limiting (T209) implemented via dependency injection in API endpoints
    # See src/api/dependencies.py for check_rate_limit() function

    # Register global exception handlers
    fastapi_app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]  # pylint: disable=line-too-long
    fastapi_app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]  # pylint: disable=line-too-long
    fastapi_app.add_exception_handler(Exception, generic_exception_handler)

    # Register API routers
    fastapi_app.include_router(auth_router, prefix="", tags=["auth"])
    fastapi_app.include_router(dataset_rows_router, prefix="", tags=["datasets"])
    fastapi_app.include_router(datasets_router, prefix="", tags=["datasets"])
    fastapi_app.include_router(queries_router, prefix="", tags=["queries"])
    fastapi_app.include_router(health_router, prefix="", tags=["health"])

    # Startup event: Initialize database connection pool
    @fastapi_app.on_event("startup")
    def startup_event() -> None:
        """Initialize database connection pool on application startup."""
        initialize_global_pool(config.db)
        log_event(
            logger=logger,
            level="info",
            event="database_pool_initialized",
            user=None,
            extra={"database": config.db.database},  # pylint: disable=no-member
        )

    # Shutdown event: Close database connection pool
    @fastapi_app.on_event("shutdown")
    def shutdown_event() -> None:
        """Close database connection pool on application shutdown."""
        close_global_pool()
        log_event(
            logger=logger,
            level="info",
            event="database_pool_closed",
            user=None,
            extra={},
        )

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
