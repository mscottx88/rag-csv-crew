# python-sdd-2 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-26

**Constitution**: This file reflects HOW principles are applied. For WHAT principles govern this project, see [constitution.md](.specify/memory/constitution.md).

## Active Technologies

- Python 3.13 with FastAPI (synchronous REST API), Pydantic v2 (data validation), psycopg[pool] 3.x (synchronous connection pooling) (001-rag-csv-crew)
- PostgreSQL 17 with pgvector extension for vector similarity search (001-rag-csv-crew)
- CrewAI for multi-agent RAG workflow orchestration (001-rag-csv-crew)
- Claude Opus (via Anthropic API) for text generation (SQL queries, HTML responses) (001-rag-csv-crew)
- OpenAI text-embedding-3-small for semantic search embeddings (001-rag-csv-crew)
- React 18+ with TypeScript, Vite (dev server, bundler) for frontend (001-rag-csv-crew)
- pytest for testing, ruff for linting/formatting, mypy --strict for type checking, pylint (10.00/10.00 required) (001-rag-csv-crew)

## Project Structure

```text
backend/
├── src/           # FastAPI application code
│   ├── models/    # Pydantic models
│   ├── services/  # Business logic
│   ├── api/       # FastAPI routers
│   ├── db/        # Database utilities
│   ├── crew/      # CrewAI agents and tasks
│   └── utils/     # Shared utilities
tests/
├── contract/      # API contract tests
├── integration/   # Cross-component integration tests
└── unit/          # Unit tests
frontend/
├── src/           # React application code
│   ├── components/
│   ├── services/  # API client services
│   ├── types/     # TypeScript types
│   └── utils/
└── tests/
```

## Commands

**Backend (Python)**:
- `pytest` - Run all tests (unit, integration, contract)
- `ruff check backend/src backend/tests` - Run linting
- `ruff format backend/src backend/tests` - Format code
- `mypy --strict backend/src backend/tests` - Type checking
- `pylint backend/src backend/tests` - Additional linting (must achieve 10.00/10.00)
- `docker-compose up -d` - Start PostgreSQL + pgvector container

**Frontend (React/TypeScript)**:
- `cd frontend && npm install` - Install dependencies
- `cd frontend && npm run dev` - Start Vite dev server
- `cd frontend && npm run build` - Build for production
- `cd frontend && npm test` - Run frontend tests

## Git Workflow - Checkpoint Commits

**CRITICAL: Commit changes at reasonable checkpoints to enable diagnosis of critical failures.**

### When to Commit

You MUST create git commits at the following checkpoints:

1. **Unit of Work Completed**: After implementing a complete feature, service, or endpoint
2. **Quality Gate Passed**: After all tests pass and quality checks succeed (ruff, mypy, pylint)
3. **Phase Boundary**: After completing a user story or major phase (e.g., "Phase 3 complete")
4. **Refactoring Checkpoint**: After completing a significant refactoring task
5. **Before Major Changes**: Before starting a complex or risky change
6. **Error Recovery Points**: After fixing a critical bug or recovering from a failure

### Commit Message Format

Use descriptive commit messages that explain WHAT changed and WHY:

