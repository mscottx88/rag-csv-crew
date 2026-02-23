# Phase 1: Data Model Design

**Feature**: Hybrid Search RAG for CSV Data
**Date**: 2026-02-02
**Status**: Complete

## Overview

This document defines all data models, database schemas, and entity relationships for the hybrid search RAG application. Models follow Pydantic v2 patterns and PostgreSQL schema design per constitution requirements.

## Entity Definitions (from spec.md)

From specification, six key entities identified:

1. **User**: Individual using the system, identified by unique username
2. **Dataset**: Uploaded CSV file with metadata
3. **Query**: User question with processing status
4. **Response**: Answer to a query with formatted HTML content
5. **Column Mapping**: System's understanding of data structure
6. **Cross-Reference**: Detected relationships between datasets

## Database Schema Design

### PostgreSQL Architecture

**Multi-Tenancy Strategy**: Per-user PostgreSQL schemas

```sql
-- System-wide schema (shared metadata)
CREATE SCHEMA IF NOT EXISTS public;

-- Per-user schemas (data isolation)
CREATE SCHEMA IF NOT EXISTS alice_schema;
CREATE SCHEMA IF NOT EXISTS bob_schema;

-- Search path per session
SET search_path TO alice_schema, public;
```

### System Schema (public)

#### Users Table

```sql
CREATE TABLE public.users (
    username VARCHAR(50) PRIMARY KEY,
    schema_name VARCHAR(63) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT username_format CHECK (username ~ '^[a-z][a-z0-9_]{2,49}$')
);

CREATE INDEX idx_users_active ON public.users (is_active) WHERE is_active = TRUE;
```

**Rationale**: Centralized user registry for authentication and schema management

#### Query History (Cross-User Analytics)

```sql
CREATE TABLE public.query_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL REFERENCES public.users(username) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    execution_time_ms INTEGER,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'timeout')),
    result_count INTEGER,
    error_message TEXT,

    CONSTRAINT positive_execution_time CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
    CONSTRAINT positive_result_count CHECK (result_count IS NULL OR result_count >= 0)
);

CREATE INDEX idx_query_log_user_time ON public.query_log (username, submitted_at DESC);
CREATE INDEX idx_query_log_status ON public.query_log (status) WHERE status IN ('pending', 'processing');
```

**Rationale**: Centralized logging for observability (FR-024), cross-user analytics, query caching

### User Schema (per user)

#### Datasets Metadata

```sql
-- In {username}_schema
CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    table_name VARCHAR(63) NOT NULL UNIQUE,
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    row_count BIGINT NOT NULL,
    column_count INTEGER NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    schema_json JSONB NOT NULL, -- Column definitions: [{name, type, nullable}]

    CONSTRAINT positive_row_count CHECK (row_count >= 0),
    CONSTRAINT positive_column_count CHECK (column_count > 0),
    CONSTRAINT positive_file_size CHECK (file_size_bytes > 0),
    CONSTRAINT valid_table_name CHECK (table_name ~ '^[a-z][a-z0-9_]{0,62}$')
);

CREATE INDEX idx_datasets_uploaded ON datasets (uploaded_at DESC);
CREATE INDEX idx_datasets_filename ON datasets (filename);
```

**Rationale**: Per-user dataset metadata, tracks all uploaded CSVs

#### Dynamic CSV Data Tables

```sql
-- Example: User uploads "sales.csv" → table "sales_data"
CREATE TABLE sales_data (
    _row_id BIGSERIAL PRIMARY KEY,
    _dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    _ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Dynamic columns from CSV (inferred types)
    date DATE,
    product_name TEXT,
    quantity INTEGER,
    revenue NUMERIC(10, 2),
    region TEXT,

    _fulltext tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            COALESCE(product_name, '') || ' ' ||
            COALESCE(region, ''))
    ) STORED
);

CREATE INDEX idx_sales_data_dataset ON sales_data (_dataset_id);
CREATE INDEX idx_sales_data_fulltext ON sales_data USING GIN (_fulltext);
```

**Rationale**: Dynamic tables created per CSV upload, `_` prefix for system columns

#### Column Mappings (Semantic Metadata)

```sql
CREATE TABLE column_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    inferred_type VARCHAR(50) NOT NULL,
    semantic_type VARCHAR(100), -- e.g., "date", "currency", "category", "text"
    description TEXT,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension

    UNIQUE (dataset_id, column_name)
);

CREATE INDEX idx_column_mappings_dataset ON column_mappings (dataset_id);
CREATE INDEX idx_column_mappings_embedding ON column_mappings USING hnsw (embedding vector_cosine_ops);
```

**Rationale**: Semantic understanding of columns for intelligent query routing

#### Cross-References (Dataset Relationships)

```sql
CREATE TABLE cross_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    source_column VARCHAR(255) NOT NULL,
    target_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    target_column VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL CHECK (relationship_type IN ('foreign_key', 'shared_values', 'similar_values')),
    confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (source_dataset_id, source_column, target_dataset_id, target_column)
);

CREATE INDEX idx_cross_refs_source ON cross_references (source_dataset_id);
CREATE INDEX idx_cross_refs_target ON cross_references (target_dataset_id);
```

