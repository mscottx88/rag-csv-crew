# Contract: Response Generator Enhancement

**Feature**: 004-parallel-query-fusion
**Date**: 2026-03-03
**Module**: `backend/src/services/response_generator.py`

## Modified Class: ResponseGenerator

### Current Method Signature (pre-feature)

```python
def generate_html_response(
    self,
    query_text: str,
    query_results: dict[str, Any],
    _query_id: UUID | str,
    confidence_threshold: float = 0.6,
) -> dict[str, Any]:
```

### Modified Method: generate_html_response

Add `fused_result` keyword-only parameter. All existing parameters are preserved for backward compatibility.

```python
def generate_html_response(
    self,
    query_text: str,
    query_results: dict[str, Any],
    _query_id: UUID | str,
    confidence_threshold: float = 0.6,
    *,
    fused_result: FusedResult | None = None,  # NEW
) -> dict[str, Any]:
    """Generate HTML response from query results.

    When fused_result is provided (multi-strategy path):
    - The CrewAI Result Analyst agent receives the fused rows (ctid excluded)
      along with strategy attribution metadata.
    - If fused_result.is_multi_strategy is True, the prompt instructs the agent
      to include an attribution summary above the data table (FR-014).
    - If fused_result.is_multi_strategy is False (single strategy contributed),
      no attribution is shown (FR-015).

    When fused_result is None (single-strategy path / fallback):
    - Existing behavior is preserved exactly as before this feature.

    Args:
        query_text: The user's original query.
        query_results: Raw query result dict (rows, columns, row_count).
        _query_id: Query identifier (existing parameter, preserved).
        confidence_threshold: Confidence threshold (existing parameter, preserved).
        fused_result: Optional FusedResult for multi-strategy responses.

    Returns:
        {"html_content": str, "plain_text": str, "confidence_score": float}
    """
```

### ctid Exclusion (FR-013)

The `fused_result.rows[*].data` dicts already exclude system columns (ctid, _ts_*, _emb_*, rank, similarity) — this filtering happens in the ResultFusionService before the FusedResult is constructed. The response generator receives clean user data only.

### Attribution Format (FR-014)

When `fused_result.is_multi_strategy` is True, the prompt to the CrewAI Result Analyst agent includes:

```text
STRATEGY ATTRIBUTION (include this note above the data table):
Results from {strategy1} ({N1} rows), {strategy2} ({N2} rows), and {strategy3} ({N3} rows).
```

Strategy names are human-readable:
- `structured` → "structured query"
- `fulltext` → "full-text search"
- `vector` → "semantic search"

The attribution is a single line of plain text above the HTML data table. The agent formats it within the HTML output.

### Single-Strategy Pass-Through (FR-015)

When `fused_result.is_multi_strategy` is False or `fused_result` is None, no attribution is included. The response looks identical to pre-feature output.

### Zero-Results Handling (US3 AS3)

When `fused_result.total_row_count == 0`, the existing zero-results behavior applies: a helpful message suggesting query refinements. No strategy attribution is shown for zero results.

### Caller Integration

```python
# In _execute_sql_query or equivalent (queries.py):
if fused_result is not None:
    # Convert FusedResult to the dict format expected by generate_html_response
    query_result_dict: dict[str, Any] = {
        "rows": [row.data for row in fused_result.rows],
        "columns": fused_result.columns,
        "row_count": fused_result.total_row_count,
    }
    response: dict[str, Any] = response_generator.generate_html_response(
        query_text=query_text,
        query_results=query_result_dict,
        _query_id=query_id,
        fused_result=fused_result,
    )
else:
    # Single-strategy path (existing flow, unchanged)
    response = response_generator.generate_html_response(
        query_text=query_text,
        query_results=query_result,
        _query_id=query_id,
    )
```
