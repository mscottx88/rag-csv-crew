-- Initialize RAG CSV Crew database
-- This script runs automatically when the PostgreSQL container starts

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create public schema tables (system-wide)
CREATE TABLE IF NOT EXISTS public.users (
    username VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS public.query_log (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL REFERENCES public.users(username) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    log_level VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    request_id UUID,
    execution_time_ms INTEGER,
    result_count INTEGER,
    error_message TEXT,
    stack_trace TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_query_log_username ON public.query_log(username);
CREATE INDEX IF NOT EXISTS idx_query_log_timestamp ON public.query_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_log_event_type ON public.query_log(event_type);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE rag_csv_crew TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
