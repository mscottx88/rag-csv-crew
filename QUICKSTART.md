# RAG CSV Crew - Quickstart Guide

**Hybrid Search RAG for CSV Data with Multi-Agent Orchestration**

Natural language querying for your CSV files powered by AI. Upload data, ask questions in plain English, get intelligent answers.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Running the Application](#running-the-application)
5. [Using the Application](#using-the-application)
6. [Example Workflows](#example-workflows)
7. [API Reference](#api-reference)
8. [Architecture Overview](#architecture-overview)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

**Get up and running in 5 minutes:**

```bash
# 1. Clone and navigate to the project
cd rag-csv-crew

# 2. Set up environment variables
cp backend/.env.example backend/.env
# Edit backend/.env and add your API keys:
# - ANTHROPIC_API_KEY (for Claude Opus)
# - OPENAI_API_KEY (for embeddings)
# - GROQ_API_KEY (optional, for GROQ LLM)

# 3. Start PostgreSQL database
docker-compose up -d

# 4. Install dependencies
cd backend && pip install -e . && cd ..
cd frontend && npm install && cd ..

# 5. Start backend (Terminal 1)
cd backend && python -m uvicorn src.main:app --reload

# 6. Start frontend (Terminal 2)
cd frontend && npm run dev

# 7. Open browser
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

**First-time login:**
- Navigate to http://localhost:3000
- Enter any username (no password required)
- Upload a CSV file
- Ask a natural language question
- View results!

---

## Prerequisites

### Required Software

- **Python 3.13** - Backend runtime
- **Node.js 18+** - Frontend build tools
- **Docker** - For PostgreSQL + pgvector database
- **Git** - Version control

### API Keys (Required)

You'll need API keys for:

1. **Anthropic API** (Claude Opus for text generation)
   - Sign up: https://console.anthropic.com
   - Get API key from dashboard
   - Set `ANTHROPIC_API_KEY` in backend/.env

2. **OpenAI API** (text-embedding-3-small for semantic search)
   - Sign up: https://platform.openai.com
   - Get API key from dashboard
   - Set `OPENAI_API_KEY` in backend/.env

3. **GROQ API** (Optional alternative LLM provider)
   - Sign up: https://console.groq.com
   - Get API key from dashboard
   - Set `GROQ_API_KEY` in backend/.env

### System Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 2GB for application + database storage
- **OS**: Linux, macOS, or Windows with WSL2

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd rag-csv-crew
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/Mac:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

### 4. Database Setup

```bash
# Start PostgreSQL with pgvector extension
docker-compose up -d

# Verify database is running
docker ps | grep postgres
```

### 5. Environment Configuration

```bash
# Copy example environment file
cp backend/.env.example backend/.env

# Edit with your favorite editor
nano backend/.env  # or vim, code, etc.
```

**Required environment variables:**

```env
# LLM Configuration - Anthropic (Claude Opus)
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# LLM Configuration - OpenAI (Embeddings)
OPENAI_API_KEY=your-openai-api-key-here

# Optional: GROQ LLM Provider
GROQ_API_KEY=your-groq-api-key-here

# Database Configuration (defaults should work)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=rag_csv_crew
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres

# Application Settings
APP_ENV=development
APP_DEBUG=true
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]

# JWT Secret (change for production)
JWT_SECRET_KEY=your-secret-key-here-change-in-production
```

---

## Running the Application

### Full Stack (Recommended)

**Terminal 1 - Backend API Server:**
```bash
cd backend
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend Development Server:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Database (if not already running):**
```bash
docker-compose up -d
```

### Access Points

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs**: http://localhost:8000/redoc

### Verifying Installation

1. **Check backend health:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"healthy"}
   ```

2. **Check database connection:**
   ```bash
   docker exec -it rag-csv-crew-postgres psql -U postgres -c "\l"
   # Should list databases including rag_csv_crew
   ```

3. **Check frontend:**
   - Open http://localhost:3000
   - Should see login page

---

## Using the Application

### 1. Login (Username Only)

1. Navigate to http://localhost:3000
2. Enter any username (e.g., "demo_user")
3. Click "Login" (no password required)
4. You'll be redirected to the dashboard

**Note:** This is a demo/prototype authentication system. Each unique username creates an isolated database schema.

### 2. Upload CSV Data

1. Click "Datasets" in the sidebar
2. Click "Upload CSV Dataset" or drag and drop a file
3. Select your CSV file (max 1GB)
4. Watch the upload progress (0-100%)
5. File appears in the dataset list

**Supported formats:**
- CSV files (.csv extension)
- UTF-8 encoding recommended
- Headers required in first row
- Automatic schema inference

**Conflict handling:**
- If filename exists, you'll see a dialog:
  - **Replace**: Deletes old file, uploads new one
  - **Keep Both**: Renames new file (e.g., "data (1).csv")
  - **Cancel**: Aborts upload

### 3. Ask Questions

1. Click "Query" in the sidebar
2. Type your question in natural language:
   - "What are the top 10 customers by revenue?"
   - "Show me all sales from last month"
   - "Which products have the highest profit margin?"
3. Click "Submit Query"
4. Wait for processing (2-30 seconds)
5. View results with metadata:
   - Execution time
   - Row count
   - Confidence score

**Query features:**
- Natural language understanding
- Automatic SQL generation
- Hybrid search (exact + fuzzy + semantic)
- HTML-formatted results
- Real-time status updates (pending → processing → completed)

### 4. View Query History

1. Click "History" in the sidebar
2. Browse past queries with status badges:
   - ✅ **Completed**: Query succeeded
   - 🔄 **Processing**: Currently running
   - ⏸️ **Pending**: Queued
   - ❌ **Failed**: Error occurred
   - 🚫 **Cancelled**: User cancelled
3. Click any query to see full results
4. Filter by status using dropdown

### 5. Manage Datasets

1. Click "Datasets" in the sidebar
2. View list with metadata:
   - Filename
   - Row count
   - Column count
   - Upload date
3. Click "Delete" to remove dataset
4. Confirm deletion in dialog

---

## Example Workflows

### Example 1: Sales Analysis

**Upload data:**
```csv
date,product,quantity,revenue
2024-01-15,Widget A,100,1500.00
2024-01-16,Widget B,75,2250.00
2024-01-17,Widget A,120,1800.00
```

**Ask questions:**
- "What is the total revenue?"
- "Which product sold the most units?"
- "Show me sales by date"
- "What's the average revenue per product?"

**Expected results:**
- SQL query automatically generated
- HTML table with formatted results
- Metadata: execution time, row count

### Example 2: Customer Analytics

**Upload customers.csv:**
```csv
customer_id,name,email,signup_date
1,John Doe,john@example.com,2024-01-01
2,Jane Smith,jane@example.com,2024-01-05
```

**Upload orders.csv:**
```csv
order_id,customer_id,amount,order_date
101,1,250.00,2024-01-10
102,2,180.00,2024-01-12
103,1,320.00,2024-01-15
```

**Ask cross-dataset questions:**
- "Which customers have the highest order totals?"
- "How many orders has John Doe placed?"
- "Show me customers who signed up in January"

**System automatically:**
- Detects relationships (customer_id links)
- Joins tables in SQL query
- Returns combined results

### Example 3: Semantic Search

**Upload product_catalog.csv:**
```csv
product_id,name,description,price
1,Laptop Pro,"High-performance laptop with 16GB RAM",1299.99
2,Desktop Tower,"Powerful desktop computer",899.99
3,Notebook Basic,"Affordable laptop for students",499.99
```

**Ask semantic questions:**
- "Show me expensive computers" (finds Laptop Pro and Desktop Tower)
- "What portable devices do you have?" (finds laptops/notebooks)
- "Which products are good for students?" (finds Notebook Basic)

**Hybrid search combines:**
- Exact matches: "laptop" → "Laptop Pro"
- Fuzzy text: "computer" → "Laptop", "Desktop"
- Semantic: "expensive" → high price values

### Example 4: Handling Ambiguity

**Ambiguous question:**
- "Show me money"

**System response (low confidence < 60%):**
```
I found multiple possible interpretations:

1. Revenue (sales data, $125,000 total)
2. Profit (calculated from cost data, $45,000)
3. Balance (account balances, 15 records)

Which one would you like to see?
```

**Clear question:**
- "Show me total revenue by month"

**System response (high confidence > 60%):**
- Directly generates SQL and returns results

---

## API Reference

### Authentication Endpoints

**POST /auth/login**
- Request: `{"username": "demo_user"}`
- Response: `{"access_token": "...", "token_type": "bearer"}`
- Creates user schema on first login

**GET /auth/me**
- Headers: `Authorization: Bearer <token>`
- Response: `{"username": "demo_user"}`

### Dataset Endpoints

**GET /datasets**
- Headers: `Authorization: Bearer <token>`
- Response: List of user's datasets
- Returns: filename, row_count, column_count, created_at

**POST /datasets**
- Headers: `Authorization: Bearer <token>`, `Content-Type: multipart/form-data`
- Body: `file=<csv_file>`
- Response: Dataset metadata
- Returns 409 if filename exists (conflict)

**DELETE /datasets/{id}**
- Headers: `Authorization: Bearer <token>`
- Response: 204 No Content
- Requires confirmation from client

### Query Endpoints

**POST /queries**
- Headers: `Authorization: Bearer <token>`
- Body: `{"query_text": "What are the top 10 sales?", "dataset_ids": []}`
- Response: Query object with ID and status
- Status: pending → processing → completed/failed

**GET /queries/{id}**
- Headers: `Authorization: Bearer <token>`
- Response: Query object with current status
- Poll every 2 seconds until completed

**POST /queries/{id}/cancel**
- Headers: `Authorization: Bearer <token>`
- Response: Query object with cancelled status

**GET /queries/history**
- Headers: `Authorization: Bearer <token>`
- Query params: `page`, `page_size`, `status`
- Response: Paginated query history

**GET /queries/examples**
- No authentication required
- Response: List of example queries

### Health Check

**GET /health**
- No authentication required
- Response: `{"status": "healthy"}`

---

## Architecture Overview

### Technology Stack

**Backend:**
- FastAPI (synchronous REST API)
- PostgreSQL 17 + pgvector (database + vector search)
- CrewAI (multi-agent orchestration)
- Claude Opus 4.5 (text generation via Anthropic API)
- OpenAI text-embedding-3-small (semantic embeddings)
- psycopg[pool] 3.x (connection pooling)

**Frontend:**
- React 18+ with TypeScript
- Vite (development server)
- React Router (navigation)
- Axios (HTTP client)

**Infrastructure:**
- Docker Compose (PostgreSQL container)
- Git (version control)

### Multi-Tenancy Architecture

**Per-User Schema Isolation:**
```sql
-- User "demo_user" gets:
CREATE SCHEMA demo_user_schema;

-- All user tables in isolated schema:
demo_user_schema.datasets
demo_user_schema.queries
demo_user_schema.sales_data  -- Dynamic CSV tables
demo_user_schema.column_mappings
```

**Benefits:**
- Complete data isolation
- No cross-user data access
- Schema-level permissions
- Easy cleanup (DROP SCHEMA CASCADE)

### Hybrid Search Pipeline

**Query Processing Flow:**
```
User Question
     ↓
CrewAI SQL Agent (generates SQL)
     ↓
Hybrid Search (parallel execution):
  - Exact Match (column names)
  - Full-Text Search (tsvector + tsquery)
  - Vector Similarity (pgvector cosine)
     ↓
Result Fusion (weighted combination)
     ↓
CrewAI Analyst Agent (formats HTML)
     ↓
User sees formatted results
```

**Search Weights:**
- Exact match: 40%
- Full-text: 30%
- Vector similarity: 30%

### CrewAI Agent Architecture

**SQL Generator Agent:**
- Role: Database Query Specialist
- Goal: Convert natural language to SQL
- Tools: Schema inspector, query validator
- LLM: Claude Opus or GROQ

**Data Analyst Agent:**
- Role: Data Analysis Expert
- Goal: Interpret results and format HTML
- Tools: Result formatter, confidence scorer
- LLM: Claude Opus or GROQ

---

## Troubleshooting

### Common Issues

**1. Backend fails to start: "No module named 'backend'"**

**Solution:**
```bash
cd backend
pip install -e .
# Run from backend directory:
python -m uvicorn src.main:app --reload
```

**2. Database connection error: "could not connect to server"**

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# If not running, start it
docker-compose up -d

# Check logs
docker logs rag-csv-crew-postgres
```

**3. Frontend shows "Network Error" or CORS issues**

**Solution:**
```bash
# Check backend/.env has correct CORS settings:
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]

# Restart backend server
```

**4. Upload fails with "File too large"**

**Solution:**
```bash
# Check backend/.env:
MAX_UPLOAD_SIZE_MB=1000  # Increase if needed

# Restart backend
```

**5. Query timeout after 30 seconds**

**Solution:**
```bash
# Increase timeout in backend/.env:
QUERY_TIMEOUT_SECONDS=60

# Or optimize query by:
# - Using smaller datasets
# - Adding filters to narrow results
# - Asking more specific questions
```

**6. LLM API errors: "Invalid API key" or "Rate limit exceeded"**

**Check:**
```bash
# Verify API keys in backend/.env
ANTHROPIC_API_KEY=sk-ant-...  # Should start with sk-ant
OPENAI_API_KEY=sk-...          # Should start with sk-

# Check API rate limits on provider dashboards
# - Anthropic: https://console.anthropic.com
# - OpenAI: https://platform.openai.com/usage
```

**7. Frontend build errors**

**Solution:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Debug Mode

**Enable verbose logging:**
```bash
# In backend/.env:
APP_DEBUG=true
LOG_LEVEL=DEBUG
CREWAI_VERBOSE=true

# Restart backend to see detailed logs
```

**Check backend logs:**
```bash
cd backend
tail -f logs/app.log
```

**Check database queries:**
```bash
docker exec -it rag-csv-crew-postgres psql -U postgres -d rag_csv_crew
\dt demo_user_schema.*  -- List user tables
SELECT * FROM demo_user_schema.queries ORDER BY created_at DESC LIMIT 5;
```

### Performance Tips

**1. Speed up CSV uploads:**
- Use smaller files (<100MB) for testing
- Ensure database has enough disk space
- Check Docker container resources

**2. Optimize query performance:**
- Ask specific questions (avoid "show me everything")
- Use filters in queries ("last month", "top 10")
- Limit result size with pagination

**3. Reduce LLM API latency:**
- Use GROQ LLM (faster, set GROQ_API_KEY)
- Cache common queries (coming soon)
- Reduce context size with targeted questions

---

## Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **GitHub Issues**: <repository-url>/issues
- **Constitution**: `.specify/memory/constitution.md`
- **Architecture Details**: `specs/001-rag-csv-crew/plan.md`

---

## Quick Reference Card

**Start Everything:**
```bash
docker-compose up -d  # Database
cd backend && python -m uvicorn src.main:app --reload  # Backend
cd frontend && npm run dev  # Frontend
```

**Access Points:**
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

**Stop Everything:**
```bash
Ctrl+C  # Stop frontend & backend
docker-compose down  # Stop database
```

**Reset Everything:**
```bash
docker-compose down -v  # Delete database
docker-compose up -d    # Recreate database
# Re-upload your datasets
```

---

**Need help?** Open an issue with:
- Error messages (full stack trace)
- Steps to reproduce
- Environment details (OS, Python version, Node version)
- Configuration (sanitized .env)
