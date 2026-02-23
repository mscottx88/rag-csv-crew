# Phase 0: Research & Technology Decisions

**Feature**: Hybrid Search RAG for CSV Data
**Date**: 2026-02-02
**Status**: Complete

## Overview

This document records research findings and technology decisions for the hybrid search RAG application. All technical context has been specified in plan.md with no open clarifications.

## Technology Stack Decisions

### 1. Backend Framework: FastAPI

**Decision**: Use FastAPI for the REST API backend

**Rationale**:
- **Synchronous simplicity**: FastAPI supports both sync and async handlers - we use synchronous handlers exclusively per constitutional requirement (Principle VI)
- **Performance**: One of the fastest Python frameworks (comparable to Node.js/Go), excellent performance with synchronous handlers for I/O-bound workloads
- **Type safety**: Leverages Python type hints + Pydantic for automatic validation
- **OpenAPI generation**: Automatic schema generation for API contracts
- **Developer experience**: Auto-generated interactive API docs (Swagger UI, ReDoc)
- **Modern Python**: Designed for Python 3.6+ features (type hints, dataclasses)
- **Thread-based concurrency**: Works seamlessly with ThreadPoolExecutor and synchronous database connections

**Alternatives Considered**:
- **Flask**: More mature, good synchronous support, but requires more boilerplate and extensions for validation
- **Django REST Framework**: Full-featured but heavyweight for API-only application
- **Starlette**: FastAPI's foundation, but FastAPI provides better DX with validation and docs

**Best Practices**:
- Use APIRouter for modular route organization
- Leverage dependency injection for shared resources (database pools, authentication)
- Use Pydantic models for request/response validation
- Enable CORS middleware for React frontend communication
- Implement exception handlers for consistent error responses

### 2. Database: PostgreSQL 16+ with pgvector

**Decision**: PostgreSQL with pgvector extension for hybrid search capabilities

**Rationale**:
- **Relational + Vector**: Single database for structured data + vector embeddings
- **pgvector extension**: Native vector similarity search with index support (HNSW, IVFFlat)
- **Full-text search**: Built-in `tsvector` and `tsquery` for keyword search
- **Schema isolation**: PostgreSQL schemas provide per-user data isolation
- **JSON support**: `jsonb` type for flexible metadata storage
- **Mature ecosystem**: Excellent Python drivers (psycopg3), monitoring tools, backups

**Alternatives Considered**:
- **Pinecone/Weaviate**: Dedicated vector DBs but require separate relational DB for structured data
- **MySQL**: Lacks native vector support, weaker full-text search
- **MongoDB**: Document model less suitable for tabular CSV data
- **SQLite**: Insufficient for multi-user concurrent access

**Best Practices**:
- Use connection pooling (psycopg.Pool) for concurrent queries
- Create database schemas programmatically: `CREATE SCHEMA IF NOT EXISTS {username}_schema`
- Index vector columns with HNSW for fast similarity search
- Use `ts_rank` for relevance scoring in full-text search
- Enable statement logging for query performance monitoring

### 3. AI Orchestration: CrewAI

**Decision**: Use CrewAI for multi-agent RAG workflow orchestration

**Rationale**:
- **Agent coordination**: Multiple specialized agents (SQL generator, searcher, analyst)
- **Task decomposition**: Break complex queries into subtasks with dependencies
- **Tool integration**: Custom tools for database access, vector search, SQL execution
- **LLM abstraction**: Works with OpenAI, Anthropic, local models
- **Error handling**: Built-in retry logic and fallback strategies

**Alternatives Considered**:
- **LangChain**: More general-purpose, heavier weight, steeper learning curve
- **Custom LLM integration**: More control but requires building orchestration from scratch
- **Haystack**: Focused on document search, less flexible for multi-agent workflows

**Best Practices**:
- Define agents with clear roles: SQL Generator, Keyword Searcher, Vector Searcher, Result Analyst
- Use sequential task execution for query pipeline: question analysis → search → synthesis
- Implement custom tools for database querying with timeout and cancellation support
- Cache LLM responses for identical questions (query history as cache)
- Log all agent interactions for debugging and performance tuning

### 4. LLM Integration: OpenAI API (configurable)

**Decision**: OpenAI API as primary LLM provider with configurable alternatives

**Rationale**:
- **Text-to-SQL**: GPT-4 shows strong performance on SQL generation tasks
- **Embeddings**: `text-embedding-3-small` provides good quality/cost balance
- **Mature API**: Stable, well-documented, extensive community examples
- **Flexibility**: Can swap to Anthropic Claude, Llama via Ollama, or Azure OpenAI

**Alternatives Considered**:
- **Anthropic Claude**: Strong reasoning but newer API, fewer examples for SQL generation
- **Local models (Ollama)**: Free, private, but requires GPU resources and quality varies
- **Azure OpenAI**: Enterprise-ready but adds deployment complexity

