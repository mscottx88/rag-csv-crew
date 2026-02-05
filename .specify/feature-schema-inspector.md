# Feature: Schema Inspector Agent & Metadata Precomputation

## Overview
Enhance the RAG CSV Crew system with two major capabilities:
1. Schema Inspector Agent - Provides database schema context to query generation
2. Metadata Precomputation - Compute and store column statistics during CSV upload

## Requirements

### Schema Inspector Agent
- CrewAI agent that inspects database schemas and provides context
- Query available datasets, table names, column types, relationships
- Integrate with Text-to-SQL agent for context-aware SQL generation

### Metadata Precomputation
- Compute column statistics during CSV upload (min/max, distinct counts, sample values)
- Store metadata in new `column_metadata` table
- Enrich embeddings with metadata context for better semantic search
- Use thread-based parallelization for performance

## Technical Constraints
- Thread-based concurrency only (no async/await)
- All code must pass: ruff, mypy --strict, pylint 10.00/10
- Maintain <5s metadata computation for 50-column datasets
- Schema inspection must complete in <2s for typical queries

## Success Criteria
- SQL queries reference correct table/column names (100% accuracy)
- Metadata available for all columns after upload
- Clarification responses include actual value suggestions
- Improved confidence scores and query accuracy
