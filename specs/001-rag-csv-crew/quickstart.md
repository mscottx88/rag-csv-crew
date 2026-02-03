# Quickstart Guide: Hybrid Search RAG for CSV Data

**Feature**: Hybrid Search RAG for CSV Data
**Date**: 2026-02-02
**Status**: Complete
**Prerequisites**: Docker Desktop, Python 3.13, Node.js 18+

## Overview

This guide will help you get the hybrid search RAG application running locally for development.

**What you'll build**: A web application where users upload CSV files and ask natural language questions, receiving AI-generated HTML responses powered by hybrid search (structured SQL + full-text + vector similarity).

## Quick Start (5 minutes)

### 1. Start PostgreSQL with pgvector

```bash
# Navigate to project root
cd rag-csv-crew

# Start PostgreSQL container with pgvector extension
docker-compose up -d postgres

# Verify container is running
docker ps | grep postgres
```

**Expected output**: Container `rag-csv-crew-postgres-1` running on port 5432

### 2. Set up Backend

```bash
# Navigate to backend directory
cd backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync

# Configure environment variables
cp .env.example .env
# Edit .env to add your OpenAI API key: LLM_API_KEY=sk-...

# Initialize database schema
uv run python -m src.db.migrations init

# Start FastAPI development server
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Application startup complete.
```

### 3. Set up Frontend

Open a new terminal:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

**Expected output**:
```
  VITE v5.0.0  ready in 250 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 4. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)

## Detailed Setup

### Prerequisites Installation

#### Docker Desktop

**macOS/Windows**: Download from https://www.docker.com/products/docker-desktop

**Linux**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

#### Python 3.13

**macOS** (Homebrew):
```bash
brew install python@3.13
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install python3.13 python3.13-venv
```

**Windows**: Download installer from https://www.python.org/downloads/

#### uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Node.js 18+

**macOS** (Homebrew):
```bash
brew install node
```

**Ubuntu/Debian**:
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**Windows**: Download installer from https://nodejs.org/

### Environment Configuration

#### Backend .env

Create `backend/.env`:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=ragcsv
DB_USER=dev
DB_PASSWORD=dev
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10

# LLM Configuration
LLM_PROVIDER=openai  # openai, anthropic, ollama
LLM_API_KEY=sk-...  # Your OpenAI API key
LLM_MODEL=gpt-4
LLM_EMBEDDING_MODEL=text-embedding-3-small
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.1

# Application Configuration
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
QUERY_TIMEOUT_SECONDS=30
MAX_FILE_SIZE_BYTES=0  # 0 = unlimited

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440  # 24 hours
```

#### docker-compose.yml

Create `docker-compose.yml` in project root:

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:0.6.0-pg16
    container_name: rag-csv-crew-postgres
    environment:
      POSTGRES_DB: ragcsv
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev -d ragcsv"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
    driver: local
```

### Database Initialization

```bash
cd backend

# Initialize system schema and tables
uv run python -m src.db.migrations init

# Verify schema creation
uv run python -m src.db.migrations verify
```

**Expected output**:
```
✓ System schema (public) created
✓ Users table created
✓ Query log table created
✓ pgvector extension enabled
Database initialization complete!
```

## Usage Examples

### Example 1: Upload CSV and Query

#### 1. Login (username-only, no password)

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice"}'
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "username": "alice"
}
```

Save the `access_token` for subsequent requests.

#### 2. Upload CSV File

```bash
# Create sample CSV
cat > sales.csv << EOF
date,product,quantity,revenue,region
2024-01-15,Widget A,100,1999.50,North
2024-01-16,Widget B,50,999.00,South
2024-01-17,Widget A,75,1499.25,East
EOF

# Upload CSV
curl -X POST http://localhost:8000/datasets \
  -H "Authorization: Bearer <your_token>" \
  -F "file=@sales.csv"
```

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "sales.csv",
  "original_filename": "sales.csv",
  "table_name": "sales_data",
  "uploaded_at": "2024-01-18T10:30:00Z",
  "row_count": 3,
  "column_count": 5,
  "file_size_bytes": 245,
  "schema_json": [
    {"name": "date", "inferred_type": "date", "nullable": false},
    {"name": "product", "inferred_type": "text", "nullable": false},
    {"name": "quantity", "inferred_type": "integer", "nullable": false},
    {"name": "revenue", "inferred_type": "numeric", "nullable": false},
    {"name": "region", "inferred_type": "text", "nullable": false}
  ]
}
```

#### 3. Submit Natural Language Query

```bash
curl -X POST http://localhost:8000/queries \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "What are the top 2 products by total revenue?"
  }'
```

**Response**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "query_text": "What are the top 2 products by total revenue?",
  "submitted_at": "2024-01-18T10:35:00Z",
  "completed_at": null,
  "status": "pending",
  "generated_sql": null,
  "result_count": null,
  "execution_time_ms": null
}
```

#### 4. Poll for Query Completion

```bash
curl -X GET http://localhost:8000/queries/660e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer <your_token>"
```

