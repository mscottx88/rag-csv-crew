# Feature Specification: Hybrid Search RAG for CSV Data

**Feature Branch**: `001-rag-csv-crew`
**Created**: 2026-02-02
**Status**: Draft
**Input**: User description: "Create a Python-based Hybrid Search RAG application using CrewAI, built with SDD, combining structured, full-text, and vector store queries to convert plain-text questions about arbitrary Postgres data ingested from local CSV files into SQL queries and analyze the results to produce a human-readable plain-text response formatted in HTML all hosted by a FastAPI based backend with a React frontend."

## Clarifications

### Session 2026-02-02

- Q: User Authentication Mechanism → A: Simple username-only authentication - users log in with username (no password), system creates schema on first login
- Q: Dataset Replacement Behavior → A: Prompt user for action - ask whether to replace existing dataset or keep both (rename new upload with timestamp suffix)
- Q: Database Connection Loss Recovery → A: Retry with user notification - attempt 3 retries with exponential backoff, show "Reconnecting..." message to user, fail after retries exhausted
- Q: Operational Observability Level → A: Standard application logging - structured logs for authentication, file operations, query processing (with timing), errors, and user actions
- Q: Query Processing Timeout → A: 30 second timeout with cancellation - queries automatically terminate after 30 seconds with clear message; users can cancel anytime before timeout
- Q: Deployment Environment Security Context → A: Demo/prototype environment - Not intended for production use with real data, security reduced for ease of testing
- Q: LLM API Failure Handling Strategy → A: Queue requests for retry - Buffer failed LLM requests and retry automatically with exponential backoff, user sees "Processing..." state
- Q: User Role and Permission Model → A: Single role - all users equal - All authenticated users have identical permissions to upload CSV, query their own data, manage their datasets, and view their history
- Q: Data Retention and Deletion Policy → A: User-controlled deletion, no auto-expiration - Data persists indefinitely until user explicitly deletes it; users can delete individual datasets or clear query history
- Q: API Versioning Strategy → A: No versioning for MVP - API can change freely during demo/prototype phase; versioning deferred until production-ready
- Q: LLM Model for Text Generation (SQL queries and HTML responses) → A: Claude Opus
- Q: Embedding Model for Semantic Search → A: OpenAI text-embedding-3-small
- Q: Cross-Dataset Query Default Behavior → A: Query all datasets by default
- Q: Multiple Device Session Management → A: Allow multiple concurrent sessions
- Q: Dataset Deletion Confirmation → A: Require explicit confirmation dialog

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CSV Data Upload and Basic Querying (Priority: P1)

Users need to upload CSV files containing business data and immediately start asking questions about that data using natural language, receiving accurate answers without needing to know database query languages or data structures.

**Why this priority**: Core value proposition - without data ingestion and basic querying, the application has no value. This represents the minimal viable product.

**Independent Test**: Can be fully tested by uploading a single CSV file with sample data, asking simple questions like "What are the top 5 sales by revenue?" and verifying the system returns correct answers.

**Acceptance Scenarios**:

1. **Given** no data has been uploaded, **When** a user uploads a CSV file with valid data, **Then** the system ingests the data and confirms successful import
2. **Given** data has been successfully uploaded, **When** a user asks a simple question like "How many records are there?", **Then** the system returns an accurate count
3. **Given** uploaded data contains structured information, **When** a user asks a question requiring data filtering or aggregation, **Then** the system correctly interprets the question and returns relevant results
4. **Given** a user asks a question, **When** the answer is generated, **Then** the response is formatted in readable HTML with proper structure
5. **Given** a user has previously uploaded a file named "sales.csv", **When** they upload another file with the same name, **Then** the system prompts them to either replace the existing dataset or keep both with a timestamp suffix

---

### User Story 2 - Intelligent Multi-Strategy Search (Priority: P2)

Users need the system to understand the semantic meaning and context of their questions, not just keyword matches, so they can ask questions in natural language without worrying about exact terminology used in the data.

**Why this priority**: Differentiates this from simple database query tools. Enables users to find information even when they don't know exact column names or values. Requires P1 to be functional first.

**Independent Test**: Can be tested by asking semantically similar questions with different wording (e.g., "revenue", "income", "earnings") and verifying the system understands they refer to the same concept. Compare results with exact keyword matching to demonstrate improvement.

