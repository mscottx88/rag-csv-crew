# Implementation Plan: Hybrid Search RAG for CSV Data

**Branch**: `001-rag-csv-crew` | **Date**: 2026-02-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-rag-csv-crew/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a hybrid search RAG (Retrieval-Augmented Generation) application that allows users to upload CSV files and ask natural language questions about the data. The system combines structured SQL queries, full-text search, and semantic vector search to provide intelligent answers formatted in HTML. Multi-user system with username-based authentication and per-user database schema isolation.

**Core Capabilities**:
- CSV file upload and ingestion into PostgreSQL with schema inference
- Natural language question processing using CrewAI multi-agent orchestration
- Hybrid search combining exact matches, full-text search (PostgreSQL `tsquery`), and vector similarity (pgvector)
- Text-to-SQL query generation for structured data analysis
- AI-generated HTML-formatted responses from query results
- Web interface for file management, query submission, and result display
- Multi-tenancy with per-user PostgreSQL schemas

**Clarified Decisions** (from `/speckit.clarify`):
- **Deployment**: Demo/prototype environment (not production-ready)
- **Auth Model**: Username-only (no password), single-role permission model
- **LLM Failures**: Automatic retry with exponential backoff (3 attempts)
- **Data Retention**: User-controlled deletion, no automatic expiration
- **API Versioning**: No versioning for MVP (breaking changes allowed)

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**:
- **Backend Framework**: FastAPI (synchronous REST API)
- **Database**: PostgreSQL 17 with pgvector extension (vector embeddings)
- **AI Orchestration**: CrewAI (multi-agent RAG workflow)
- **LLM Integration**: OpenAI API or compatible (text generation, embeddings)
- **Data Validation**: Pydantic v2 (models, config, validation)
- **Database Driver**: psycopg[pool] 3.x (synchronous connection pooling)
- **Frontend Framework**: React 18+ with TypeScript
- **Frontend Build**: Vite (dev server, bundler)

**Storage**:
- PostgreSQL database with:
  - User-specific schemas (isolation via `<username>_schema`)
  - CSV data tables (dynamic schema per upload)
  - Vector embeddings (pgvector for semantic search)
  - Query history and metadata tables

**Testing**:
- **Framework**: pytest
- **Coverage**: pytest-cov
- **Contract**: OpenAPI validation against FastAPI schema
- **Integration**: PostgreSQL testcontainers for isolated testing
- **Unit**: Mocked dependencies, isolated business logic

**Target Platform**: Linux server (Docker containerized for deployment)

**Project Type**: Web application (FastAPI backend + React frontend)

**Performance Goals**:
- CSV ingestion: <10s for files <100MB, progress updates for larger
- Query response: <5s for typical queries (<100K rows)
- Query timeout: 30s maximum with user cancellation
- Concurrent users: 10+ without degradation

**Constraints**:
- Username-only authentication (no password, demo/prototype environment)
- No file size limits (streaming ingestion for large files)
- English language only for natural language queries
- LLM API retry with exponential backoff (1s, 2s, 4s delays, 3 attempts)
- 30-second query timeout with manual cancellation
- 3-retry connection loss recovery with exponential backoff

**Scale/Scope**:
- Multi-user with per-schema isolation
- User-controlled data retention (no automatic expiration)
- Query history persistence
- Support for multi-file cross-dataset queries
- Single-role permission model (all users equal)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 (Pre-Planning) ✓

- [x] **Specification complete**: spec.md with 4 user stories, 47 functional requirements, 11 success criteria
- [x] **Specification approved**: Clarifications session completed with 10 resolved ambiguities (5 from previous session + 5 new)
- [x] **Test cases defined**: Acceptance scenarios (Given/When/Then) for all user stories
- [x] **Constitution compliance verified**: All quality gates understood

### Phase 1 (Design) ✓ COMPLETE

- [x] **Technical plan documented**: This file (plan.md)
- [x] **Data models defined**: data-model.md with entities, schemas, relationships
- [x] **API contracts specified**: /contracts/openapi.yaml with complete API specification
- [x] **Constitution re-check passed**: All design artifacts follow constitution requirements

#### Constitution Compliance Analysis

**I. Specification-First Development** ✓
- Complete specification exists (spec.md) with user scenarios, functional requirements, edge cases, and key entities
- Planning follows specification (this phase)

**II. Test-Driven Development** ✅
- TDD workflow ENFORCED in tasks.md (updated 2026-02-02)
- Tests written FIRST in Phase XA (RED phase) before any implementation
- User approval gates (Phase XC) required before implementation begins
- Implementation in Phase XD (GREEN phase) makes tests pass
- See tasks.md: T011-TEST through T028-TEST (Phase 2A), T029-VERIFY, T030-APPROVAL, T011-IMPL through T028-IMPL (Phase 2D)

