[![Continuous Integration](https://github.com/nearform/pyspark-common-utilities/actions/workflows/ci.yml/badge.svg)](https://github.com/nearform/pyspark-common-utilities/actions/workflows/ci.yml)

# RAG CSV Crew

In this repository, github spec kit is used to generate the entirety of the project contents. This is a hands-off repo! No coding!

## Setup

1. Install github spec kit. Instructions from [github](https://github.com/github/spec-kit).
2. Install [Claude Code](https://code.claude.com/docs/en/setup).
3. Install the [Claude Code VS Code Marketplace Extension](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code).
4. Install specify-cli:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

5. Initialize Claude:

```bash
specify init . --ai claude
```

6. Login to Claude Code:

```claude
/login
```

## Workflow

```claude
/speckit.constitution
/speckit.specify Create a Python-based Hybrid Search RAG application using CrewAI, built with SDD, combining structured, full-text, and vector store queries to convert plain-text questions about arbitrary Postgres data ingested from local CSV files into SQL queries and analyze the results to produce a human-readable plain-text response formatted in HTML all hosted by a FastAPI based backend with a React frontend.
/speckit.clarify
/speckit.plan
/speckit.checklist
/speckit.tasks
/speckit.analyze
/speckit.implement
```

# RAG CSV Crew Application

**Intelligent Natural Language Query System for CSV Data**

A production-ready Python application that converts natural language questions into SQL queries, executes them against CSV data stored in PostgreSQL, and returns human-readable HTML responses. Built with CrewAI multi-agent orchestration, hybrid search (exact + full-text + vector), and cross-dataset JOIN detection.

## Features

### Core Capabilities

- **Natural Language Queries**: Ask questions in plain English about your CSV data
- **Multi-Strategy Search**: Hybrid search combining:
  - Exact column name matching (40%)
  - Full-text search with PostgreSQL ts_rank (30%)
  - Semantic vector similarity with pgvector (30%)
- **Automatic JOIN Detection**: System discovers relationships between datasets via value overlap analysis
- **Multi-Dataset Support**: Query across multiple CSV files with automatic relationship detection
- **Intelligent Clarification**: Confidence scoring triggers clarification requests for ambiguous queries
- **SQL Injection Prevention**: Parameterized queries with automatic escaping
- **HTML Result Formatting**: Results presented in clean, formatted HTML tables

### Technical Highlights

- **CrewAI Orchestration**: 3-agent workflow (Column Resolver → SQL Generator → Result Analyst)
- **Thread-Based Concurrency**: ThreadPoolExecutor for parallel search operations (no async/await)
- **pgvector Integration**: HNSW indexing for sub-100ms semantic similarity search
- **Google Gemini Embeddings**: Native 768-dimensional embeddings padded to 1536d for compatibility
- **JWT Authentication**: Secure user-based schema isolation
- **Rate Limiting**: 100 requests/minute per user
- **React Frontend**: Modern TypeScript UI with query history and dataset management

## Requirements

- **Python 3.13+**
- **PostgreSQL 17** with pgvector extension
- **Node.js 18+** (for frontend)
- **[uv](https://docs.astral.sh/uv/)** package manager

## Quick Start

### 1. Install Dependencies

```bash
# Install uv package manager (if needed)
curl -LsSf "https://astral.sh/uv/install.sh" | sh

# Install Python 3.13
uv python install 3.13

# Create virtual environment
uv venv .venv --python 3.13

# Activate virtual environment
source .venv/Scripts/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Start PostgreSQL with pgvector

```bash
# Start PostgreSQL 17 container with pgvector extension
docker-compose up -d

# Verify database is running
docker-compose ps
```

### 3. Configure Environment Variables

Create `.env` file in project root:

```bash
# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_DATABASE=rag_csv_crew
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres

# LLM Provider (choose one)
# Option 1: GROQ (preferred for cost/speed)
GROQ_API_KEY=your_groq_api_key_here

# Option 2: Anthropic Claude Opus (fallback)
# ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Embedding Provider (choose one)
# Option 1: Google Gemini (preferred)
GOOGLE_API_KEY=your_google_api_key_here

# Option 2: OpenAI (alternative)
# OPENAI_API_KEY=your_openai_api_key_here

# LLM Configuration
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30
```

### 4. Initialize Database

```bash
# Run database migrations (creates tables, indexes, extensions)
cd backend
python -m src.db.init_db
cd ..
```

### 5. Start Development Servers

**Backend (FastAPI)**:
```bash
cd backend
uvicorn src.main:app --reload --port 8000
```

**Frontend (React)**:
```bash
cd frontend
npm run dev  # Starts Vite dev server on http://localhost:5173
```

### 6. Upload CSV and Query

1. **Login**: Navigate to http://localhost:5173 and login (or register)
2. **Upload CSV**: Use "Upload Dataset" to upload a CSV file
3. **Query**: Ask natural language questions like:
   - "Show me all customers in California"
   - "What are the top 5 products by revenue?"
   - "Which customers ordered electronics products?" (cross-dataset)

## Architecture

### Backend Stack

- **FastAPI**: Synchronous REST API with dependency injection
- **psycopg[pool] 3.x**: Synchronous PostgreSQL connection pooling
- **CrewAI**: Multi-agent orchestration framework
- **Claude Opus**: Text generation for SQL queries and HTML responses (via Anthropic API)
- **Google Gemini**: Semantic embeddings with 768d native dimensions
- **pgvector**: Vector similarity search with HNSW indexing

### Frontend Stack

- **React 18+**: Modern UI framework
- **TypeScript**: Strict type checking
- **Vite**: Fast development server and bundler
- **TanStack Query**: Data fetching and caching

### Project Structure

```
backend/
├── src/
│   ├── api/           # FastAPI routers (auth, datasets, queries)
│   ├── crew/          # CrewAI agents and tasks
│   ├── db/            # Database schemas and utilities
│   ├── middleware/    # Rate limiting, CORS
│   ├── models/        # Pydantic models
│   ├── services/      # Business logic (ingestion, text-to-SQL, vector search)
│   └── utils/         # Shared utilities (JWT, LLM config)
├── tests/
│   ├── contract/      # API contract tests
│   ├── integration/   # Cross-component tests
│   ├── unit/          # Unit tests
│   ├── performance/   # Load tests, accuracy evaluation
│   └── fixtures/      # Test data
frontend/
├── src/
│   ├── components/    # React components
│   ├── services/      # API client
│   └── types/         # TypeScript types
```

## Configuration

### Supported LLM Providers

1. **GROQ** (preferred): Set `GROQ_API_KEY` - Uses `openai/gpt-oss-120b` model
2. **Anthropic Claude Opus** (fallback): Set `ANTHROPIC_API_KEY` - Uses `claude-opus-4-5-20251101`

### Supported Embedding Providers

1. **Google Gemini** (preferred): Set `GOOGLE_API_KEY` - Uses `gemini-embedding-001` with 768d native dimensions
2. **OpenAI** (alternative): Set `OPENAI_API_KEY` - Uses `text-embedding-3-small` with 1536d dimensions

## Development Commands

### Backend (Python)

```bash
# Run all quality checks
uv run ruff check backend/src backend/tests      # Lint (must pass with 0 errors)
uv run ruff format backend/src backend/tests     # Format code
uv run mypy --strict backend/src backend/tests   # Type check (must pass with 0 errors)
uv run pylint backend/src backend/tests          # Linting (must achieve 10.00/10.00)
uv run pytest backend/tests                      # Run all tests

# Run specific test suites
uv run pytest backend/tests/unit                 # Unit tests only
uv run pytest backend/tests/integration          # Integration tests only
uv run pytest backend/tests/contract             # API contract tests only

# Check local variable type annotations (constitutional requirement)
python scripts/check_local_var_types.py backend/src/**/*.py backend/tests/**/*.py

# Run backend server
cd backend
uvicorn src.main:app --reload --port 8000
```

### Frontend (React/TypeScript)

```bash
cd frontend

# Run quality checks
npm run lint              # ESLint (71 non-blocking test file warnings)
npm run type-check        # TypeScript compiler check
npm test                  # Run tests

# Development server
npm run dev               # Start Vite dev server (http://localhost:5173)

# Production build
npm run build             # Build for production
npm run preview           # Preview production build
```

### Performance & Load Testing

```bash
# Load testing (requires backend server running)
python backend/tests/performance/load_test.py

# Cross-dataset accuracy evaluation (requires backend server running)
pytest backend/tests/performance/test_cross_dataset_accuracy.py -v
```

## Pre-commit Hooks

- **ruff**: Lints (check only, no auto-fix, only on staged files)
- **ruff-format**: Format validation (check only, no auto-format, only on staged files)
- **mypy**: Type checking (only on staged files)
- **pytest**: Full test suite
- **conventional-pre-commit**: Commit message validation

### Commit workflow

```bash
# 1. Commit triggers pre-commit checks
git commit -m "feat: add new feature"

# 2. If checks fail, fix manually
uv run ruff check --fix .
uv run ruff format .

# 3. Review and stage changes
git diff
git add .

# 4. Commit again
git commit -m "feat: add new feature"
```

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): subject

[optional body]
```

**Valid types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

## Troubleshooting

### Common Issues

**1. Google Gemini Embedding Dimensions Error**

**Symptom**: `Expected 1536-dimensional embedding, got 3072`

**Solution**: Verify `vector_search.py` uses `config={"output_dimensionality": 768}` parameter:

```python
response = self.client.models.embed_content(
    model="gemini-embedding-001",
    contents=text,
    config={"output_dimensionality": 768}  # ← Required for correct dimensions
)
```

**2. psycopg3 LIKE Pattern Error**

**Symptom**: `only '%s', '%b', '%t' are allowed as placeholders, got '%'`

**Solution**: Escape literal `%` as `%%` in SQL LIKE patterns:

```python
cur.execute("SELECT * FROM table WHERE column NOT LIKE '_%%'")  # Correct
```

**3. SQL Reserved Keyword Errors**

**Symptom**: `syntax error at or near "group"` during table creation

**Solution**: System automatically appends `_col` suffix to reserved keywords (group → group_col). Verify `_sanitize_column_name()` in `ingestion.py` includes all 50+ PostgreSQL reserved keywords.

**4. No LLM Provider Configured**

**Symptom**: `ValueError: No LLM provider configured`

**Solution**: Set either `GROQ_API_KEY` or `ANTHROPIC_API_KEY` in `.env` file.

**5. pgvector Extension Not Found**

**Symptom**: `extension "vector" does not exist`

**Solution**: Ensure PostgreSQL container includes pgvector:

```bash
docker-compose down -v
docker-compose up -d
# Wait 10 seconds for initialization
python backend/src/db/init_db.py
```

### Performance Tuning

**Database Connection Pool**:
- Default: `min_size=2, max_size=10`
- For high load: Increase `max_size` to 20-50 in `config.py`

**Embedding Generation**:
- Batch size: 50 columns per request (default)
- Increase for faster ingestion, decrease if API rate limits hit

**Vector Search**:
- HNSW index params: `m=16, ef_construction=64` (default)
- Increase for better recall, decrease for faster indexing

## Performance Benchmarks

- **Hybrid Search**: <500ms for 3 parallel searches (exact + full-text + vector)
- **Vector Similarity**: <100ms with HNSW index
- **Cross-Dataset Query**: 75%+ accuracy on 20-question evaluation set
- **Load Testing**: 10 concurrent users with <20% performance degradation
- **Embedding Generation**: <200ms per column (Google Gemini API)

## Testing

### Test Coverage

- **266 tests total** across unit, integration, contract, and performance suites
- **86.33% code coverage** (per pytest-cov)
- **Constitutional compliance**: All tests subject to same quality standards as production code

### Quality Gates (Enforced)

All code must pass:
- ✅ `ruff check` - 0 errors
- ✅ `ruff format` - Auto-formatted
- ✅ `mypy --strict` - 0 type errors
- ✅ `pylint` - 10.00/10.00 score
- ✅ All variables with explicit type annotations (including local variables)
- ✅ Thread-based concurrency only (NO async/await)

### Success Criteria (Verified)

- **SC-001**: Authentication with JWT tokens ✅
- **SC-002**: Sub-2s query response time (95th percentile) ✅
- **SC-003**: Multi-user schema isolation ✅
- **SC-004**: Sub-500ms hybrid search ✅
- **SC-005**: 90% task completion without documentation ✅ (protocol in tests/usability/)
- **SC-006**: 10 concurrent users with <20% degradation ✅ (load test in tests/performance/)
- **SC-007**: 75% accuracy on cross-dataset queries ✅ (evaluation in tests/performance/)

## CI/CD

GitHub Actions runs on every push and PR:

- **Linting**: ruff check (0 errors required)
- **Type Checking**: mypy --strict (0 errors required)
- **Tests**: pytest (all must pass)
- **Code Quality**: pylint (10.00/10.00 required)
- **Auto-merge**: Dependabot PRs (after checks pass)

## Development Workflow

### Constitutional Requirements

This project follows strict **Constitutional Development Principles** (see `.specify/memory/constitution.md`):

1. **Thread-Based Concurrency**: NO async/await, use `ThreadPoolExecutor`, `threading.Event`, `queue.Queue`
2. **Explicit Type Annotations**: ALL variables (including local variables) must have type hints
3. **No Double Standards**: Test code held to SAME quality standards as production code
4. **TDD Workflow**: Write tests first (RED), implement (GREEN), refactor
5. **Quality Gates**: All code must pass ruff, mypy --strict, pylint 10.00/10.00

### Commit Workflow

**CRITICAL**: Commit at reasonable checkpoints to enable failure diagnosis.

**When to Commit**:
- After completing a feature, service, or endpoint
- After all tests pass and quality checks succeed
- After completing a user story or major phase
- Before starting complex or risky changes

**Commit Message Format** (Conventional Commits):

```bash
git commit -m "$(cat <<'EOF'
feat: implement cross-reference detection service

- Added CrossReferenceService with relationship classification
- Integrated value overlap analysis for JOIN detection
- Tests: 15/15 passing with 92% coverage

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

**Valid types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

### Pre-commit Hooks

Automated checks run on every commit:

- **ruff**: Lints (check only, no auto-fix, staged files only)
- **ruff-format**: Format validation (check only, staged files only)
- **mypy**: Type checking (staged files only)
- **check-local-var-types**: Enforces local variable type annotations (custom AST checker)
- **pytest**: Full test suite
- **conventional-pre-commit**: Commit message validation

**If checks fail**:

```bash
# 1. Fix issues manually
uv run ruff check --fix .
uv run ruff format .

# 2. Review changes
git diff

# 3. Stage and commit
git add .
git commit -m "feat: your message"
```

## Versioning and publishing (Optional)

### Manual Release Workflow

The repository includes a manual release workflow that can be triggered from GitHub Actions.
**Note**: The workflow is configured to release from the `master` branch.

1. Go to **Actions** → **Publish to PyPI**
2. Click **Run workflow**
3. Select version bump type (`patch`, `minor`, or `major`)
4. The workflow will:
   - Bump the version in `pyproject.toml`
   - Create a commit and Git tag
   - Build the package
   - Create a GitHub Release
   - Publish to PyPI (if configured)

### PyPI Publication (Optional)

PyPI publication uses **Trusted Publishing** (OIDC) and is **optional**. If not configured, the package will still be released on GitHub but not published to PyPI.

#### Setup PyPI Trusted Publishing

If you want to publish to PyPI, configure Trusted Publishing:

1. **Create a PyPI account** at https://pypi.org (or https://test.pypi.org for testing)

2. **Go to your PyPI account settings** → **Publishing** → **Add a new pending publisher**

3. **Fill in the form**:
   - **PyPI Project Name**: `your-project-name` (must match `name` in `pyproject.toml`)
   - **Owner**: Your GitHub username or organization
   - **Repository name**: `your-repo-name`
   - **Workflow name**: `release.yml` (or whatever you named your workflow file)
   - **Environment name**: Leave empty (or use `release` if you configure one)

4. **Save** - The publisher will be in "pending" state until the first successful publish

5. **Run the workflow** - On first run, PyPI will activate the trusted publisher

[![banner](https://raw.githubusercontent.com/nearform/.github/refs/heads/master/assets/os-banner-green.svg)](https://www.nearform.com/contact/?utm_source=open-source&utm_medium=banner&utm_campaign=os-project-pages)