```bash
git commit -m "$(cat <<'EOF'
feat: implement text-to-SQL service with CrewAI

- Added TextToSQLService with SQL generation agent
- Integrated Claude Opus API for natural language processing
- Added parameterized query generation for security
- Tests: 95% coverage on service methods

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

### Commit Frequency Guidelines

- **Minimum**: Commit after each completed task in tasks.md (e.g., T077-T089)
- **Ideal**: Commit after each file or logical group of files is implemented and tested
- **Maximum**: Never go more than 1 hour without a commit if actively working

### Why This Matters

**Checkpoint commits enable:**

1. **Failure Diagnosis**: Compare working vs broken states using `git diff`
2. **Selective Rollback**: Revert specific changes without losing all progress
3. **Progress Tracking**: Clear history of what was completed when
4. **Collaboration**: Other developers (or future Claude sessions) can pick up where you left off
5. **Code Review**: Smaller, focused commits are easier to review than large diffs

### Enforcement

- **Before Quality Gates**: Always commit working code before running quality checks
- **After Quality Gates**: Always commit after achieving passing quality gates
- **During Implementation**: Commit each file or service as it's completed
- **Session Boundaries**: Always commit at the end of a work session

**Bottom line**: Commit early, commit often. Each commit should represent a coherent, working checkpoint.

## Code Style

**Python 3.13**: Follow strict constitutional standards (ruff, mypy --strict, pylint 10.00/10.00, thread-based concurrency)
**TypeScript**: Follow React + TypeScript best practices with strict type checking

### ⚠️ CRITICAL: NO DOUBLE STANDARDS - ALL PYTHON CODE (NON-NEGOTIABLE)

**ALL Python files MUST meet the EXACT SAME strict quality standards. ZERO EXCEPTIONS.**

This is a core constitutional principle (see constitution.md "Test Code Quality Requirements").

#### What "ALL Python files" means:

- ✅ `src/` - Production code
- ✅ `tests/` - Test code (unit, integration, contract)
- ✅ `scripts/` - Utility scripts, benchmarks, migrations, data processing
- ✅ `tools/` - Development tools, code generators, analyzers
- ✅ `examples/` - Example code, demos, tutorials
- ✅ `docs/` - Documentation code snippets (if executable)
- ✅ `benchmarks/` - Performance benchmarks
- ✅ `config/` - Configuration scripts
- ✅ Root-level Python files - `setup.py`, `conftest.py`, etc.
- ✅ **ANY `.py` file ANYWHERE in the repository**

#### What you MUST NEVER do:

- ❌ **NEVER** relax mypy, pylint, or ruff rules for ANY Python files
- ❌ **NEVER** add mypy overrides like `disallow_untyped_defs = false` for ANY directory
- ❌ **NEVER** exclude ANY Python files from quality checks in .pre-commit-config.yaml
- ❌ **NEVER** treat ANY Python code as "second-class" code
- ❌ **NEVER** say "it's just a script" or "it's just a benchmark" as justification for lower quality
- ❌ **NEVER** add `# type: ignore` without specific, justified type codes
- ❌ **NEVER** skip type hints because "the file is small" or "it's temporary"

#### Requirements for EVERY Python file in the repository:

**Type Annotations** (Required):

- ALL functions must have explicit return type annotations (including `-> None`)
- ALL function parameters must have type annotations
- ALL module-level variables MUST have explicit type annotations
- ALL local variables MUST have explicit type annotations (even when the type appears obvious from assignment)
  - Including variables in test functions: `result: SomeType = function_call()`
  - Including loop variables where practical: `item: ItemType`
  - Including comprehension results: `items: list[str] = [x for x in source]`
- Generator types must be fully specified: `Generator[YieldType, SendType, ReturnType]`
- Type hints are required in ALL cases unless there is a specific technical reason preventing it

**Verification Protocol** (CRITICAL):
When verifying type hint compliance, you MUST check ALL Python files systematically:

1. Run `mypy --strict src/ tests/ scripts/` to catch function-level violations
2. Run `python scripts/check_local_var_types.py src/**/*.py tests/**/*.py scripts/**/*.py` to catch missing local variable type hints
3. **AUTOMATED ENFORCEMENT**: The pre-commit hook `check-local-var-types` automatically enforces local variable type annotations
4. Search for patterns: `= ` without `: Type =` on the same line
5. Test files are ESPECIALLY prone to missing local variable hints - the checker double-checks every test function

**Static Analysis** (Required):

- `mypy --strict`: MUST pass with ZERO errors
- `pylint`: MUST achieve 10.00/10.00 score
- `ruff check`: MUST pass with ZERO violations
- `ruff format`: MUST pass (code auto-formatted)
- `python scripts/check_local_var_types.py <files>`: MUST pass (enforces local variable type hints)

**Automated Enforcement** (NEW):

Since mypy, ruff, and pylint don't enforce local variable type annotations (they allow type inference per PEP 484), this project uses a **custom AST-based checker**:

- **Script**: `scripts/check_local_var_types.py`
- **Pre-commit hook**: `check-local-var-types` (runs automatically on commit)
- **Purpose**: Enforces "ALL local variables MUST have explicit type annotations"
- **Usage**: `python scripts/check_local_var_types.py src/**/*.py tests/**/*.py scripts/**/*.py`

The checker uses a **pragmatic approach** to balance strictness with practicality:
- ✅ **Allows**: Obvious constructor calls like `config = DatabaseConfig(...)` (self-documenting)
- ❌ **Requires annotations**: Non-obvious types like `peak_mb = peak / (1024 * 1024)`, `result = some_function()`

**Exemptions** (allowed by the checker):
- **Obvious constructor calls**: `config = ClassName(...)`, `obj = module.Type(...)` (pragmatic)
- Unpacking assignments: `_, x = func()` (tuple returns)
- Loop variables in for loops (optional per constitution: "where practical")
- Context manager targets: `with ... as var:`
- Exception handlers: `except Exception as e:`
- Augmented assignments: `x += 1` (variable already exists)