**III. Independent User Stories** ✓
- 4 prioritized user stories (P1, P2, P2, P3)
- Each story is independently testable and delivers standalone value:
  - P1: CSV upload + basic querying (MVP)
  - P2: Intelligent multi-strategy search
  - P2: Interactive web interface
  - P3: Multi-file cross-dataset queries

**IV. Quality Gates** ✅
- Pre-planning gates passed (Phase 0) ✓
- Phase 1 gates: Completed ✓ (includes T010a constitution re-check)
- Phase 2+ gates: ENFORCED after each phase per tasks.md (updated 2026-02-02)
  - Phase 2E: Quality Gate (T031-QA through T038-QA) - ruff, mypy, pylint 10.00/10.00, pytest
  - Phase 3E: Quality Gate (T090-QA through T097-QA) - all checks repeated
  - Phase 4F, 5F, 6F: Quality gates continue through all phases
  - Phase 7: Final validation only (no deferred quality checks)

**V. Code Quality Standards** 📋
- Python 3.13+ ✓
- ruff (linting/formatting) - will be configured
- mypy --strict (type checking) - will be configured
- pylint (10.00/10.00 required) - will be configured
- Pylance (VS Code type checking) - will be configured
- PEP 8 compliance - enforced by ruff + pylint
- Type hints: ALL functions, parameters, return values, and local variables must have explicit type annotations
- No inline imports (all imports at top of file)
- Pydantic v2 for data models ✓
- Test code quality: Same standards as production code (NO DOUBLE STANDARDS)

**VI. Concurrency Model** ✓
- Thread-based concurrency ONLY (ThreadPoolExecutor, threading.Event, queue.Queue)
- NO async/await patterns anywhere in codebase
- Synchronous FastAPI route handlers (def, not async def)
- Synchronous database connections (psycopg ConnectionPool, not AsyncConnectionPool)
- Thread pool for parallel I/O operations

### Phase 2 (Implementation) - NOT STARTED

Will require:
- All linting passes (ruff on src/ AND tests/)
- Type checking passes (mypy --strict on src/ AND tests/)
- Pylint score 10.00/10.00 (on src/ AND tests/)
- Pylance analysis: Zero errors and warnings
- All tests pass (pytest)
- Test code quality verified (same standards as production)
- Docker Desktop running for integration tests
- PostgreSQL + pgvector container verified

### Complexity Justification

No constitutional violations requiring justification. Project follows standard patterns:
- Single web application (backend + frontend)
- Standard Python project structure (src/, tests/)
- Pydantic for models
- pytest for testing
- Thread-based concurrency (no async/await)
- No custom complexity patterns introduced

## Project Structure

### Documentation (this feature)

```text
specs/001-rag-csv-crew/
├── spec.md              # Feature specification (COMPLETE)
├── plan.md              # This file (COMPLETE)
├── research.md          # Phase 0 research (COMPLETE)
├── data-model.md        # Phase 1 data design (COMPLETE)
├── quickstart.md        # Phase 1 usage guide (COMPLETE)
├── contracts/           # Phase 1 API contracts (COMPLETE)
│   └── openapi.yaml     # FastAPI OpenAPI schema
└── tasks.md             # Phase 2 task list (COMPLETE via /speckit.tasks)
```

### Source Code (repository root)