**Rationale**: Auto-detected relationships for cross-file queries (FR-010)

#### Query History (Per-User)

```sql
CREATE TABLE queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'timeout')),
    generated_sql TEXT,
    result_count INTEGER,
    execution_time_ms INTEGER,

    CONSTRAINT positive_execution_time CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
    CONSTRAINT positive_result_count CHECK (result_count IS NULL OR result_count >= 0)
);

CREATE INDEX idx_queries_submitted ON queries (submitted_at DESC);
CREATE INDEX idx_queries_status ON queries (status) WHERE status IN ('pending', 'processing');
```

**Rationale**: Per-user query history for UI display and caching

#### Response Cache

```sql
CREATE TABLE responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    html_content TEXT NOT NULL,
    plain_text TEXT NOT NULL,
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    data_snapshot JSONB, -- Top N rows returned

    UNIQUE (query_id)
);

CREATE INDEX idx_responses_query ON responses (query_id);
CREATE INDEX idx_responses_generated ON responses (generated_at DESC);
```

**Rationale**: Cache generated responses, support query history display

## Pydantic Models (Python)

### 1. User Models

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class UserBase(BaseModel):
    """Base user model with username validation."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z][a-z0-9_]{2,49}$')

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Ensure username is lowercase and valid format."""
        if not v[0].islower():
            raise ValueError('Username must start with lowercase letter')
        return v

class UserCreate(UserBase):
    """Request model for user creation."""
    pass

class User(UserBase):
    """Complete user model with metadata."""
    schema_name: str
    created_at: datetime
    last_login_at: datetime | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    """Login request (username only, no password)."""
    username: str = Field(..., min_length=3, max_length=50)

class AuthToken(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str = "bearer"
    username: str
```

### 2. Dataset Models

```python
from uuid import UUID
from typing import Any

class ColumnSchema(BaseModel):
    """Schema for a single CSV column."""
    name: str = Field(..., min_length=1, max_length=255)
    inferred_type: str = Field(..., pattern=r'^(text|integer|numeric|boolean|date|timestamp)$')
    nullable: bool = False
    semantic_type: str | None = None
    description: str | None = None

class DatasetBase(BaseModel):
    """Base dataset model."""
    filename: str = Field(..., min_length=1, max_length=255)

class DatasetCreate(DatasetBase):
    """Dataset creation with file upload."""
    pass

class Dataset(DatasetBase):
    """Complete dataset model with metadata."""
    id: UUID
    original_filename: str
    table_name: str
    uploaded_at: datetime
    row_count: int = Field(..., ge=0)
    column_count: int = Field(..., gt=0)
    file_size_bytes: int = Field(..., gt=0)
    schema_json: list[ColumnSchema]

    model_config = ConfigDict(from_attributes=True)

class DatasetList(BaseModel):
    """Paginated list of datasets."""
    datasets: list[Dataset]
    total_count: int
    page: int = 1
    page_size: int = 50
```

### 3. Query Models

```python
from enum import Enum

class QueryStatus(str, Enum):
    """Query processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class QueryCreate(BaseModel):
    """Query submission request."""
    query_text: str = Field(..., min_length=1, max_length=5000)
    dataset_ids: list[UUID] | None = None  # Specific datasets or all

class Query(BaseModel):
    """Complete query model."""
    id: UUID
    query_text: str
    submitted_at: datetime
    completed_at: datetime | None = None
    status: QueryStatus
    generated_sql: str | None = None
    result_count: int | None = Field(None, ge=0)
    execution_time_ms: int | None = Field(None, ge=0)

    model_config = ConfigDict(from_attributes=True)

class QueryCancel(BaseModel):
    """Request to cancel a running query."""
    query_id: UUID

class QueryHistory(BaseModel):
    """Paginated query history."""
    queries: list[Query]
    total_count: int
    page: int = 1
    page_size: int = 50
```

### 4. Response Models

```python
class ResponseBase(BaseModel):
    """Base response model."""
    query_id: UUID

class Response(ResponseBase):
    """Complete response model."""
    id: UUID
    html_content: str = Field(..., min_length=1)
    plain_text: str = Field(..., min_length=1)
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    generated_at: datetime
    data_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)

class QueryWithResponse(Query):
    """Query with embedded response."""
    response: Response | None = None
```

### 5. Configuration Models

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseConfig(BaseSettings):
    """PostgreSQL configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "ragcsv"
    user: str
    password: str
    pool_min_size: int = 2
    pool_max_size: int = 10
    statement_timeout: int = 30000  # 30 seconds in ms

    model_config = SettingsConfigDict(env_prefix="DB_")

class LLMConfig(BaseSettings):
    """LLM API configuration."""
    provider: str = "openai"  # openai, anthropic, ollama
    api_key: str | None = None
    model: str = "gpt-4"
    embedding_model: str = "text-embedding-3-small"
    max_tokens: int = 4096
    temperature: float = Field(0.1, ge=0.0, le=2.0)

    model_config = SettingsConfigDict(env_prefix="LLM_")

class AppConfig(BaseSettings):
    """Application configuration."""
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]
    query_timeout_seconds: int = 30
    max_file_size_bytes: int = 0  # 0 = unlimited

    model_config = SettingsConfigDict(env_file=".env")