**Acceptance Scenarios**:

1. **Given** uploaded data contains product information, **When** a user asks "Which items sold the most?" instead of the exact column name "units_sold", **Then** the system understands the semantic meaning and returns correct results
2. **Given** a question could match multiple data concepts, **When** the system searches for answers, **Then** it combines exact matches, fuzzy text matching, and semantic understanding to find the most relevant results
3. **Given** a user asks an ambiguous question, **When** the system cannot determine intent with confidence, **Then** it asks for clarification or suggests multiple interpretations
4. **Given** data contains text descriptions, **When** a user asks about concepts mentioned in those descriptions, **Then** the system performs full-text search across relevant fields

---

### User Story 3 - Multi-File Cross-Dataset Queries (Priority: P3)

Users need to ask questions that span multiple uploaded CSV files, enabling analysis of relationships between different datasets without manual data joining or preprocessing.

**Why this priority**: Enables advanced analytical use cases but requires both P1 (basic querying) and P2 (intelligent search) to be valuable. Can be deferred to later releases.

**Independent Test**: Can be tested by uploading two related CSV files (e.g., "customers.csv" and "orders.csv"), asking a question like "Which customers have the highest order totals?" and verifying the system correctly correlates data across both files.

**Acceptance Scenarios**:

1. **Given** multiple CSV files have been uploaded, **When** a user asks a question that requires data from multiple files, **Then** the system identifies the relevant datasets and correlates them appropriately
2. **Given** CSV files contain relational data (e.g., customer IDs linking customers to orders), **When** the system processes a cross-file query, **Then** it automatically detects and uses these relationships
3. **Given** a user uploads a new CSV file, **When** it contains data related to existing uploads, **Then** the system updates its understanding of cross-references

---

### User Story 4 - Interactive Web Interface (Priority: P2)

Users need a web-based interface where they can upload files, submit questions, view results, and review their query history, all without requiring installation of desktop software.

**Why this priority**: Essential for usability and accessibility. Without a UI, the system is unusable for most users. Should be developed in parallel with P1 backend functionality.

**Independent Test**: Can be tested by accessing the web interface, verifying all core interactions (file upload, question submission, result display) work correctly through the browser.

**Acceptance Scenarios**:

1. **Given** a user accesses the web application, **When** they navigate to the upload section, **Then** they can select and upload CSV files with clear progress indicators
2. **Given** data has been uploaded, **When** a user types a question in the query interface, **Then** they receive results displayed in a clear, formatted manner
3. **Given** a user has submitted multiple queries, **When** they view their history, **Then** they can see previous questions and answers with timestamps
4. **Given** a query is processing, **When** the user waits, **Then** they see a loading indicator and can cancel if desired

---

### Edge Cases