**Response (when complete)**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "query_text": "What are the top 2 products by total revenue?",
  "submitted_at": "2024-01-18T10:35:00Z",
  "completed_at": "2024-01-18T10:35:02Z",
  "status": "completed",
  "generated_sql": "SELECT product, SUM(revenue) as total_revenue FROM sales_data GROUP BY product ORDER BY total_revenue DESC LIMIT 2",
  "result_count": 2,
  "execution_time_ms": 1250,
  "response": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "query_id": "660e8400-e29b-41d4-a716-446655440001",
    "html_content": "<h2>Top Products by Revenue</h2><table><tr><th>Product</th><th>Total Revenue</th></tr><tr><td>Widget A</td><td>$3,498.75</td></tr><tr><td>Widget B</td><td>$999.00</td></tr></table>",
    "plain_text": "The top 2 products by revenue are Widget A ($3,498.75) and Widget B ($999.00).",
    "confidence_score": 0.95,
    "generated_at": "2024-01-18T10:35:02Z"
  }
}
```

### Example 2: Multi-File Query

Upload a second CSV:

```bash
# Create customers CSV
cat > customers.csv << EOF
customer_id,name,region
1,Alice Corp,North
2,Bob Inc,South
3,Charlie LLC,East
EOF

curl -X POST http://localhost:8000/datasets \
  -H "Authorization: Bearer <your_token>" \
  -F "file=@customers.csv"
```

Query across both files:

```bash
curl -X POST http://localhost:8000/queries \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Which customers are in regions where Widget A had sales?"
  }'
```

The system will:
1. Detect the question requires data from both `sales_data` and `customers_data`
2. Identify the `region` column as the join key (cross-reference)
3. Generate a SQL query joining the tables
4. Format a response with customer names

## Development Workflow

### Running Tests

```bash
# Backend tests
cd backend
uv run pytest tests/ -v --cov=src

# Frontend tests
cd frontend
npm test

# Integration tests (requires running PostgreSQL)
cd backend
uv run pytest tests/integration/ -v
```

### Code Quality Checks

```bash
# Backend quality checks
cd backend

# Linting (ruff)
uv run ruff check src/ tests/

# Type checking (mypy)
uv run mypy --strict src/ tests/

# Code analysis (pylint)
uv run pylint src/ tests/

# Formatting
uv run ruff format src/ tests/

# Frontend quality checks
cd frontend
npm run lint
npm run type-check
```

### Hot Reloading

Both backend and frontend support hot reloading:

- **Backend**: `uvicorn` with `--reload` flag auto-restarts on code changes
- **Frontend**: Vite dev server auto-refreshes browser on code changes

No manual restart needed during development!

## Troubleshooting

### PostgreSQL Connection Failed

**Symptom**: `psycopg.OperationalError: could not connect to server`

**Solution**:
```bash
# Check if Docker Desktop is running
docker ps

# Check if PostgreSQL container is healthy
docker-compose ps

# Restart container if needed
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### pgvector Extension Not Found

**Symptom**: `ERROR: extension "vector" does not exist`

**Solution**:
```bash
# Ensure you're using pgvector image
docker-compose down
docker-compose up -d postgres

# Verify extension
docker exec rag-csv-crew-postgres psql -U dev -d ragcsv -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### LLM API Errors

**Symptom**: `openai.error.AuthenticationError: Incorrect API key provided`

**Solution**:
```bash
# Verify API key in .env
cat backend/.env | grep LLM_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"
```

### Frontend CORS Errors

**Symptom**: `Access to XMLHttpRequest blocked by CORS policy`

**Solution**:
```bash
# Verify CORS_ORIGINS in backend/.env includes frontend URL
# Default: http://localhost:5173

# Restart backend server after changing .env
```

## Next Steps

1. **Run Tests**: Verify setup with `pytest` (backend) and `npm test` (frontend)
2. **Explore API**: Use Swagger UI at http://localhost:8000/docs
3. **Read Spec**: Review [spec.md](spec.md) for detailed requirements
4. **Read Plan**: Review [plan.md](plan.md) for architecture details
5. **Generate Tasks**: Run `/speckit.tasks` to generate implementation task list

## Architecture Summary

```
┌─────────────┐      HTTP      ┌─────────────┐      SQL       ┌──────────────┐
│   React     │ ──────────────> │   FastAPI   │ ────────────> │ PostgreSQL   │
│   Frontend  │ <────────────── │   Backend   │ <──────────── │ + pgvector   │
└─────────────┘    JSON/HTML    └─────────────┘   Async I/O   └──────────────┘
                                       │
                                       │ LLM API
                                       ▼
                                ┌─────────────┐
                                │   OpenAI    │
                                │   (GPT-4)   │
                                └─────────────┘
```

**Data Flow**:
1. User uploads CSV → Backend ingests to PostgreSQL (username_schema.table_name)
2. User submits query → Backend sends to CrewAI agents
3. CrewAI agents:
   - SQL Generator: Convert question to SQL query
   - Keyword Searcher: Full-text search (PostgreSQL `ts_rank`)
   - Vector Searcher: Semantic similarity (pgvector)
4. Results fused, ranked, and sent to Result Analyst agent
5. Result Analyst generates HTML response
6. Frontend displays formatted answer

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **CrewAI Docs**: https://docs.crewai.com/
- **pgvector GitHub**: https://github.com/pgvector/pgvector
- **React Docs**: https://react.dev/
- **Vite Docs**: https://vitejs.dev/

---

**Questions?** Check [spec.md](spec.md) for detailed requirements or [plan.md](plan.md) for architecture decisions.