```

## Type System Mapping

### CSV Type Detection → PostgreSQL Types

| CSV Pattern | PostgreSQL Type | Example Value |
|-------------|----------------|---------------|
| `YYYY-MM-DD` | DATE | `2024-01-15` |
| `YYYY-MM-DD HH:MM:SS` | TIMESTAMP | `2024-01-15 10:30:00` |
| Integer only | INTEGER or BIGINT | `42`, `1000000` |
| Decimal | NUMERIC(p,s) | `19.99`, `1000.50` |
| `true/false`, `yes/no` | BOOLEAN | `true`, `yes` |
| Currency prefix | NUMERIC(10,2) | `$19.99`, `€100.00` |
| Default | TEXT | Any string |

### PostgreSQL Types → Python Types (Pydantic)

| PostgreSQL | Python (Pydantic) | Notes |
|------------|-------------------|-------|
| VARCHAR, TEXT | str | UTF-8 strings |
| INTEGER | int | 32-bit signed |
| BIGINT | int | 64-bit signed |
| NUMERIC | Decimal | Exact precision |
| BOOLEAN | bool | True/False |
| DATE | datetime.date | Date only |
| TIMESTAMP | datetime.datetime | With timezone |
| JSONB | dict[str, Any] | JSON objects |
| UUID | uuid.UUID | Standard UUIDs |
| vector(n) | list[float] | pgvector embeddings |

## Data Flow Diagrams

### CSV Upload Flow

```
User → FastAPI Upload Endpoint
  ↓
Schema Detection (sample 1000 rows)
  ↓
User Schema Creation (if new user)
  ↓
Table Creation ({filename}_data)
  ↓
Bulk INSERT via COPY protocol
  ↓
Column Mapping Generation
  ↓
Embedding Generation (column names)
  ↓
Cross-Reference Detection
  ↓
Dataset Metadata Saved
```

### Query Processing Flow

```
Natural Language Query → FastAPI
  ↓
CrewAI Agent Orchestration
  ├── SQL Generator Agent → Text-to-SQL
  ├── Keyword Search Agent → Full-text search
  └── Vector Search Agent → Embedding similarity
  ↓
Result Fusion (weighted scoring)
  ↓
Result Analyst Agent → HTML generation
  ↓
Response Cache Save
  ↓
HTML Response to User
```

## Indexing Strategy

### Primary Indexes (Always Created)

```sql
-- Performance-critical indexes
CREATE INDEX idx_datasets_user_uploaded ON datasets (uploaded_at DESC);
CREATE INDEX idx_queries_user_status ON queries (status, submitted_at DESC);
CREATE INDEX idx_responses_query ON responses (query_id);
```

### Conditional Indexes (Created Based on Usage)

```sql
-- Full-text search (if text columns detected)
CREATE INDEX idx_{table}_fulltext ON {table} USING GIN (_fulltext);

-- Vector similarity (for semantic search)
CREATE INDEX idx_column_mappings_embedding ON column_mappings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Numeric range queries (if numeric columns frequent in queries)
CREATE INDEX idx_{table}_{column} ON {table} ({column}) WHERE {column} IS NOT NULL;
```

## Constraints & Validations

### Database Level

- Primary keys: UUID (globally unique, non-sequential)
- Foreign keys: Cascade deletes for cleanup
- Check constraints: Status enums, positive values
- Unique constraints: Prevent duplicates (filename per user)

### Application Level (Pydantic)

- Field validation: Length, format, regex patterns
- Type coercion: Strict mode for security
- Custom validators: Business logic (username format)
- Cross-field validation: model_validator decorators

## Migration Strategy

### Initial Setup

```python
from psycopg import Connection

def initialize_database(conn: Connection) -> None:
    """Create system schema and tables."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS public;
            CREATE EXTENSION IF NOT EXISTS vector;
            CREATE TABLE IF NOT EXISTS public.users (...);
            CREATE TABLE IF NOT EXISTS public.query_log (...);
        """)
    conn.commit()

def initialize_user_schema(conn: Connection, username: str) -> None:
    """Create per-user schema and tables."""
    schema_name: str = f"{username}_schema"
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        cur.execute(f"""
            CREATE TABLE {schema_name}.datasets (...);
            CREATE TABLE {schema_name}.column_mappings (...);
            CREATE TABLE {schema_name}.cross_references (...);
            CREATE TABLE {schema_name}.queries (...);
            CREATE TABLE {schema_name}.responses (...);
        """)
    conn.commit()
```

### Future Migrations

- Use Alembic or similar migration tool
- Version control schema changes
- Test migrations in staging before production
- Support rollback for failed migrations

---

**Next Steps**: Generate API contracts (contracts/openapi.yaml) and quickstart guide
