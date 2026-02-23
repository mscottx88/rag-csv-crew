# End-to-End Tests

## Overview

This directory contains end-to-end tests that exercise the **complete backend flow WITHOUT mocks**. These tests make **real API calls** to OpenAI and Anthropic services through CrewAI.

⚠️ **WARNING**: E2E tests consume API quota/credits. Run sparingly.

## What E2E Tests Cover

The E2E tests verify the complete flow:

1. **Authentication** - User login with JWT
2. **Data Ingestion** - CSV upload and schema detection
3. **CrewAI Orchestration** - REAL calls to Claude Opus
4. **SQL Generation** - Natural language → SQL (via Claude)
5. **Query Execution** - SQL against PostgreSQL
6. **Response Generation** - Query results → HTML (via Claude)
7. **Database Persistence** - All data stored correctly

## Running E2E Tests

### Prerequisites

1. Valid API keys configured in `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...  # Valid Claude API key
   OPENAI_API_KEY=sk-proj-...     # Valid OpenAI API key
   ```

2. PostgreSQL running with test database:
   ```bash
   docker-compose up -d
   ```

### Enable E2E Tests

By default, E2E tests are **disabled** to avoid accidental API usage. To enable:

1. Edit `tests/e2e/test_complete_flow.py`
2. Change the `skipif` condition:
   ```python
   @pytest.mark.skipif(
       False,  # Changed from True to False
       reason="E2E test disabled by default..."
   )
   ```

### Run E2E Tests

```bash
# Run only E2E tests (if enabled)
pytest tests/e2e/ -v

# Run specific E2E test
pytest tests/e2e/test_complete_flow.py::TestCompleteFlow::test_complete_query_flow_with_real_apis -v

# Run with detailed output
pytest tests/e2e/ -v -s
```

### Expected Output

When E2E tests run successfully, you'll see:

```
✅ Dataset uploaded: <uuid>
🚀 Submitting query (calling REAL APIs - Claude/OpenAI)...
✅ Query submitted: <uuid>
   Status: completed
✅ SQL Generated (by Claude):
   SELECT * FROM ...
✅ HTML Response Generated (by Claude):
   <article><h1>Query Results</h1>...
🎉 Complete E2E flow succeeded with REAL API calls!
```

## Cost Considerations

Each E2E test run makes approximately:
- **2-4 Claude Opus API calls** (SQL generation + HTML formatting)
- **1-2 OpenAI embedding calls** (if semantic search is used)

**Estimated cost per test run**: $0.02 - $0.10 (depending on query complexity)

## When to Run E2E Tests

✅ **Run E2E tests when:**
- Verifying a major feature works end-to-end
- Before deploying to production
- Debugging issues that mocked tests don't catch
- Testing API integration changes

❌ **Don't run E2E tests for:**
- Regular development (use mocked tests instead)
- CI/CD pipelines (too slow and expensive)
- Refactoring that doesn't touch API logic
- Testing edge cases (use mocked unit tests)

## Troubleshooting

### E2E Tests Skip Automatically

**Cause**: Tests are disabled by default (skipif=True)
**Solution**: Change `skipif=True` to `skipif=False` in test file

### API Quota Exceeded

**Cause**: OpenAI/Anthropic rate limits or quota exhausted
**Solution**:
- Check API usage dashboard
- Add credits to account
- Use mocked tests instead for development

### Tests Timeout

**Cause**: CrewAI processing takes time for complex queries
**Solution**:
- Increase pytest timeout
- Use simpler queries in tests
- Check API service status

## Comparison: E2E vs Mocked Tests

| Aspect | E2E Tests | Mocked Tests |
|--------|-----------|--------------|
| **Speed** | Slow (~30s per test) | Fast (<1s per test) |
| **Cost** | $0.02-$0.10 per run | Free |
| **Reliability** | Real API behavior | Simulated behavior |
| **Use Case** | Final validation | Development/CI |
| **Quota** | Consumes quota | No quota usage |

## Best Practices

1. **Keep E2E tests simple** - Test happy path, not edge cases
2. **Run locally, not in CI** - Too slow and expensive for CI/CD
3. **Use descriptive assertions** - Easy to debug failures
4. **Clean up test data** - Remove datasets after tests
5. **Monitor API usage** - Track costs in OpenAI/Anthropic dashboards

## Architecture Note

E2E tests bypass the `mock_crewai` fixture by using the `@pytest.mark.e2e` marker. See `tests/conftest.py` for implementation details.
