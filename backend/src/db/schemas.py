"""Database schema definitions for user-specific schemas.

Centralized schema definitions used by both migrations and runtime schema creation
to ensure consistency and eliminate code duplication.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

# Schema SQL templates - use with schema_name parameter
# Format: .format(schema_name="user_username")

DATASETS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    table_name VARCHAR(63) NOT NULL UNIQUE,
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    row_count BIGINT NOT NULL,
    column_count INTEGER NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    schema_json JSONB NOT NULL,

    CONSTRAINT positive_row_count CHECK (row_count >= 0),
    CONSTRAINT positive_column_count CHECK (column_count > 0),
    CONSTRAINT positive_file_size CHECK (file_size_bytes > 0),
    CONSTRAINT valid_table_name CHECK (table_name ~ '^[a-z][a-z0-9_]{{0,62}}$')
)
"""

DATASETS_UPLOADED_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_datasets_uploaded
ON {schema_name}.datasets (uploaded_at DESC)
"""

DATASETS_FILENAME_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_datasets_filename
ON {schema_name}.datasets (filename)
"""

COLUMN_MAPPINGS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.column_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    inferred_type VARCHAR(50) NOT NULL,
    semantic_type VARCHAR(100),
    description TEXT,
    embedding vector(1536),
    _fulltext TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(column_name, '') || ' ' || coalesce(description, ''))
    ) STORED,

    UNIQUE (dataset_id, column_name)
)
"""

COLUMN_MAPPINGS_DATASET_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_column_mappings_dataset
ON {schema_name}.column_mappings (dataset_id)
"""

COLUMN_MAPPINGS_EMBEDDING_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_column_mappings_embedding
ON {schema_name}.column_mappings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
"""

COLUMN_MAPPINGS_FULLTEXT_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_column_mappings_fulltext
ON {schema_name}.column_mappings
USING GIN (_fulltext)
"""

CROSS_REFERENCES_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.cross_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_dataset_id UUID NOT NULL
        REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
    source_column VARCHAR(255) NOT NULL,
    target_dataset_id UUID NOT NULL
        REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
    target_column VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL CHECK (relationship_type IN ('foreign_key', 'shared_values', 'similar_values')),
    confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (source_dataset_id, source_column, target_dataset_id, target_column)
)
"""

CROSS_REFERENCES_SOURCE_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_cross_refs_source
ON {schema_name}.cross_references (source_dataset_id)
"""

CROSS_REFERENCES_TARGET_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_cross_refs_target
ON {schema_name}.cross_references (target_dataset_id)
"""

QUERIES_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    dataset_ids JSONB,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'timeout')),
    generated_sql TEXT,
    query_params JSONB,
    result_count INTEGER,
    execution_time_ms INTEGER,
    progress_message TEXT,
    progress_timeline JSONB,
    agent_logs TEXT,

    CONSTRAINT positive_execution_time CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
    CONSTRAINT positive_result_count CHECK (result_count IS NULL OR result_count >= 0)
)
"""

QUERIES_SUBMITTED_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_queries_submitted
ON {schema_name}.queries (submitted_at DESC)
"""

QUERIES_STATUS_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_queries_status
ON {schema_name}.queries (status)
WHERE status IN ('pending', 'processing')
"""

RESPONSES_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES {schema_name}.queries(id) ON DELETE CASCADE,
    html_content TEXT NOT NULL,
    plain_text TEXT NOT NULL,
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    data_snapshot JSONB,

    UNIQUE (query_id)
)
"""

RESPONSES_QUERY_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_responses_query
ON {schema_name}.responses (query_id)
"""

RESPONSES_GENERATED_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_responses_generated
ON {schema_name}.responses (generated_at DESC)
"""

COLUMN_METADATA_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.column_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    min_value TEXT,
    max_value TEXT,
    distinct_count BIGINT,
    null_count BIGINT,
    top_values JSONB,
    computed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (dataset_id, column_name),
    CONSTRAINT positive_distinct_count CHECK (distinct_count IS NULL OR distinct_count >= 0),
    CONSTRAINT positive_null_count CHECK (null_count IS NULL OR null_count >= 0)
)
"""

COLUMN_METADATA_DATASET_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_column_metadata_dataset
ON {schema_name}.column_metadata (dataset_id)
"""

COLUMN_METADATA_TOP_VALUES_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_column_metadata_top_values
ON {schema_name}.column_metadata
USING GIN (top_values)
"""

INDEX_METADATA_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS {schema_name}.index_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES {schema_name}.datasets(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    index_name VARCHAR(255) NOT NULL,
    index_type VARCHAR(50) NOT NULL,
    capability VARCHAR(50) NOT NULL,
    generated_column_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, column_name, index_type)
)
"""

INDEX_METADATA_DATASET_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_index_metadata_dataset
ON {schema_name}.index_metadata (dataset_id)
"""

INDEX_METADATA_CAPABILITY_INDEX_SQL: str = """
CREATE INDEX IF NOT EXISTS idx_index_metadata_capability
ON {schema_name}.index_metadata (capability)
"""
