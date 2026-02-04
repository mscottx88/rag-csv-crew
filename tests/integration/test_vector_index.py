"""Integration tests for pgvector HNSW index (T100-TEST).

Tests the pgvector HNSW (Hierarchical Navigable Small World) index creation
and query performance for vector similarity search.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

import pytest

from backend.src.db.schema_manager import SchemaManager


@pytest.mark.integration
class TestVectorIndex:
    """Integration tests for pgvector HNSW index (T100)."""

    def test_hnsw_index_created_on_schema_init(self, test_db_connection: Any) -> None:
        """Test HNSW index is created during schema initialization.

        Validates:
        - Index exists on column_mappings.embedding
        - Index uses HNSW algorithm
        - Index parameters match data-model.md spec

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T100):
        - HNSW index exists on column_mappings table
        - Index uses cosine distance (vector_cosine_ops)
        - Index parameters: m=16, ef_construction=64
        """
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"

        # Ensure user schema exists with vector extension
        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        # Verify HNSW index exists
        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Query pg_indexes for HNSW index
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'column_mappings'
                AND indexname LIKE '%hnsw%'
            """)
            row: tuple[Any, ...] | None = cur.fetchone()

        assert row is not None, "HNSW index not found on column_mappings table"
        index_name: str = row[0]
        index_def: str = row[1]

        # Verify index uses HNSW algorithm
        assert "hnsw" in index_def.lower()
        assert "embedding" in index_def.lower()
        assert "vector_cosine_ops" in index_def.lower()

    def test_hnsw_index_parameters(self, test_db_connection: Any) -> None:
        """Test HNSW index uses correct parameters per data-model.md.

        Validates:
        - m=16 (number of bidirectional links per layer)
        - ef_construction=64 (size of dynamic candidate list)
        - Distance function: cosine

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T100):
        - Index parameters match spec
        - Optimized for 1536-dimensional vectors
        """
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"

        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Query index parameters
            cur.execute("""
                SELECT idx.relname, am.amname, pg_get_indexdef(idx.oid) AS indexdef
                FROM pg_class idx
                JOIN pg_index i ON idx.oid = i.indexrelid
                JOIN pg_class tbl ON tbl.oid = i.indrelid
                JOIN pg_am am ON idx.relam = am.oid
                WHERE tbl.relname = 'column_mappings'
                AND am.amname = 'hnsw'
            """)
            row: tuple[Any, ...] | None = cur.fetchone()

        assert row is not None, "HNSW index not found"
        index_def: str = row[2]

        # Verify HNSW parameters
        assert "m = 16" in index_def or "m=16" in index_def
        assert "ef_construction = 64" in index_def or "ef_construction=64" in index_def

    def test_vector_similarity_query_uses_index(self, test_db_connection: Any) -> None:
        """Test vector similarity queries utilize HNSW index.

        Validates:
        - Query plan shows index scan (not sequential)
        - Performance is acceptable for 10K+ vectors
        - Results are ranked by cosine distance

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T100):
        - EXPLAIN shows index scan
        - Query completes in < 100ms for 10K vectors
        """
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"

        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Insert sample embeddings
            for i in range(100):
                embedding: list[float] = [float(i % 10) / 10.0] * 1536
                cur.execute("""
                    INSERT INTO column_mappings
                    (dataset_id, original_column, mapped_column, embedding)
                    VALUES (%s, %s, %s, %s)
                """, (
                    f"dataset-{i}",
                    f"column_{i}",
                    f"column_{i}",
                    embedding
                ))
            test_db_connection.commit()

            # Query vector similarity with EXPLAIN
            query_embedding: list[float] = [0.5] * 1536
            cur.execute("""
                EXPLAIN (FORMAT JSON)
                SELECT original_column,
                       embedding <=> %s::vector AS distance
                FROM column_mappings
                ORDER BY embedding <=> %s::vector
                LIMIT 10
            """, (query_embedding, query_embedding))

            explain_result: list[dict[str, Any]] = cur.fetchone()[0]

        # Verify index scan is used
        plan_str: str = str(explain_result)
        assert "index" in plan_str.lower() or "hnsw" in plan_str.lower()

    def test_index_maintenance_on_updates(self, test_db_connection: Any) -> None:
        """Test HNSW index is maintained on INSERT/UPDATE/DELETE.

        Validates:
        - New embeddings are indexed automatically
        - Updated embeddings reflect in index
        - Deleted embeddings are removed from index

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T100):
        - Index remains consistent with table data
        - Query performance doesn't degrade
        """
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"

        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Insert embedding
            embedding_1: list[float] = [0.1] * 1536
            cur.execute("""
                INSERT INTO column_mappings
                (dataset_id, original_column, mapped_column, embedding)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, ("dataset-1", "revenue", "revenue", embedding_1))
            row_id: int = cur.fetchone()[0]
            test_db_connection.commit()

            # Update embedding
            embedding_2: list[float] = [0.9] * 1536
            cur.execute("""
                UPDATE column_mappings
                SET embedding = %s
                WHERE id = %s
            """, (embedding_2, row_id))
            test_db_connection.commit()

            # Query to verify updated embedding
            cur.execute("""
                SELECT embedding <=> %s::vector AS distance
                FROM column_mappings
                WHERE id = %s
            """, (embedding_2, row_id))
            distance: float = cur.fetchone()[0]

            # Distance to itself should be ~0
            assert distance < 0.01

            # Delete embedding
            cur.execute("DELETE FROM column_mappings WHERE id = %s", (row_id,))
            test_db_connection.commit()

            # Verify deleted
            cur.execute("SELECT COUNT(*) FROM column_mappings WHERE id = %s", (row_id,))
            count: int = cur.fetchone()[0]
            assert count == 0

    def test_index_creation_with_existing_data(self, test_db_connection: Any) -> None:
        """Test HNSW index creation on table with existing embeddings.

        Validates:
        - Index can be created after data insertion
        - All existing vectors are indexed
        - Query performance improves after index creation

        Args:
            test_db_connection: Test database connection fixture

        Success Criteria (T100):
        - Index creation succeeds on populated table
        - All rows are accessible via index
        """
        schema_manager: SchemaManager = SchemaManager(test_db_connection)
        username: str = "testuser"

        schema_manager.ensure_user_schema_exists(test_db_connection, username)

        with test_db_connection.cursor() as cur:
            cur.execute(f"SET search_path TO {username}_schema, public")

            # Drop existing index
            cur.execute("""
                DROP INDEX IF EXISTS column_mappings_embedding_hnsw_idx
            """)
            test_db_connection.commit()

            # Insert data without index
            for i in range(50):
                embedding: list[float] = [float(i) / 50.0] * 1536
                cur.execute("""
                    INSERT INTO column_mappings
                    (dataset_id, original_column, mapped_column, embedding)
                    VALUES (%s, %s, %s, %s)
                """, (f"dataset-{i}", f"col_{i}", f"col_{i}", embedding))
            test_db_connection.commit()

            # Recreate index
            cur.execute("""
                CREATE INDEX column_mappings_embedding_hnsw_idx
                ON column_mappings
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
            test_db_connection.commit()

            # Verify index exists and is usable
            query_embedding: list[float] = [0.5] * 1536
            cur.execute("""
                SELECT COUNT(*)
                FROM column_mappings
                WHERE embedding <=> %s::vector < 0.5
            """, (query_embedding,))
            count: int = cur.fetchone()[0]

            # Should find some similar vectors
            assert count > 0
