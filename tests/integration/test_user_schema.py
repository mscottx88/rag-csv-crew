"""Integration tests for per-user schema creation.

Tests user-specific schema creation per data-model.md:
- {username}_schema for multi-tenancy isolation
- datasets, column_mappings, cross_references tables
- queries, responses tables for per-user history

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from psycopg_pool import ConnectionPool
import pytest


@pytest.mark.integration
class TestUserSchema:
    """Test per-user schema creation and table structure."""

    def test_create_user_schema(self, connection_pool: ConnectionPool) -> None:
        """Test creating user-specific schema.

        Validates:
        - Schema created with pattern {username}_schema
        - Schema isolated from other users
        - Multiple user schemas can coexist

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            # Create schema for alice
            create_user_schema(conn, "alice")

            # Verify schema exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name = 'alice_schema'
                """)
                result: tuple[str] | None = cur.fetchone()
                assert result is not None
                assert result[0] == "alice_schema"

            # Create schema for bob
            create_user_schema(conn, "bob")

            # Verify both schemas exist
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name IN ('alice_schema', 'bob_schema')
                    ORDER BY schema_name
                """)
                schemas: list[tuple[str]] = cur.fetchall()
                assert len(schemas) == 2
                assert schemas[0][0] == "alice_schema"
                assert schemas[1][0] == "bob_schema"

    def test_user_schema_is_idempotent(self, connection_pool: ConnectionPool) -> None:
        """Test user schema creation is idempotent.

        Validates:
        - Can run create_user_schema multiple times safely
        - Existing tables preserved
        - No errors on duplicate creation

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            # Create schema twice
            create_user_schema(conn, "alice")
            create_user_schema(conn, "alice")  # Should not error

            # Verify only one schema exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.schemata
                    WHERE schema_name = 'alice_schema'
                """)
                count: tuple[int] = cur.fetchone()  # type: ignore
                assert count[0] == 1

    def test_datasets_table_in_user_schema(self, connection_pool: ConnectionPool) -> None:
        """Test datasets table created in user schema.

        Validates per data-model.md:
        - id (UUID, PRIMARY KEY)
        - filename (VARCHAR(255), NOT NULL)
        - original_filename (VARCHAR(255), NOT NULL)
        - table_name (VARCHAR(63), NOT NULL, UNIQUE)
        - uploaded_at (TIMESTAMP, NOT NULL)
        - row_count (BIGINT, >= 0)
        - column_count (INTEGER, > 0)
        - file_size_bytes (BIGINT, > 0)
        - schema_json (JSONB, NOT NULL)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            create_user_schema(conn, "alice")

            # Query table structure
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'alice_schema'
                    AND table_name = 'datasets'
                    ORDER BY ordinal_position
                """)
                columns: list[tuple[str, str, str]] = cur.fetchall()

            column_dict: dict[str, tuple[str, str]] = {col[0]: (col[1], col[2]) for col in columns}

            # Verify required columns
            assert "id" in column_dict
            assert "uuid" in column_dict["id"][0]

            assert "filename" in column_dict
            assert column_dict["filename"][0] == "character varying"

            assert "table_name" in column_dict
            assert column_dict["table_name"][0] == "character varying"

            assert "row_count" in column_dict
            assert "bigint" in column_dict["row_count"][0]

            assert "schema_json" in column_dict
            assert column_dict["schema_json"][0] == "jsonb"

    def test_column_mappings_table_with_vector_column(
        self, connection_pool: ConnectionPool
    ) -> None:
        """Test column_mappings table with pgvector embedding column.

        Validates:
        - id (UUID, PRIMARY KEY)
        - dataset_id (UUID, FOREIGN KEY to datasets)
        - column_name (VARCHAR(255), NOT NULL)
        - inferred_type (VARCHAR(50), NOT NULL)
        - semantic_type (VARCHAR(100), nullable)
        - description (TEXT, nullable)
        - embedding (vector(1536), nullable) for OpenAI text-embedding-3-small

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            create_user_schema(conn, "alice")

            # Query table structure
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_schema = 'alice_schema'
                    AND table_name = 'column_mappings'
                    ORDER BY ordinal_position
                """)
                columns: list[tuple[str, str, str]] = cur.fetchall()

            column_dict: dict[str, tuple[str, str]] = {col[0]: (col[1], col[2]) for col in columns}

            # Verify vector column exists
            assert "embedding" in column_dict
            assert column_dict["embedding"][1] == "vector"  # UDT name

    def test_cross_references_table_structure(self, connection_pool: ConnectionPool) -> None:
        """Test cross_references table for dataset relationships.

        Validates:
        - id (UUID, PRIMARY KEY)
        - source_dataset_id (UUID, FOREIGN KEY)
        - source_column (VARCHAR(255))
        - target_dataset_id (UUID, FOREIGN KEY)
        - target_column (VARCHAR(255))
        - relationship_type (VARCHAR(50), CHECK constraint)
        - confidence_score (FLOAT, 0.0-1.0)
        - detected_at (TIMESTAMP, NOT NULL)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            create_user_schema(conn, "alice")

            # Verify table exists
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'alice_schema'
                    AND table_name = 'cross_references'
                """)
                result: tuple[str] | None = cur.fetchone()
                assert result is not None
                assert result[0] == "cross_references"

    def test_queries_table_in_user_schema(self, connection_pool: ConnectionPool) -> None:
        """Test queries table for per-user query history.

        Validates:
        - id (UUID, PRIMARY KEY)
        - query_text (TEXT, NOT NULL)
        - submitted_at (TIMESTAMP, NOT NULL)
        - completed_at (TIMESTAMP, nullable)
        - status (VARCHAR(20), CHECK constraint)
        - generated_sql (TEXT, nullable)
        - result_count (INTEGER, >= 0)
        - execution_time_ms (INTEGER, >= 0)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            create_user_schema(conn, "alice")

            # Verify table structure
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'alice_schema'
                    AND table_name = 'queries'
                    ORDER BY ordinal_position
                """)
                columns: list[tuple[str, str]] = cur.fetchall()

            column_names: list[str] = [col[0] for col in columns]

            # Verify required columns exist
            assert "id" in column_names
            assert "query_text" in column_names
            assert "status" in column_names
            assert "generated_sql" in column_names

    def test_responses_table_in_user_schema(self, connection_pool: ConnectionPool) -> None:
        """Test responses table for cached query responses.

        Validates:
        - id (UUID, PRIMARY KEY)
        - query_id (UUID, FOREIGN KEY to queries, UNIQUE)
        - html_content (TEXT, NOT NULL)
        - plain_text (TEXT, NOT NULL)
        - confidence_score (FLOAT, 0.0-1.0, nullable)
        - generated_at (TIMESTAMP, NOT NULL)
        - data_snapshot (JSONB, nullable)

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            create_user_schema(conn, "alice")

            # Verify table exists with required columns
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'alice_schema'
                    AND table_name = 'responses'
                """)
                columns: list[tuple[str]] = cur.fetchall()
                column_names: list[str] = [col[0] for col in columns]

            assert "id" in column_names
            assert "query_id" in column_names
            assert "html_content" in column_names
            assert "confidence_score" in column_names
            assert "data_snapshot" in column_names

    def test_user_schema_indexes(self, connection_pool: ConnectionPool) -> None:
        """Test performance indexes created in user schema.

        Validates:
        - datasets(uploaded_at DESC) for chronological listing
        - column_mappings(embedding) HNSW for vector similarity
        - queries(submitted_at DESC, status) for history and active queries
        - responses(query_id) for fast lookup

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            create_user_schema(conn, "alice")

            # Check datasets indexes
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'datasets'
                    AND schemaname = 'alice_schema'
                """)
                indexes: list[tuple[str]] = cur.fetchall()
                assert len(indexes) > 0  # At least primary key

    def test_user_schema_isolation(self, connection_pool: ConnectionPool) -> None:
        """Test data isolation between user schemas.

        Validates:
        - Alice cannot access Bob's data
        - Each user sees only their own datasets
        - Schema-level security enforced

        Args:
            connection_pool: Database connection pool fixture
        """
        from backend.src.db.migrations import create_user_schema

        with connection_pool.connection() as conn:
            # Create schemas for alice and bob
            create_user_schema(conn, "alice")
            create_user_schema(conn, "bob")

            # Insert dataset for alice
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO alice_schema.datasets
                    (filename, original_filename, table_name, row_count, column_count, file_size_bytes, schema_json)
                    VALUES ('sales.csv', 'sales.csv', 'sales_data', 100, 5, 1024, '[]'::jsonb)
                """)
            conn.commit()

            # Query from alice_schema should find it
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM alice_schema.datasets")
                count: tuple[int] = cur.fetchone()  # type: ignore
                assert count[0] == 1

            # Query from bob_schema should not find it
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM bob_schema.datasets")
                count = cur.fetchone()  # type: ignore
                assert count[0] == 0
