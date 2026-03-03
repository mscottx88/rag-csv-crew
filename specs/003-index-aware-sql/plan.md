# Implementation Plan: Index-Aware SQL Generation

**Branch**: `003-index-aware-sql` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-index-aware-sql/spec.md`

## Summary

The SQL generation agent (`create_sql_generation_task`) has no awareness that PostgreSQL supports full-text search (tsvector/GIN) and vector similarity search (pgvector/HNSW) on data columns. Currently, dynamically created data tables from CSV uploads receive only two indexes (a GIN on `_fulltext` and a B-tree on `_dataset_id`), and the SQL generation task description includes no information about available search capabilities. This plan adds: (1) automatic B-tree index creation on all data columns, (2) tsvector + GIN index creation on text columns, (3) an index metadata registry table, (4) index-capability context injection into the SQL generation task, and (5) data-value embedding generation with HNSW indexes for qualifying text columns.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, Pydantic v2, psycopg[pool] 3.x, CrewAI, OpenAI (text-embedding-3-small)
**Storage**: PostgreSQL 17 with pgvector extension, per-user schema isolation (`{username}_schema`)
**Testing**: pytest (unit, integration, contract), ruff, mypy --strict, pylint 10.00/10.00
**Target Platform**: Linux server (WSL2 development)
**Project Type**: Web application (backend/ + frontend/)
**Performance Goals**: Ingestion time increase <= 50% from index creation (SC-005)
**Constraints**: Thread-based concurrency only (no async/await), all local variables explicitly typed
**Scale/Scope**: CSV files up to 100K+ rows, multiple datasets per user, all rows embedded for qualifying columns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Specification-First | PASS | spec.md complete with user stories, FRs, edge cases, clarifications |
| II. TDD (NON-NEGOTIABLE) | PASS | Implementation will follow red-green-refactor; tests written first |
| III. Independent User Stories | PASS | 5 stories prioritized P1/P2, each independently testable |
| IV. Quality Gates | PASS | All gates will be enforced (ruff, mypy --strict, pylint 10.00, pytest) |
| V. Code Quality Standards | PASS | Strict type hints, PEP 8, docstrings, 100-char lines, top-level imports |
| VI. Concurrency Model | PASS | All code uses synchronous patterns; ThreadPoolExecutor for parallel embedding generation |

**Pre-Phase 0 Gate**: PASS — no violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/003-index-aware-sql/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── dataset.py         # Existing — add IndexMetadata Pydantic model
│   │   └── index_metadata.py  # NEW — IndexMetadataEntry, DataColumnIndexProfile models
│   ├── services/
│   │   ├── ingestion.py       # Existing — not modified (orchestration in api/datasets.py)
│   │   ├── index_manager.py   # NEW — IndexManagerService for index creation + metadata
│   │   └── vector_search.py   # MODIFY — add batch embedding generation for data values
│   ├── db/
│   │   └── schemas.py         # MODIFY — add index_metadata table DDL
│   ├── crew/
│   │   └── tasks.py           # MODIFY — inject index capability context into SQL generation task
│   └── api/
│       └── datasets.py        # MODIFY — integrate index creation into upload flow, cleanup on delete
tests/
├── unit/
│   ├── services/
│   │   ├── test_index_manager.py       # NEW — IndexManagerService unit tests
│   │   └── test_text_to_sql.py         # MODIFY — index context retrieval tests
│   ├── models/
│   │   └── test_index_metadata.py      # NEW — Pydantic model validation tests
│   └── crew/
│       └── test_sql_generation_task.py  # NEW/MODIFY — verify index context in task description
├── integration/
│   ├── test_index_creation.py       # NEW — verify indexes created in PostgreSQL
│   └── test_embedding_generation.py # NEW — verify data value embeddings
└── contract/
    └── test_index_metadata_api.py   # NEW — if index metadata exposed via API
```

**Structure Decision**: Extends existing web application structure. New service (`index_manager.py`) and model (`index_metadata.py`) follow established patterns. No new top-level directories needed.

## Post-Phase 1 Constitution Re-Check

| Principle | Status | Notes |
|---|---|---|
| I. Specification-First | PASS | spec.md complete, plan.md + research.md + data-model.md + contracts/ all generated |
| II. TDD (NON-NEGOTIABLE) | PASS | Test files defined in project structure; TDD cycle will be followed during implementation |
| III. Independent User Stories | PASS | Stories remain independently implementable: P1 (Stories 1-3) can ship without P2 (Stories 4-5) |
| IV. Quality Gates | PASS | Phase 1 design complete: data models defined, API contracts specified, constitution re-checked |
| V. Code Quality Standards | PASS | All Pydantic models use strict typing, StrEnum for constrained values, ConfigDict for from_attributes |
| VI. Concurrency Model | PASS | Embedding generation uses ThreadPoolExecutor (R5); all DB access via synchronous psycopg connection pool |

**Post-Phase 1 Gate**: PASS — no violations detected. Design is constitution-compliant.

## Complexity Tracking

> No constitution violations requiring justification.