**Code Standards** (Required):

- PEP 8: ALL imports at top of file (no inline imports except where absolutely necessary with justification)
- **Test File Import Convention** (MANDATORY):
  - ✅ **CORRECT**: All imports at the global level (top of file)
    ```python
    from backend.src.services.auth import generate_jwt_token

    def test_configurable_expiration(self) -> None:
        token: str = generate_jwt_token(...)
    ```
  - ❌ **INCORRECT**: Imports inside test functions
    ```python
    def test_configurable_expiration(self) -> None:
        from backend.src.services.auth import generate_jwt_token  # NEVER DO THIS
    ```
  - **Rationale**: Global imports improve readability, enable static analysis, and follow PEP 8 standards
  - **Exceptions**: ZERO - test files have NO special exemption from PEP 8 import rules
- Docstrings: ALL public functions, classes, and modules
- Line length: Maximum 100 characters
- File encoding: UTF-8 with LF line endings (not CRLF)

#### Rationale:

**Why this matters:**

1. **Scripts are code** - They run in production environments, CI/CD, and developer machines
2. **Benchmarks are code** - They validate performance requirements and influence architecture decisions
3. **Tests are code** - They execute as frequently as production code and must be maintainable
4. **Tools are code** - They shape development workflow and can introduce bugs if poorly written
5. **Examples are code** - They teach users and represent the project's quality standards

**Consequences of poor quality "utility" code:**

- ❌ Scripts fail silently in CI/CD pipelines
- ❌ Benchmarks give misleading performance data
- ❌ Tests provide false confidence
- ❌ Tools introduce bugs into the development process
- ❌ Technical debt spreads from "quick scripts" to the entire codebase
- ❌ New contributors learn bad patterns from low-quality examples

**Bottom line**: If it's written in Python and checked into this repository, it meets our strict quality standards. No exceptions.

### ⚠️ CRITICAL: CONFIGURATION MANAGEMENT - NO RULE RELAXATION (NON-NEGOTIABLE)

**NEVER modify pyproject.toml, ruff.toml, or other configuration files to relax quality standards.**

#### Absolute Prohibitions

You MUST NEVER:

- ❌ **Add rules to disable lists** in pyproject.toml `[tool.pylint."messages control"]`
- ❌ **Add blanket `# pylint: disable` comments** without line-level justification
- ❌ **Disable PEP 8 checks** (import-outside-toplevel, line-too-long, etc.)
- ❌ **Relax mypy strictness** (no-warn-return-any, allow-untyped-defs, etc.)
- ❌ **Exclude files from quality checks** without explicit constitutional amendment
- ❌ **Increase complexity thresholds** (max-args, max-locals, max-branches)
- ❌ **Add ruff `--fix` auto-suppressions** (type: ignore, noqa, etc.)
- ❌ **Justify rule relaxation with "performance", "convenience", or "it's just a test"**

#### When You Encounter Quality Violations

**The ONLY acceptable response:**

1. **Fix the code** to comply with the standard
2. **Refactor** if the code is legitimately too complex
3. **Ask the user** if you genuinely cannot comply without architectural changes

**NEVER:**

- Disable the rule globally
- Add the rule to a disable list
- Exclude files or directories from checks
- Suggest "temporarily" disabling the rule

#### Line-Level Exceptions (Rare)

If a violation is **truly unavoidable** (e.g., external API requires specific pattern):

```python
# pylint: disable=rule-name  # JUSTIFICATION: Specific technical reason why this is required
problematic_code()
# pylint: enable=rule-name
```

**Requirements for line-level exceptions:**

- ✅ Must have explicit `# JUSTIFICATION:` comment explaining why
- ✅ Must be narrowly scoped (1-5 lines maximum)
- ✅ Must re-enable the rule immediately after
- ✅ Must have technical justification (not "convenience" or "performance")
- ✅ Must be reviewed in code review

#### Why This Matters

Configuration-based rule relaxation:

- Creates **invisible violations** that pass quality checks
- Violates the **NO DOUBLE STANDARDS** policy
- Makes the **constitution meaningless** (rules exist but aren't enforced)
- Allows **technical debt** to accumulate silently
- **Misleads developers** into thinking 10.00/10.00 means compliant code
- Creates **false confidence** in code quality

#### Enforcement

- Any PR that modifies disable lists will be rejected
- Quality gates MUST catch constitutional violations
- Configuration changes require explicit constitutional amendment
- Line-level exceptions must be justified in code review

**Bottom line**: The constitution defines the standards. Configuration enforces them. Never modify configuration to avoid compliance.

### ⚠️ CRITICAL: CONCURRENCY MODEL - THREAD-BASED ONLY (NON-NEGOTIABLE)

**ALL Python code MUST use thread-based concurrency. Async/await patterns are STRICTLY PROHIBITED.**

This is a core constitutional principle (see constitution.md "Principle VI: Concurrency Model").

#### Async/Await Prohibition

The following patterns are **ABSOLUTELY FORBIDDEN** anywhere in this repository:

- ❌ **NEVER** use `async def` function definitions
- ❌ **NEVER** use `await` keyword
- ❌ **NEVER** import or use `asyncio` module (event loops, tasks, futures, coroutines)
- ❌ **NEVER** use `async with` context managers
- ❌ **NEVER** use `async for` iteration
- ❌ **NEVER** create async generators (`async def` with `yield`)
- ❌ **NEVER** use async third-party libraries (aiohttp, asyncpg, motor, httpx async client, etc.)
- ❌ **NEVER** use FastAPI async route handlers (use sync route handlers only)
- ❌ **NEVER** suggest async/await as a solution to any problem

#### Thread-Based Concurrency Requirements

**ALWAYS use these patterns instead:**

**Database Connections:**
- ✅ Use `psycopg_pool.ConnectionPool` (synchronous connection pooling)
- ✅ NEVER use `asyncpg` or `psycopg` async variants
- ✅ Configure pool with appropriate size (min_size, max_size)
- ✅ Use context managers for connection acquisition: `with pool.connection() as conn:`

**Parallel I/O Operations:**
- ✅ Use `concurrent.futures.ThreadPoolExecutor` with context manager
- ✅ Example: `with ThreadPoolExecutor(max_workers=10) as executor:`
- ✅ Use `executor.map()` for parallel mapping operations
- ✅ Use `executor.submit()` for individual task submission
- ✅ Use `concurrent.futures.wait()` with timeout for cancellation support

**Inter-Thread Communication:**
- ✅ Use `threading.Event` for signaling (set(), clear(), wait(), is_set())
- ✅ Use `threading.Lock` for mutual exclusion of shared state
- ✅ Use `threading.RLock` for reentrant locks (when needed)
- ✅ Use `queue.Queue` for thread-safe producer-consumer patterns

**HTTP Requests:**
- ✅ Use `requests` library (synchronous)
- ✅ NEVER use `aiohttp`, `httpx async client`, or other async HTTP clients
- ✅ For parallel HTTP requests: use ThreadPoolExecutor with requests

**Web Framework (FastAPI):**
- ✅ Use **synchronous route handlers only** (regular `def`, not `async def`)
- ✅ Example: `@app.get("/") def read_root() -> dict[str, str]:`
- ✅ FastAPI fully supports synchronous handlers - use them exclusively
- ✅ Background tasks: use `Thread` with `Event`, NOT `BackgroundTasks` with async

**Timeouts and Cancellation:**
- ✅ Use `concurrent.futures.wait(futures, timeout=30)` for operation timeouts
- ✅ Use `threading.Timer` for delayed execution
- ✅ Use `threading.Event` to signal cancellation between threads
- ✅ NEVER use `asyncio.wait_for()` or similar async timeout mechanisms

#### Code Patterns

**ThreadPoolExecutor Pattern (Parallel I/O):**

```python
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

def process_items(items: list[Any], processor: Callable[[Any], Any], max_workers: int = 10) -> list[Any]:
    """Process items in parallel using thread pool."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results: list[Any] = list(executor.map(processor, items))
    return results

# Example usage
def fetch_data(url: str) -> dict[str, Any]:
    """Fetch data from URL using requests (synchronous)."""
    import requests
    response: requests.Response = requests.get(url, timeout=10)
    return response.json()

urls: list[str] = ["http://api.example.com/1", "http://api.example.com/2"]
data: list[dict[str, Any]] = process_items(urls, fetch_data, max_workers=5)
```

**Event-Based Signaling Pattern (Background Tasks):**

```python
from threading import Event, Thread
from typing import Callable
import time

def background_worker(stop_event: Event, task_fn: Callable[[], None]) -> None:
    """Run task in background thread until stop_event is set."""
    while not stop_event.is_set():
        task_fn()
        if stop_event.wait(timeout=1.0):  # Check every second
            break

# Usage
def do_work() -> None:
    """Perform background work."""
    print("Working...")
    time.sleep(0.5)

stop_event: Event = Event()
worker: Thread = Thread(target=background_worker, args=(stop_event, do_work))
worker.start()

# Later: signal graceful shutdown
stop_event.set()
worker.join(timeout=5.0)
```

**Database Connection Pool Pattern:**

```python
from psycopg_pool import ConnectionPool
from psycopg import Connection
from typing import Any

# Initialize pool (do once at application startup)
pool: ConnectionPool = ConnectionPool(
    conninfo="postgresql://user:pass@localhost/dbname",
    min_size=2,
    max_size=10,
    timeout=30.0
)

# Use pool in request handlers (synchronous)
def get_user(user_id: int) -> dict[str, Any]:
    """Fetch user from database using connection pool."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row: tuple[Any, ...] | None = cur.fetchone()
            if row is None:
                raise ValueError(f"User {user_id} not found")
            return {"id": row[0], "name": row[1], "email": row[2]}
```

**FastAPI Synchronous Route Handler Pattern:**

```python
from fastapi import FastAPI, HTTPException
from typing import Any

app: FastAPI = FastAPI()

# ✅ CORRECT: Synchronous route handler
@app.get("/users/{user_id}")
def read_user(user_id: int) -> dict[str, Any]:
    """Get user by ID (synchronous handler)."""
    try:
        user: dict[str, Any] = get_user(user_id)  # Calls synchronous function
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ❌ INCORRECT: Async route handler (PROHIBITED)
# @app.get("/users/{user_id}")
# async def read_user(user_id: int) -> dict[str, Any]:
#     user = await get_user_async(user_id)  # NEVER DO THIS
#     return user
```

#### Rationale

**Why Thread-Based Concurrency:**

1. **Simplicity**: No event loop management, no "color" functions (sync vs async)
2. **Ecosystem Compatibility**: Most Python libraries support threading; async support is fragmented
3. **Testing Simplicity**: Standard pytest works; no async fixtures or event loop in tests
4. **I/O-Bound Workloads**: ThreadPoolExecutor provides sufficient parallelism for database, HTTP, file I/O
5. **GIL Considerations**: For I/O-bound code (typical in web apps), GIL is released during I/O operations
6. **Debuggability**: Standard debuggers work seamlessly with threads; async debugging is more complex
7. **Library Consistency**: Avoids mixing sync/async libraries (requests vs aiohttp, psycopg vs asyncpg)
8. **Production Maturity**: Thread pools have decades of production hardening

**Why Async/Await is Prohibited:**

- Adds significant complexity without meaningful performance benefits for I/O-bound Python workloads
- Creates "colored function" problem (sync functions can't call async functions without changes)
- Fragments ecosystem (must choose between sync and async versions of libraries)
- Complicates testing (requires async test fixtures, event loop management)
- Makes debugging harder (async stack traces, event loop debugging)
- Violates "explicit is better than implicit" - async/await hides control flow

#### Enforcement

**During Code Review:**
- Any use of `async`, `await`, or `asyncio` is grounds for immediate rejection
- Any suggestion to use async libraries must be rejected with thread-based alternative
- Verify all route handlers in FastAPI use `def`, not `async def`
- Verify database drivers are synchronous (psycopg, not asyncpg)
- Verify HTTP clients are synchronous (requests, not aiohttp)

**During Implementation:**
- If you think a task "requires" async/await, STOP and consider thread-based alternatives:
  - High concurrency → ThreadPoolExecutor with appropriate `max_workers` (100+ threads is fine for I/O)
  - Timeouts → `concurrent.futures.wait()` with timeout parameter
  - Cancellation → `threading.Event` to signal cancellation
  - WebSockets → Use synchronous WebSocket libraries (e.g., `websocket-client`)
  - Background tasks → `Thread` with `Event` for graceful shutdown

**Bottom Line**: If it's async/await, it's not allowed. No exceptions. Use threads.

## Recent Changes
- 001-rag-csv-crew: Added Python 3.13 with FastAPI, Pydantic v2, psycopg[pool] 3.x
- 001-rag-csv-crew: Added PostgreSQL 17 with pgvector extension
- 001-rag-csv-crew: Added CrewAI for multi-agent RAG workflow
- 001-rag-csv-crew: Added Claude Opus (Anthropic API) for text generation
- 001-rag-csv-crew: Added OpenAI text-embedding-3-small for semantic search
- 001-rag-csv-crew: Added React 18+ with TypeScript and Vite for frontend
- 001-rag-csv-crew: Configured web application structure (backend/ + frontend/)



<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
