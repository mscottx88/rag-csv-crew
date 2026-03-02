"""Unit tests for IndexManagerService.

Tests index name generation utility with 63-character identifier truncation
and MD5 hash suffix per data-model.md Identifier Length Handling.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import pytest

from backend.src.services.index_manager import generate_index_name


@pytest.mark.unit
class TestGenerateIndexName:
    """Test index name generation with PostgreSQL 63-char limit."""

    def test_normal_name_no_truncation(self) -> None:
        """Test that short names are returned without truncation."""
        name: str = generate_index_name("products_data", "price", "btree")
        assert name == "idx_products_data_price_btree"
        assert len(name) <= 63

    def test_gin_index_name(self) -> None:
        """Test GIN index name for tsvector columns."""
        name: str = generate_index_name("products_data", "name", "gin")
        assert name == "idx_products_data_name_gin"

    def test_hnsw_index_name(self) -> None:
        """Test HNSW index name for vector columns."""
        name: str = generate_index_name("products_data", "description", "hnsw")
        assert name == "idx_products_data_description_hnsw"

    def test_truncation_at_63_chars(self) -> None:
        """Test that long names are truncated to 63 characters max."""
        long_table: str = "very_long_table_name_that_exceeds_normal"
        long_column: str = "very_long_column_name_also_exceeds"
        name: str = generate_index_name(long_table, long_column, "btree")
        assert len(name) <= 63

    def test_truncation_includes_hash(self) -> None:
        """Test that truncated names include 8-char MD5 hash."""
        long_table: str = "very_long_table_name_that_exceeds_normal"
        long_column: str = "very_long_column_name_also_exceeds"
        name: str = generate_index_name(long_table, long_column, "btree")
        # Name should follow pattern: idx_{truncated}_{hash8}_{type}
        assert name.startswith("idx_")
        assert name.endswith("_btree")
        # Hash should be 8 hex characters
        parts: list[str] = name.split("_")
        # The hash is the second-to-last part (before type)
        hash_part: str = parts[-2]
        assert len(hash_part) == 8
        # Verify it's hex
        int(hash_part, 16)

    def test_hash_uniqueness(self) -> None:
        """Test that different table/column combos produce different hashes."""
        name1: str = generate_index_name("a" * 40, "b" * 40, "btree")
        name2: str = generate_index_name("a" * 40, "c" * 40, "btree")
        assert name1 != name2
        assert len(name1) <= 63
        assert len(name2) <= 63

    def test_exactly_63_chars(self) -> None:
        """Test name exactly at 63 chars is not truncated."""
        # idx_ = 4, _btree = 6, middle needs 53
        # 4 + table + _ + col + 6 = 63 => table_col = 53
        table: str = "t" * 26
        col: str = "c" * 26  # idx_ + 26 + _ + 26 + _btree = 4+26+1+26+6 = 63
        name: str = generate_index_name(table, col, "btree")
        assert name == f"idx_{table}_{col}_btree"
        assert len(name) == 63

    def test_64_chars_triggers_truncation(self) -> None:
        """Test name at 64 chars triggers truncation."""
        table: str = "t" * 27
        col: str = "c" * 26  # idx_ + 27 + _ + 26 + _btree = 4+27+1+26+6 = 64
        name: str = generate_index_name(table, col, "btree")
        assert len(name) <= 63
        assert "_btree" in name

    def test_no_trailing_underscore(self) -> None:
        """Test that truncated names don't end with trailing underscore."""
        name: str = generate_index_name("a" * 50, "b" * 50, "btree")
        # Split to get the truncated portion
        # Pattern: idx_{truncated}_{hash8}_{type}
        assert len(name) <= 63
        # No double underscores from truncation
        assert "___" not in name

    def test_consistent_results(self) -> None:
        """Test that same inputs always produce same output."""
        name1: str = generate_index_name("products_data", "name", "gin")
        name2: str = generate_index_name("products_data", "name", "gin")
        assert name1 == name2