**Best Practices**:
- Use environment variables for API keys (never hardcode)
- Implement LLM abstraction layer for provider swapping
- Set conservative token limits to control costs (max 4096 tokens per request)
- Enable streaming responses for better UX on long generations
- Cache embeddings for reused CSV column names and common queries

### 5. Database Driver: psycopg 3.x (synchronous)

**Decision**: psycopg[pool] version 3.x for PostgreSQL connectivity with synchronous connection pooling

**Rationale**:
- **Thread-based concurrency**: Synchronous connection pool (psycopg.pool.ConnectionPool) aligns with constitutional requirement for thread-based patterns (Principle VI)
- **Connection pooling**: Built-in synchronous connection pool with thread-safe access
- **Performance**: Binary protocol (libpq) faster than pure-Python drivers, excellent performance for I/O-bound workloads
- **Type safety**: Good integration with type checkers (mypy)
- **PostgreSQL native**: Officially recommended driver for PostgreSQL
- **Simplicity**: No async/await complexity, works seamlessly with ThreadPoolExecutor
- **Production maturity**: Thread pools have decades of production hardening

**Alternatives Considered**:
- **asyncpg**: Async-only, violates constitutional prohibition on async/await patterns
- **psycopg2**: Older version with good synchronous support, but psycopg 3.x has better type safety
- **SQLAlchemy**: ORM overhead unnecessary for dynamic table creation from CSVs

**Best Practices**:
- Use synchronous connection pools with min_size=2, max_size=10 for typical load
- Enable prepared statements for repeated queries (query history patterns)
- Use `COPY` protocol for bulk CSV ingestion (much faster than INSERTs)
- Use ThreadPoolExecutor for parallel database operations when needed
- Implement connection health checks before query execution
- Configure statement timeout at pool level (30s max per query)

### 6. Data Validation: Pydantic v2

**Decision**: Pydantic v2 for all data models and configuration

**Rationale**:
- **Constitution requirement**: Mandatory per project constitution
- **FastAPI integration**: Native integration, automatic request/response validation
- **Type safety**: Enforces runtime type checking beyond mypy
- **Performance**: v2 rewrite in Rust core 5-50x faster than v1
- **Validation**: Rich validation rules (regex, ranges, custom validators)

**Best Practices**:
- Use `BaseModel` for API request/response schemas
- Use `BaseSettings` (pydantic-settings) for environment configuration
- Define Field() constraints for validation (min_length, max_length, regex)
- Use `ConfigDict` for model behavior (frozen, extra=forbid)
- Leverage `model_validator` for cross-field validation

### 7. Frontend Framework: React 18+ with TypeScript

**Decision**: React 18+ with TypeScript, built with Vite

**Rationale**:
- **Ecosystem**: Largest component library, extensive documentation
- **Type safety**: TypeScript catches frontend errors at build time
- **Performance**: React 18 concurrent features improve responsiveness
- **Developer experience**: Fast refresh, excellent debugging tools
- **Vite**: Fast dev server (ESBuild), optimized production builds

**Alternatives Considered**:
- **Vue.js**: Simpler but smaller ecosystem for component libraries
- **Svelte**: Excellent performance but smaller community, fewer libraries
- **Plain JavaScript**: No type safety, harder to maintain

**Best Practices**:
- Use functional components with hooks (no class components)
- Implement React Query (TanStack Query) for API state management
- Use axios for API calls with interceptors for auth and error handling
- Organize components by feature (Auth/, Dataset/, Query/)
- Use TypeScript interfaces matching backend Pydantic models

## Integration Patterns

### CSV Ingestion Flow

**Pattern**: Streaming upload → Schema detection → Bulk COPY

```python
from typing import BinaryIO

# 1. Stream upload (chunked, no file size limit)
def upload_csv(file: BinaryIO, username: str) -> None:
    """Upload CSV file using synchronous streaming."""
    chunks: list[bytes] = []
    for chunk in file:
        chunks.append(chunk)

    # 2. Detect schema (sample first 1000 rows)
    schema: dict[str, str] = detect_csv_schema(chunks[:1000])

    # 3. Create user schema + table (synchronous)
    create_user_table(username, schema)

    # 4. Bulk insert via COPY (fastest method, synchronous)
    bulk_insert_copy(username, chunks, schema)
```

**Rationale**: `COPY` protocol is 10-100x faster than INSERTs for bulk data

### Hybrid Search Strategy

**Pattern**: Parallel execution → Score fusion → Ranking

