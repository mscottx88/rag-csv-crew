"""Pydantic models for RAG CSV Crew application.

This package contains all data models following Pydantic v2 patterns
per constitution requirements.

Models:
- config: Application configuration (DatabaseConfig, LLMConfig, AppConfig)
- user: User management and authentication (User, UserLogin, AuthToken)
- dataset: CSV dataset metadata (Dataset, ColumnSchema)
- query: Query processing (Query, QueryStatus, Response, QueryWithResponse)
"""

from src.models.config import (
    AppConfig,
    DatabaseConfig,
    LLMConfig,
)
from src.models.dataset import (
    ColumnSchema,
    Dataset,
    DatasetCreate,
    DatasetList,
)
from src.models.query import (
    Query,
    QueryCancel,
    QueryCreate,
    QueryHistory,
    QueryStatus,
    QueryWithResponse,
    Response,
)
from src.models.user import (
    AuthToken,
    User,
    UserBase,
    UserCreate,
    UserLogin,
)

__all__: list[str] = [
    # Configuration models
    "AppConfig",
    "DatabaseConfig",
    "LLMConfig",
    # User models
    "User",
    "UserBase",
    "UserCreate",
    "UserLogin",
    "AuthToken",
    # Dataset models
    "ColumnSchema",
    "Dataset",
    "DatasetCreate",
    "DatasetList",
    # Query and Response models
    "Query",
    "QueryCreate",
    "QueryCancel",
    "QueryHistory",
    "QueryStatus",
    "QueryWithResponse",
    "Response",
]