```text
# Web application structure (FastAPI backend + React frontend)

backend/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── models/                    # Pydantic models
│   │   ├── __init__.py
│   │   ├── user.py               # User, auth models
│   │   ├── dataset.py            # Dataset, CSV file models
│   │   ├── query.py              # Query, response models
│   │   └── config.py             # App configuration (Pydantic BaseSettings)
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   ├── auth.py               # Username-only authentication
│   │   ├── ingestion.py          # CSV upload, schema detection, ingestion
│   │   ├── hybrid_search.py      # Hybrid search orchestration
│   │   ├── text_to_sql.py        # Natural language to SQL conversion
│   │   ├── vector_search.py      # pgvector semantic search
│   │   ├── response_generator.py # HTML response formatting
│   │   └── schema_manager.py     # Per-user schema creation/management
│   ├── api/                       # FastAPI routers
│   │   ├── __init__.py
│   │   ├── auth.py               # /auth endpoints (login)
│   │   ├── datasets.py           # /datasets endpoints (upload, list, delete)
│   │   ├── queries.py            # /queries endpoints (submit, cancel, history)
│   │   └── health.py             # /health endpoint
│   ├── db/                        # Database utilities
│   │   ├── __init__.py
│   │   ├── connection.py         # Connection pool management
│   │   ├── migrations.py         # Schema migration utilities
│   │   └── retry.py              # Connection retry logic (exponential backoff)
│   ├── crew/                      # CrewAI agents and tasks
│   │   ├── __init__.py
│   │   ├── agents.py             # SQL generator, searcher, analyst agents
│   │   ├── tasks.py              # CrewAI task definitions
│   │   └── tools.py              # Custom tools for agents
│   └── utils/                     # Shared utilities
│       ├── __init__.py
│       ├── logging.py            # Structured logging setup
│       └── validators.py         # Custom validators

tests/
├── __init__.py
├── conftest.py                    # pytest fixtures, PostgreSQL container setup
├── contract/                      # API contract tests
│   ├── __init__.py
│   ├── test_auth_contract.py
│   ├── test_datasets_contract.py
│   └── test_queries_contract.py
├── integration/                   # Cross-component integration tests
│   ├── __init__.py
│   ├── test_csv_ingestion_flow.py
│   ├── test_query_flow.py
│   └── test_multi_user_isolation.py
└── unit/                          # Unit tests for individual components
    ├── __init__.py
    ├── models/
    │   └── test_dataset_model.py
    ├── services/
    │   ├── test_ingestion.py
    │   ├── test_text_to_sql.py
    │   └── test_schema_manager.py
    └── utils/
        └── test_validators.py

frontend/
├── src/
│   ├── App.tsx                    # Main app component
│   ├── main.tsx                   # Entry point
│   ├── components/                # React components
│   │   ├── Auth/
│   │   │   └── Login.tsx
│   │   ├── Dataset/
│   │   │   ├── UploadForm.tsx
│   │   │   └── DatasetList.tsx
│   │   ├── Query/
│   │   │   ├── QueryInput.tsx
│   │   │   ├── QueryHistory.tsx
│   │   │   └── ResultDisplay.tsx
│   │   └── Layout/
│   │       ├── Header.tsx
│   │       └── Sidebar.tsx
│   ├── services/                  # API client services
│   │   ├── api.ts                # Axios client configuration
│   │   ├── auth.ts               # Auth API calls
│   │   ├── datasets.ts           # Dataset API calls
│   │   └── queries.ts            # Query API calls
│   ├── types/                     # TypeScript types
│   │   ├── user.ts
│   │   ├── dataset.ts
│   │   └── query.ts
│   └── utils/
│       └── formatters.ts
├── tests/
│   └── components/
│       └── QueryInput.test.tsx
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json

# Root configuration files
pyproject.toml                      # Python dependencies, tool configs
.pylintrc or pyproject.toml         # Pylint configuration
ruff.toml                           # Ruff configuration
.gitignore
.editorconfig                       # Line endings (LF), encoding (UTF-8)
.gitattributes                      # Line ending normalization
docker-compose.yml                  # PostgreSQL + pgvector container
README.md                           # Project overview, setup instructions
```

**Structure Decision**: Web application structure selected based on:
1. Feature spec explicitly mentions "FastAPI backend with a React frontend"
2. Clear separation of concerns between API layer and UI layer
3. Independent deployment of backend and frontend (backend can be used standalone via API)
4. Frontend can be served statically or via separate server (Vite dev server for development)

## Complexity Tracking

No constitutional violations requiring justification.

**Rationale**: Project follows standard patterns defined in the constitution:
- Web application structure (explicitly supported: backend/ + frontend/)
- Python 3.13 with mandatory tooling (ruff, mypy, pylint, Pylance, pytest)
- Pydantic v2 for data models
- Thread-based concurrency (no async/await)
- Single responsibility: Each service handles one concern
- No custom abstractions or patterns beyond what constitution defines

---

**Phase 0 & 1 Status**: ✅ **COMPLETE**
- research.md generated with technology decisions and rationale
- data-model.md generated with entities, schemas, relationships
- contracts/openapi.yaml generated with complete API specification
- quickstart.md generated with setup and usage instructions

**Next Steps**:
1. ✅ Phase 0: research.md complete
2. ✅ Phase 1: data-model.md, contracts/, quickstart.md complete
3. ✅ Phase 1: Agent context updated (CLAUDE.md) - technologies and structure documented
4. ✅ Phase 2 Planning: tasks.md generated (224 tasks with TDD workflow)
5. ⏭️ Phase 2 Execution: Ready to begin implementation via /speckit.implement