```python
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# Execute 3 search strategies in parallel using ThreadPoolExecutor
def hybrid_search(question: str, username: str) -> list[dict[str, Any]]:
    """Execute 3 search strategies in parallel and combine results."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all search tasks in parallel
        future_exact = executor.submit(exact_match_search, question, username)
        future_fulltext = executor.submit(fulltext_search, question, username)
        future_vector = executor.submit(vector_search, question, username)

        # Wait for all results
        results: list[list[dict[str, Any]]] = [
            future_exact.result(),
            future_fulltext.result(),
            future_vector.result()
        ]

    # Fuse scores (weighted combination)
    fused: list[dict[str, Any]] = fuse_scores(results, weights=[0.4, 0.3, 0.3])

    # Re-rank by combined relevance
    return ranked_results(fused)
```

**Rationale**: Combines complementary search strategies for better recall and precision

### Multi-Tenancy Isolation

**Pattern**: PostgreSQL schemas per user

```sql
-- User "alice" gets schema "alice_schema"
CREATE SCHEMA IF NOT EXISTS alice_schema;

-- All alice's tables in her schema
CREATE TABLE alice_schema.sales_data (...);
CREATE TABLE alice_schema.customers (...);

-- Search path ensures isolation
SET search_path TO alice_schema, public;
```

**Rationale**: Schema-level isolation provides security without separate databases

## Performance Optimizations

### 1. Connection Pooling

- **Configuration**: min_size=2, max_size=10, timeout=30s
- **Benefit**: Avoid connection overhead (50-100ms per connection)
- **Monitoring**: Log pool exhaustion warnings

### 2. Query Caching

- **Strategy**: Cache identical natural language questions → SQL + results
- **TTL**: 5 minutes for query results, 1 hour for SQL generation
- **Invalidation**: Clear cache on dataset changes (upload, delete)

### 3. Embedding Caching

- **Strategy**: Cache column name embeddings, common query embeddings
- **Storage**: PostgreSQL table with vector column for persistence
- **Benefit**: Reduce OpenAI API calls (cost + latency)

### 4. Thread-Based Concurrency

- **Pattern**: All I/O operations use ThreadPoolExecutor for parallelism (database, LLM API, file upload)
- **Concurrency**: Handle multiple user queries simultaneously using thread pools
- **Timeout**: 30s max per query using concurrent.futures.wait() with timeout, cancellation via threading.Event
- **Synchronization**: Use threading.Event for signaling, threading.Lock for shared state protection

## Security Considerations

### 1. SQL Injection Prevention

- **Strategy**: Use parameterized queries exclusively (`$1`, `$2` placeholders)
- **Validation**: Validate user input before SQL generation
- **Sandboxing**: Limit SQL to SELECT queries only (no DDL/DML except in admin operations)

### 2. Schema Isolation

- **Enforcement**: Set `search_path` per user session
- **Validation**: Verify username before schema access
- **Audit**: Log all cross-schema access attempts

### 3. API Rate Limiting

- **Strategy**: 100 requests/minute per user
- **Implementation**: FastAPI middleware with Redis or in-memory store
- **Response**: 429 Too Many Requests with retry-after header

## Monitoring & Observability

### 1. Structured Logging (FR-024)

**Format**: JSON structured logs with fields:
```json
{
  "timestamp": "2026-02-02T10:30:45Z",
  "level": "INFO",
  "event": "query_submitted",
  "user": "alice",
  "query_text": "What are top 10 sales?",
  "execution_time_ms": 1250,
  "result_count": 10
}
```

### 2. Metrics Collection

- Query latency (p50, p95, p99)
- CSV ingestion throughput (rows/sec)
- LLM API call duration and token usage
- Database connection pool utilization

### 3. Error Tracking

- Log all exceptions with stack traces
- Track query timeout frequency
- Monitor connection retry attempts

## Development Environment

### 1. Docker Compose Setup

```yaml
services:
  postgres:
    image: pgvector/pgvector:0.6.0-pg16
    environment:
      POSTGRES_DB: ragcsv
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
```

### 2. Development Workflow

1. Start PostgreSQL: `docker-compose up -d`
2. Install dependencies: `uv sync` (backend), `npm install` (frontend)
3. Run backend: `uvicorn src.main:app --reload`
4. Run frontend: `npm run dev`
5. Access: Backend http://localhost:8000, Frontend http://localhost:5173

### 3. Testing Environment

- Pytest with testcontainers for isolated PostgreSQL per test
- Mock LLM API calls to avoid costs during testing
- Playwright for frontend end-to-end tests

## Open Questions

None - all technical context clarified in plan.md.

## References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- pgvector GitHub: https://github.com/pgvector/pgvector
- CrewAI Documentation: https://docs.crewai.com/
- psycopg3 Documentation: https://www.psycopg.org/psycopg3/
- Pydantic v2 Migration: https://docs.pydantic.dev/latest/migration/

---

**Next Phase**: Generate data-model.md, contracts/, and quickstart.md
