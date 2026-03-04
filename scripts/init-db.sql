-- Initialize RAG CSV Crew database
-- This script runs automatically when the PostgreSQL container starts for the first time.
-- The Python initialize_database() in backend/src/db/migrations.py is also called on
-- every app startup (idempotent) and is the authoritative schema definition.

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create public.users table (system-wide)
CREATE TABLE IF NOT EXISTS public.users (
    username     VARCHAR(50)  PRIMARY KEY,
    schema_name  VARCHAR(63)  NOT NULL UNIQUE,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT username_format CHECK (username ~ '^[a-z][a-z0-9_]{2,49}$')
);

CREATE INDEX IF NOT EXISTS idx_users_active
    ON public.users (is_active)
    WHERE is_active = TRUE;

-- Create public.query_log table (system-wide analytics)
CREATE TABLE IF NOT EXISTS public.query_log (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username         VARCHAR(50) NOT NULL REFERENCES public.users(username) ON DELETE CASCADE,
    query_text       TEXT        NOT NULL,
    submitted_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    execution_time_ms INTEGER,
    status           VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'timeout')),
    result_count     INTEGER,
    error_message    TEXT,

    CONSTRAINT positive_execution_time CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
    CONSTRAINT positive_result_count   CHECK (result_count IS NULL OR result_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_query_log_user_time
    ON public.query_log (username, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_log_status
    ON public.query_log (status)
    WHERE status IN ('pending', 'processing');

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE rag_csv_crew TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
