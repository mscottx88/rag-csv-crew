# Contract: SQL Generation Task Context Enhancement

**Feature**: 003-index-aware-sql
**Date**: 2026-03-02
**Module**: `backend/src/crew/tasks.py`

## Modified Function: create_sql_generation_task

### Current Signature (unchanged)

```python
def create_sql_generation_task(
    agent: Agent,
    query_text: str,
    dataset_ids: list[UUID] | None,
    cross_references: list[dict[str, Any]] | None = None,
    search_results: dict[str, Any] | None = None,
    schema_context: str | None = None,
) -> Task:
```

### New Parameter

```python
def create_sql_generation_task(
    agent: Agent,
    query_text: str,
    dataset_ids: list[UUID] | None,
    cross_references: list[dict[str, Any]] | None = None,
    search_results: dict[str, Any] | None = None,
    schema_context: str | None = None,
    index_context: str | None = None,  # NEW
) -> Task:
```

### Context Injection

The `index_context` string is appended to the task description after the schema context and before the requirements section. It is built by `IndexManagerService.build_index_context()`.

### Context Format Specification

```text
INDEX CAPABILITIES (use these for optimal query performance):
================================================================================
Table: products_data

  Column: name (TEXT)
    - B-tree: supports =, <, >, BETWEEN, ORDER BY, LIKE 'prefix%'
    - Full-text search via '_ts_name':
      WHERE _ts_name @@ plainto_tsquery('english', %s)
      ORDER BY ts_rank(_ts_name, plainto_tsquery('english', %s)) DESC
      PREFER full-text search over ILIKE for text searches.
    - Vector similarity via '_emb_name' (1536d):
      ORDER BY _emb_name <=> %s::vector LIMIT 10
      Use for semantic/meaning-based searches.

  Column: price (DOUBLE PRECISION)
    - B-tree: supports =, <, >, BETWEEN, ORDER BY

  Column: description (TEXT)
    - B-tree: supports =, <, >, BETWEEN, ORDER BY, LIKE 'prefix%'
    - Full-text search via '_ts_description':
      WHERE _ts_description @@ plainto_tsquery('english', %s)
      ORDER BY ts_rank(_ts_description, plainto_tsquery('english', %s)) DESC
      PREFER full-text search over ILIKE for text searches.
    - Vector similarity via '_emb_description' (1536d):
      ORDER BY _emb_description <=> %s::vector LIMIT 10
      Use for semantic/meaning-based searches.

  Column: category (TEXT)
    - B-tree: supports =, <, >, BETWEEN, ORDER BY, LIKE 'prefix%'
    - Full-text search via '_ts_category':
      WHERE _ts_category @@ plainto_tsquery('english', %s)

================================================================================
RULES:
- ALWAYS use full-text search (@@, ts_rank) instead of ILIKE for text searches when available
- Use vector similarity (<=> operator) for semantic/meaning-based queries
- You may combine full-text search and vector similarity in a single query
- B-tree indexes are always available for filtering and sorting
- Columns prefixed with '_ts_' are tsvector columns — use @@ operator, not ILIKE
- Columns prefixed with '_emb_' are vector columns — use <=> operator
```

### Runtime Embedding for Vector Queries

When the SQL agent generates a query using vector similarity (e.g., `ORDER BY _emb_col <=> %s::vector`), the `%s` placeholder requires an embedding vector at query execution time. The **query execution layer** (not the SQL agent) is responsible for:

1. Detecting `%s::vector` placeholders in the generated SQL
2. Calling `VectorSearchService.generate_embedding(query_text)` to produce the embedding
3. Passing the resulting embedding as a query parameter alongside other parameters

This follows the existing parameterized query execution pattern. The SQL agent only generates the SQL template with placeholders; parameter resolution happens at execution time.

### Updated Requirements Section

The existing requirements list in the task description gains two new items:

```text
Requirements:
...existing requirements 1-10...
11. PREFER full-text search operators (@@, ts_rank, plainto_tsquery) over ILIKE for text searches when a full-text search index is available on the column. See INDEX CAPABILITIES section.
12. For semantic or meaning-based searches, use vector cosine distance (<=> operator) when vector indexes are available. See INDEX CAPABILITIES section.
```

## Caller Changes

### Modified: Query Processing Flow (services/text_to_sql.py)

The query orchestration code must:

1. After resolving target dataset_ids, call `IndexManagerService.get_index_profiles()` to get index capability data
2. Call `IndexManagerService.build_index_context()` to format the context string
3. Pass `index_context` to `create_sql_generation_task()`

```python
# In the query processing flow:
index_manager: IndexManagerService = IndexManagerService(pool=underlying_pool)
with pool.connection() as conn:
    index_profiles: dict[str, list[DataColumnIndexProfile]] = (
        index_manager.get_index_profiles(conn, username, target_dataset_ids)
    )
    table_names: dict[str, str] = get_table_names_for_datasets(conn, username, target_dataset_ids)

index_context: str = index_manager.build_index_context(index_profiles, table_names)

task: Task = create_sql_generation_task(
    agent=sql_agent,
    query_text=query_text,
    dataset_ids=dataset_ids,
    cross_references=cross_refs,
    search_results=search_results,
    schema_context=schema_ctx,
    index_context=index_context,  # NEW
)
```