- What happens when uploaded CSV files have inconsistent schemas (missing columns, different data types)?
- How does the system handle questions about data that doesn't exist in uploaded files?
- What occurs when CSV files are too large to process efficiently (>1GB)?
- How does the system respond when questions are grammatically incorrect or completely ambiguous?
- What happens when a user uploads a CSV with duplicate column names?
- How does the system handle special characters, unicode, or non-English text in CSV data?
- What occurs when multiple users upload files with the same name but different content?
- When database connection is lost during operations, system will retry up to 3 times with exponential backoff before failing
- What happens when semantic search produces no confident results?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to upload CSV files through a web interface
- **FR-002**: System MUST validate CSV file structure and provide clear error messages for invalid formats, including specific details about the validation failure (e.g., "Row 45 contains 12 columns but header has 10 columns", "Unable to detect delimiter - file may not be valid CSV", "Encoding appears to be binary, not text"), the affected location (row/column numbers), and suggested corrective actions
- **FR-003**: System MUST ingest CSV data and store it in a queryable format
- **FR-004**: System MUST accept natural language questions about uploaded data
- **FR-005**: System MUST convert natural language questions into structured queries against the ingested data
- **FR-006**: System MUST execute queries combining exact matching (40% weight for exact column/value matches), full-text search (30% weight for keyword presence in text fields), and semantic vector search (30% weight for semantic similarity), with results ranked by combined weighted score and de-duplicated when multiple strategies return the same records
- **FR-007**: System MUST analyze query results and generate human-readable responses
- **FR-008**: System MUST format responses in structured HTML for clear presentation per design-system.md specifications, including: semantic HTML5 elements (headers, paragraphs, lists, tables for tabular data), proper hierarchy (h1 for main answer, h2 for sections), readable typography (16px base size, system fonts, WCAG 2.1 AA contrast ratios minimum 4.5:1 for normal text), and clear visual separation between answer components (8px grid spacing system, semantic color scheme, confidence indicators with visual levels)
- **FR-009**: System MUST handle questions requiring data from a single uploaded file
- **FR-010**: System MUST handle questions requiring data from multiple uploaded files simultaneously, with queries defaulting to search across all user datasets when no specific datasets are explicitly selected, while still allowing users to optionally filter queries to specific datasets through manual selection. Cross-references between datasets MUST be detected automatically using column value overlap analysis: comparing distinct values across columns of the same data type (numeric, text, date) and establishing a relationship when value intersection meets or exceeds a 50% threshold (foreign key candidates) or when column names match patterns suggesting relationships (e.g., "customer_id" in both datasets)
- **FR-011**: System MUST maintain user-accessible query history for each user (stored in database, retrievable via API for display in UI)
- **FR-011a**: System MUST track query processing status (submitted, executing, completed, failed, cancelled, timeout) and provide real-time status updates to users, with clear completion notifications and result availability indicators
- **FR-012**: System MUST provide feedback during long-running operations (upload, query processing) including progress indicators (percentage complete, elapsed time, estimated remaining time) and clear visual loading states
- **FR-013**: System MUST detect and handle CSV formatting variations including encodings (UTF-8, Latin1, Windows-1252, UTF-16), delimiters (comma, semicolon, pipe, tab), quote characters (double-quote, single-quote), and header row presence/absence
- **FR-014**: System MUST support standard data types (text, numbers, dates, booleans) in uploaded CSV files, with automatic type inference during ingestion
- **FR-015**: System MUST allow users to view the list of uploaded datasets
- **FR-016**: Users MUST be able to delete uploaded datasets and clear their query history with explicit user confirmation (displaying dataset name and requiring confirmation before deletion to prevent accidental data loss); data persists indefinitely until explicitly deleted by the user (no automatic expiration or retention limits)
- **FR-017**: System MUST provide generic example questions to help users understand capabilities (e.g., "What are the top 10 rows?", "Count all records")
- **FR-018**: System MUST handle multiple concurrent users using username-based schema tenancy for complete data isolation across all operations including dataset uploads, queries, deletions, cross-reference detection, and query history, ensuring no user can access or modify another user's data. All users have equal permissions (single role model): upload CSV files, query their own data, manage their own datasets, and view their own query history
- **FR-019**: System MUST support CSV file uploads without enforcing file size limits
- **FR-020**: System MUST use username-based database schemas to isolate each user's datasets, following the naming convention `{username}_schema` (e.g., "alice_schema", "bob_schema"), with PostgreSQL search_path set per session to enforce isolation and prevent cross-schema data access
- **FR-021**: System MUST authenticate users via username-only login (no password required) and automatically create user-specific database schema on first login
- **FR-021a**: System MUST provide logout functionality that invalidates the user's authentication token, MUST allow multiple concurrent sessions from different devices or browsers (each with unique JWT tokens), and MUST implement independent session expiration after 24 hours of inactivity per session with automatic re-authentication required (logging out from one device/session does not affect other active sessions)
- **FR-022**: System MUST prompt users when uploading a CSV file with the same name as an existing dataset, offering options to replace the existing dataset or keep both (with timestamp suffix on the new upload)
- **FR-023**: System MUST handle database connection loss during operations by automatically retrying up to 3 times with exponential backoff, displaying a "Reconnecting..." message to users, and returning a clear error message if all retries fail
- **FR-024**: System MUST log all significant operations in structured JSON format for system observability and debugging (separate from user-facing query history in FR-011), with mandatory fields (timestamp ISO 8601, log_level, event_type, username, request_id) and event-specific fields (execution_time_ms for queries, row_count for uploads, error_message and stack_trace for failures), covering user authentication events (login, logout, session expiration), file operations (upload start/complete/fail, delete, conflict resolution), query lifecycle (submission, execution start, completion, cancellation, timeout), database operations (connection retries, schema creation), errors, and security-relevant actions (cross-schema access attempts, rate limit violations)
- **FR-024a**: System MUST implement log retention and rotation policy to prevent unbounded storage growth, including: daily log rotation (new log file created at midnight UTC), retention period of 30 days for standard logs and 90 days for security-relevant logs (authentication, access control violations), automatic archival of logs older than retention period to compressed format (.gz), and configurable maximum log file size (default 100MB per file before rotation) with alerts at 80% storage capacity threshold
- **FR-025**: System MUST terminate queries that exceed 30 seconds of processing time with a clear timeout message, and allow users to manually cancel queries at any time before the timeout expires
- **FR-026**: System MUST provide appropriate zero-state user interfaces for new users with no uploaded data (showing upload prompts, example questions, and getting-started guidance) and empty query history (showing placeholder text encouraging first query submission)
- **FR-027**: System MUST handle concurrent operations by the same user (e.g., uploading a new dataset while an existing query is running) by queuing operations appropriately and providing clear status indicators for each active operation
- **FR-028**: System MUST handle dataset deletion during active queries by either completing in-progress queries using cached data or gracefully failing with a clear message indicating the dataset was deleted, and preventing new queries against deleted datasets
- **FR-029**: System MUST handle timeout and cancellation scenarios by returning any partial results gathered before termination along with a clear indicator of incompleteness (e.g., "Query cancelled after processing 5 of 12 tables - partial results shown"), or returning an empty result set if no meaningful partial results exist
- **FR-030**: System MUST handle CSV re-upload with changed schema (different column names, types, or count) by treating it as a new dataset version, prompting the user about schema changes detected (e.g., "New version has 15 columns vs 10 in previous"), and optionally archiving or replacing the previous version based on user choice
- **FR-031**: System MUST handle inconsistent CSV schemas (missing columns in some rows, data type mismatches) by either rejecting the file with a clear error message specifying the inconsistency location (row/column), or attempting to import with best-effort type coercion and null-filling for missing values, based on validation strictness settings
- **FR-032**: System MUST handle questions about data that doesn't exist in uploaded files by returning a clear message indicating no matching data was found, suggesting related columns or tables that do exist, and optionally recommending re-phrasing the question or uploading relevant data
- **FR-033**: System MUST handle very large CSV files (>1GB) by using streaming ingestion without loading entire file into memory, providing real-time progress indicators (percentage, rows processed, estimated time remaining), and allowing cancellation during upload with partial rollback
- **FR-034**: System MUST handle grammatically incorrect or completely ambiguous questions by attempting to interpret intent using partial matching, returning error messages for unparseable questions with suggestions for re-phrasing (e.g., "Did you mean: [suggested reformulation]?"), or asking clarifying questions when multiple interpretations are possible
- **FR-035**: System MUST handle CSV files with duplicate column names by either rejecting the file with an error listing duplicates, or automatically deduplicating column names by appending numeric suffixes (e.g., "price", "price_2", "price_3") and warning the user about the modification
- **FR-036**: System MUST handle special characters, unicode, and non-English text in CSV data by preserving UTF-8 encoding throughout ingestion and query processing, correctly indexing unicode characters for search, and displaying special characters properly in HTML responses
- **FR-037**: System MUST handle same-filename uploads by different users through per-user schema isolation (per FR-020), allowing multiple users to independently upload files with identical names (e.g., "sales.csv") without conflicts, with each file stored in the respective user's schema namespace
- **FR-038**: System MUST handle low-confidence semantic search results by calculating and displaying confidence scores (0-100%) for each answer, providing warnings and clarification requests when confidence falls below 60% (low-confidence warning threshold selected based on preliminary analysis showing 60-69% confidence correlates with user dissatisfaction and query refinement requests in similar RAG systems), suggesting query refinements for low-confidence results, and offering to show alternative interpretations when multiple possible answers have similar confidence levels. Note: This 60% threshold triggers user clarification requests; the separate 40% threshold in FR-048 triggers complete semantic search fallback to exact matching.
- **FR-039**: System MUST define and enforce performance requirements for different load conditions: single-user baseline (query response <5s), normal load 5-10 concurrent users (response <6s per SC-006), and peak load up to 20 concurrent users (response <10s, degraded performance acceptable with user notification)
- **FR-040**: System MUST implement SQL injection prevention through parameterized queries exclusively (no string concatenation of user input into SQL), input validation and sanitization before query generation, and query sandboxing that restricts generated SQL to SELECT statements only (no INSERT, UPDATE, DELETE, DROP, or other DDL/DML)
- **FR-041**: System MUST define storage scalability requirements including per-user storage quotas (default 10GB, configurable), automatic storage monitoring with alerts at 80% capacity, and graceful handling of quota exhaustion (preventing uploads, notifying user with cleanup recommendations)
- **FR-042**: System MUST define resource exhaustion behavior including query memory limits (max 2GB per query), CPU time limits (enforced via 30s timeout per FR-025), connection pool limits (max 10 concurrent database connections per user), and clear error messages when limits are reached directing users to optimize queries or contact administrators
- **FR-043**: System MUST provide monitoring and alerting capabilities including metrics collection for query latency (p50, p95, p99), error rates by error type, database connection pool utilization, storage usage trends, and automated alerts for anomalies (error rate >5%, latency p95 >10s, storage >90% full, connection pool exhaustion)
- **FR-044**: System MUST document the security posture for password-free username-only authentication, acknowledging this is a demo/prototype environment not intended for production use with real data. Documentation should identify known risks (session hijacking, username enumeration, impersonation) and basic mitigations (TLS encryption, session expiration, rate limiting), with explicit warnings that additional security controls (strong authentication, authorization, audit logging) are required before production deployment
- **FR-045**: System documentation MUST include a complete requirements traceability matrix mapping each functional requirement (FR-001 through FR-044) to corresponding acceptance scenarios in User Stories, success criteria (SC-001 through SC-011), test cases, and implementation tasks, ensuring bidirectional traceability and coverage verification
- **FR-046**: System documentation MUST explicitly address all edge cases identified in the specification (inconsistent schemas, non-existent data, large files, malformed questions, duplicate columns, special characters, concurrent uploads, low-confidence results, connection loss) by mapping each to specific functional requirements (FR-031 through FR-038 and FR-023) or explicitly documenting why they are deferred to future releases
- **FR-047**: System documentation MUST map all identified risks and their mitigations to specific requirements: Performance Risk → FR-033, FR-039, FR-025; Storage Risk → FR-041, FR-043; Resource Exhaustion → FR-042, FR-033; Accuracy Risk → FR-038, FR-024; Data Quality → FR-002, FR-031, FR-013; Concurrency Risk → FR-039, FR-042; Semantic Search → FR-038, FR-006; Multi-Tenancy → FR-044, FR-018, FR-020
- **FR-048**: System MUST handle zero-confidence semantic search results (when no semantic matches exceed minimum confidence threshold of 40%, distinct from FR-038's 60% clarification threshold) by falling back to exact column name matching only, returning a clear "No semantic matches found" message to the user with suggestions to either rephrase the question using exact column names from the dataset schema, or verify that the question is relevant to the uploaded data, and logging the zero-confidence event for analysis of semantic search effectiveness. This 40% threshold represents the absolute minimum for semantic matching viability; confidence between 40-60% still uses semantic results but triggers clarification requests per FR-038.

### Key Entities

- **Dataset**: Represents an uploaded CSV file, including metadata (filename, upload timestamp, row count, column schema, user owner)
- **Query**: Represents a user question, including the original natural language text, timestamp, associated datasets, and processing status
- **Response**: Represents the answer to a query, including formatted HTML content, underlying data retrieved, confidence scores, and generation timestamp
- **User**: Represents an individual using the system, identified by unique username (no password), with associated database schema, uploaded datasets, and query history. All users have identical permissions in a single-role model (no admin or privileged roles)
- **Column Mapping**: Represents the system's understanding of data structure, including column names, inferred data types, and semantic annotations
- **Cross-Reference**: Represents detected relationships between columns across different datasets (e.g., foreign key relationships)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can upload typical CSV files (defined as files under 100MB with size distribution: 10% <1MB, 40% 1-10MB, 40% 10-50MB, 10% 50-100MB, representing common business data export sizes) and receive confirmation of successful ingestion within 10 seconds; larger files (supported per FR-019 with no size limits) provide progress updates during ingestion and may take proportionally longer based on size and complexity
- **SC-002**: System correctly answers at least 90% of straightforward factual questions (defined as questions requiring single-table aggregations, filters, or lookups without joins or complex logic; examples include: COUNT queries "How many customers?", MAX/MIN/AVG aggregations "What is the highest revenue?", simple WHERE filters "Which orders are pending?", DISTINCT queries "List all unique product categories"; NON-straightforward examples include: multi-table joins "Which customers never placed orders?", complex business logic "Calculate year-over-year growth rate", nested subqueries, or window functions), measured against a test dataset of 50 factual questions with verified ground truth answers
- **SC-003**: Users receive responses to natural language queries within 5 seconds for queries on datasets under 100,000 rows (normal case performance target; queries may take longer for larger datasets but MUST terminate within FR-025's 30-second absolute maximum)
- **SC-004**: System successfully handles semantic variations in questions, matching semantically similar terms at least 80% of the time, measured using a test dataset of 30 question pairs with semantic variations (e.g., "revenue"/"income"/"earnings", "sold"/"purchased"/"bought") against the same ground truth answers, with matching defined as returning identical or equivalent result sets
- **SC-005**: Users can complete the workflow (upload CSV, ask question, receive answer) without consulting documentation 90% of the time, measured through moderated usability testing with 10 participants unfamiliar with the system, observing whether they successfully complete the workflow within 5 minutes without requesting help or accessing documentation
- **SC-006**: System supports at least 10 concurrent users without performance degradation, defined as maintaining query response times within 20% of single-user baseline (<6 seconds for typical queries) and error rate below 1%, measured through load testing with 10 simulated users performing realistic query patterns over 10 minutes
- **SC-007**: Cross-dataset queries correctly identify and use relationships between datasets at least 75% of the time for clearly related data (defined as datasets with: (a) matching column names with common suffixes like "_id", "id", or "_key", e.g., "customer_id" in both files; (b) column value overlap ≥50% when comparing distinct values of the same data type; (c) parent-child relationships evident from data cardinality patterns), measured using 20 test cases with known relationships (foreign key pairs like customer_id, order_id) across multiple CSV file pairs, with correctness defined as generating joins that produce accurate result sets matching ground truth
- **SC-008**: Generated responses are readable and well-formatted, with user satisfaction rating above 4/5 for answer quality, measured through post-query surveys (5-point Likert scale) with minimum 20 user responses evaluating readability, formatting clarity, and answer usefulness
- **SC-009**: System handles common CSV formatting variations (different delimiters, encodings) successfully in 95% of cases, measured using a test suite of 20 CSV files with format variations covering all combinations of supported encodings (UTF-8, Latin1, Windows-1252, UTF-16) and delimiters (comma, semicolon, pipe, tab), with success defined as correct data ingestion and schema detection
- **SC-010**: Users can find answers using natural language at least 50% faster compared to manually writing database queries, measured through timed user studies where participants with SQL knowledge complete 10 information retrieval tasks using both natural language queries and manual SQL, comparing average task completion times with baseline established from SQL experts (target: NL query time ≤ 50% of manual SQL time)
- **SC-011**: Users can cancel long-running queries within 1 second of clicking the cancel button, and queries exceeding 30 seconds are automatically terminated with clear user notification
- **SC-012**: Vector similarity search operations using pgvector MUST complete within 100ms for typical queries (semantic column matching with up to 1000 stored embeddings), measured from embedding generation start to similarity results returned, ensuring hybrid search combines all three strategies (exact match, full-text, vector) within the 5-second target per SC-003

## Assumptions

- Users have basic familiarity with web applications and file upload interfaces
- CSV files follow standard formatting conventions (header row, consistent delimiters)
- Users asking questions understand the general domain and content of their uploaded data
- Natural language questions are in English (internationalization is out of scope)
- Users have reliable internet connectivity for web application access
- Uploaded CSV data is primarily structured/tabular (not free-form text documents)
- System will be deployed in an environment with sufficient computational resources for semantic search and query processing
- Users expect responses in near-real-time (within seconds for typical queries, longer acceptable for very large datasets)
- Multiple users may access the system simultaneously in a shared data environment
- Data is isolated per user using username-based database schema tenancy
- System is deployed as a demo/prototype environment, not intended for production use with real data, allowing simplified username-only authentication for ease of testing
- Users understand that very large CSV files (multi-GB) may require longer processing times
- Infrastructure can scale storage capacity as needed to accommodate unlimited file sizes
- Users will practice reasonable data management (not uploading unnecessarily large files)

## Out of Scope

- Real-time CSV file editing or modification after upload
- Integration with external data sources (databases, APIs, cloud storage) beyond local CSV uploads
- Advanced data visualization (charts, graphs) - only formatted text responses
- Machine learning model training or retraining based on user feedback
- Automated data quality improvement or cleaning beyond basic validation
- Export of query results to other formats (Excel, PDF, etc.)
- Scheduled or automated queries (system is interactive only)
- Version control or historical tracking of uploaded CSV files
- Support for file formats other than CSV (Excel, JSON, Parquet, etc.)
- Mobile native applications (mobile web browser access is in scope)
- API versioning and backward compatibility (deferred to production-ready phase; breaking changes allowed during demo/prototype development)

## Dependencies

- **Database**: PostgreSQL 17 with pgvector extension for vector similarity search
- **Computational Resources**: Minimum 4 CPU cores, 8GB RAM for application server; 16GB RAM recommended for handling concurrent users and large datasets; GPU acceleration optional but recommended for semantic search performance (reduces embedding generation time by 50-70%)
- **Storage**: Scalable storage with minimum 100GB initial capacity, expandable based on user data (estimate 1.5x raw CSV size for ingested data including indexes and vectors)
- **Web Hosting**: HTTPS-enabled web server infrastructure with TLS 1.2+ for secure communication
- **External Dependencies**: Anthropic API with Claude Opus model for text generation (SQL queries, HTML responses) and embedding provider for semantic search (OpenAI text-embedding-3-small or compatible); system requires API connectivity for LLM functionality. When LLM API calls fail (rate limits, service unavailable, network errors), requests are buffered and retried automatically with exponential backoff (1s, 2s, 4s, 8s delays) up to 3 retry attempts; users see "Processing..." state during retries

## Risks

- **Performance Risk**: Very large CSV files (multi-GB) or complex multi-dataset queries may exceed acceptable response times
  - *Mitigation*: Implement streaming ingestion for large files, 30-second query timeout with user cancellation, progress indicators, and clear performance expectations; use background thread processing with ThreadPoolExecutor for very large uploads
- **Storage Risk**: Unlimited file uploads with indefinite retention may consume excessive storage capacity
  - *Mitigation*: Monitor storage usage per user, implement user quotas (FR-041: 10GB default), provide user-controlled deletion tools for datasets and query history (FR-016), notify users when approaching quota limits with cleanup recommendations
- **Resource Exhaustion Risk**: Users uploading extremely large files may monopolize system resources
  - *Mitigation*: Implement upload queuing, rate limiting per user, background processing for large files, resource monitoring and alerts
- **Accuracy Risk**: Natural language understanding may misinterpret questions, leading to incorrect answers
  - *Mitigation*: Provide confidence scores with answers, allow users to refine questions, structured logging of all queries with timing enables analysis and improvement
- **Data Quality Risk**: Malformed or inconsistent CSV files may cause ingestion failures or corrupt results
  - *Mitigation*: Robust validation during upload, clear error messages, data preview before ingestion, graceful handling of format variations
- **Concurrency Risk**: Multiple concurrent users performing complex queries may overload system resources
  - *Mitigation*: Implement request queuing, resource limits per user, scale infrastructure as needed, prioritize interactive queries
- **Semantic Search Risk**: Semantic understanding may not work well for highly specialized or technical domain terminology
  - *Mitigation*: Combine with exact matching as fallback, allow users to provide domain-specific synonyms or mappings
- **Multi-Tenancy Risk**: Username-based schema isolation may have security vulnerabilities or performance implications
  - *Mitigation*: Implement robust schema-level access controls, regular security audits, performance testing with multiple concurrent schemas
- **LLM API Availability Risk**: External LLM service (OpenAI or compatible) may become unavailable due to rate limits, service outages, or network failures, blocking query processing
  - *Mitigation*: Automatic retry with exponential backoff (3 attempts: 1s, 2s, 4s delays), queue failed requests for retry, show clear "Processing..." state to users during retries, fail gracefully with error message if all retries exhausted
