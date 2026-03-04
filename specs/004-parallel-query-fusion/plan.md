# Implementation Plan: Parallel Query Fusion

**Branch**: `004-parallel-query-fusion` | **Date**: 2026-03-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-parallel-query-fusion/spec.md`

## Summary

The system currently generates a single SQL query per user question. This plan adds parallel multi-strategy query dispatch — structured SQL (B-tree), full-text search (tsvector/GIN), and vector similarity (pgvector/HNSW) — where each strategy runs concurrently via ThreadPoolExecutor. Results are fused using Reciprocal Rank Fusion (RRF, k=60) with ctid-based deduplication, then formatted into a single unified HTML response. Strategy applicability is determined at query time from existing `index_metadata`. A single LLM call produces all strategy SQL blocks, keeping API cost constant.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, Pydantic v2, psycopg[pool] 3.x, CrewAI, Claude Opus (Anthropic API), OpenAI (text-embedding-3-small)
**Storage**: PostgreSQL 17 with pgvector extension, per-user schema isolation (`{username}_schema`)
**Testing**: pytest (unit, integration, contract), ruff, mypy --strict, pylint 10.00/10.00
**Target Platform**: Linux server (WSL2 development)
**Project Type**: Web application (backend/ + frontend/)
**Performance Goals**: Total query latency <= 130% of single-strategy baseline (NFR-001)
**Constraints**: Thread-based concurrency only (no async/await), per-strategy timeout 30s (NFR-002), per-strategy row limit 50 (FR-011)
**Scale/Scope**: Up to 3 parallel strategy queries per user request, datasets with varying index profiles

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Specification-First | PASS | spec.md complete with 4 user stories, 19 FRs, 3 NFRs, 5 SCs, 6 edge cases, 4 clarifications |
| II. TDD (NON-NEGOTIABLE) | PASS | Implementation will follow red-green-refactor; tests written first |
| III. Independent User Stories | PASS | 4 stories prioritized P1/P2, each independently testable |
| IV. Quality Gates | PASS | All gates will be enforced (ruff, mypy --strict, pylint 10.00, pytest) |
| V. Code Quality Standards | PASS | Strict type hints, PEP 8, docstrings, 100-char lines, top-level imports |
| VI. Concurrency Model | PASS | All parallel execution uses ThreadPoolExecutor; no async/await |

**Pre-Phase 0 Gate**: PASS — no violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/004-parallel-query-fusion/
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
│   │   └── fusion.py               # NEW — StrategyType, StrategySQL, StrategyResult, FusedResult, FusedRow
│   ├── services/
│   │   ├── text_to_sql.py           # MODIFY — multi-strategy SQL generation orchestration
│   │   ├── query_execution.py       # MODIFY — add execute_strategies_parallel() method
│   │   ├── result_fusion.py         # NEW — RRF scoring, ctid dedup, result merging
│   │   ├── strategy_dispatcher.py   # NEW — strategy selection, dispatch, and coordination
│   │   └── response_generator.py    # MODIFY — accept FusedResult, strategy attribution in prompt
│   ├── crew/
│   │   └── tasks.py                 # MODIFY — multi-strategy SQL generation prompt with labeled blocks
│   └── api/
│       └── queries.py               # MODIFY — integrate multi-strategy flow into _execute_sql_query
tests/
├── unit/
│   ├── models/
│   │   └── test_fusion_models.py    # NEW — Pydantic model validation tests
│   ├── services/
│   │   ├── test_result_fusion.py    # NEW — RRF scoring, dedup, merging tests
│   │   ├── test_strategy_dispatcher.py  # NEW — strategy selection and dispatch tests
│   │   ├── test_query_execution.py  # NEW — parallel execution tests
│   │   ├── test_text_to_sql.py      # MODIFY — multi-strategy parse tests
│   │   └── test_response_generator.py  # MODIFY — attribution and ctid exclusion tests
│   └── crew/
│       └── test_sql_generation_task.py  # MODIFY — multi-strategy prompt tests
├── integration/
│   └── test_parallel_query.py       # NEW — end-to-end multi-strategy query tests
│       # Covers US acceptance scenarios:
│       # US1 AS1: 3 strategies dispatched in parallel (verified via logs)
│       # US1 AS2: Only applicable strategies dispatched (B-tree only dataset)
│       # US1 AS3: One strategy fails, others still return results
│       # US2 AS1: Overlapping rows fused with boosted RRF scores
│       # US2 AS2: Single-strategy returns as-is
│       # US2 AS3: Row in all 3 strategies gets 3-way RRF score
│       # US3 AS1: Multi-strategy HTML with attribution summary
│       # US3 AS2: Single-strategy HTML without attribution
│       # US3 AS3: Zero results across all strategies → helpful message
│       # US4 AS1: FTS but no vector → structured + FTS only
│       # US4 AS2: B-tree only → structured only
│       # US4 AS3: Cross-dataset different index profiles
└── contract/
    (no new contract tests — changes are internal pipeline modifications)
```

**Structure Decision**: Extends existing web application structure. New service files (`result_fusion.py`, `strategy_dispatcher.py`) and model file (`fusion.py`) follow established patterns. No new top-level directories needed.

## Post-Phase 1 Constitution Re-Check

| Principle | Status | Notes |
|---|---|---|
| I. Specification-First | PASS | spec.md complete, plan.md + research.md + data-model.md + contracts/ all generated |
| II. TDD (NON-NEGOTIABLE) | PASS | Test files defined in project structure; TDD cycle will be followed during implementation |
| III. Independent User Stories | PASS | Stories remain independently implementable: P1 (US1+US2) can ship without P2 (US3+US4) |
| IV. Quality Gates | PASS | Phase 1 design complete: data models defined, contracts specified, constitution re-checked |
| V. Code Quality Standards | PASS | All Pydantic models use strict typing, StrEnum, ConfigDict, Field constraints |
| VI. Concurrency Model | PASS | All parallel execution uses ThreadPoolExecutor with timeout and cancellation via threading.Event |

**Post-Phase 1 Gate**: PASS — no violations detected. Design is constitution-compliant.

## Complexity Tracking

> No constitution violations requiring justification.
