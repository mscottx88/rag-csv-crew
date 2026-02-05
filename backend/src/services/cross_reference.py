"""Cross-reference detection and relationship classification service.

Implements FR-010: Automatic relationship detection between datasets based on
value overlap analysis.

Relationship Types:
- foreign_key: Exact value matches with high cardinality (primary key references)
- shared_values: Partial overlap (categorical values, taxonomies)
- similar_values: Fuzzy matches (name variations, typos)

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any

from psycopg import Connection
from psycopg_pool import ConnectionPool


class CrossReferenceService:
    """Service for detecting and classifying relationships between dataset columns."""

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        """Initialize CrossReferenceService.

        Args:
            pool: Database connection pool (optional for unit testing)
        """
        self.pool: ConnectionPool | None = pool

    def classify_relationship(
        self,
        source_values: list[Any],
        target_values: list[Any],
        use_fuzzy: bool = False,
    ) -> dict[str, Any] | None:
        """Classify relationship type between two columns based on value overlap.

        Args:
            source_values: Values from source column
            target_values: Values from target column
            use_fuzzy: Enable fuzzy string matching for similar_values

        Returns:
            Dictionary with relationship_type and confidence_score, or None if
            overlap is below threshold

        Raises:
            ValueError: If source_values or target_values are empty
        """
        if not source_values or not target_values:
            raise ValueError("Source and target values cannot be empty")

        # Filter out None/null values
        source_clean: list[Any] = [v for v in source_values if v is not None]
        target_clean: list[Any] = [v for v in target_values if v is not None]

        if not source_clean or not target_clean:
            return None

        # Convert to sets for overlap calculation (case-insensitive for strings)
        source_set: set[Any] = self._normalize_values(source_clean)
        target_set: set[Any] = self._normalize_values(target_clean)

        # Calculate overlap
        overlap: set[Any] = source_set & target_set
        overlap_count: int = len(overlap)

        if overlap_count == 0:
            # Try fuzzy matching if enabled and values are strings
            if use_fuzzy and self._are_strings(source_clean):
                return self._fuzzy_match(source_clean, target_clean)
            return None

        # Calculate confidence score based on overlap percentage
        source_size: int = len(source_set)
        target_size: int = len(target_set)
        overlap_ratio: float = overlap_count / min(source_size, target_size)

        # Adjust confidence based on sample size
        sample_size: int = min(len(source_clean), len(target_clean))
        confidence: float = self._calculate_confidence(overlap_ratio, sample_size)

        # Classify relationship type based on overlap characteristics
        if overlap_ratio >= 0.95 and self._is_foreign_key_pattern(
            source_set, target_set, source_size, target_size
        ):
            return {
                "relationship_type": "foreign_key",
                "confidence_score": confidence,
            }
        elif overlap_ratio >= 0.3:
            return {
                "relationship_type": "shared_values",
                "confidence_score": confidence,
            }
        else:
            return None

    def _normalize_values(self, values: list[Any]) -> set[Any]:
        """Normalize values for comparison (case-insensitive for strings).

        Args:
            values: List of values to normalize

        Returns:
            Set of normalized values
        """
        normalized: set[Any] = set()
        for v in values:
            if isinstance(v, str):
                normalized.add(v.lower().strip())
            else:
                normalized.add(v)
        return normalized

    def _are_strings(self, values: list[Any]) -> bool:
        """Check if values are predominantly strings.

        Args:
            values: List of values to check

        Returns:
            True if >80% of values are strings
        """
        if not values:
            return False
        string_count: int = sum(1 for v in values if isinstance(v, str))
        return string_count / len(values) > 0.8

    def _is_foreign_key_pattern(
        self,
        source_set: set[Any],
        target_set: set[Any],
        source_size: int,
        target_size: int,
    ) -> bool:
        """Check if relationship follows foreign key pattern.

        Foreign key pattern: source is subset of target, high cardinality.

        Args:
            source_set: Normalized source values
            target_set: Normalized target values
            source_size: Unique count in source
            target_size: Unique count in target

        Returns:
            True if foreign key pattern detected
        """
        # Source should be subset of target (or very close)
        is_subset: bool = source_set.issubset(target_set)

        # High cardinality check (many unique values)
        high_cardinality: bool = source_size > 5 and target_size > 5

        return is_subset and high_cardinality

    def _calculate_confidence(self, overlap_ratio: float, sample_size: int) -> float:
        """Calculate confidence score adjusted for sample size.

        Args:
            overlap_ratio: Ratio of overlapping values (0-1)
            sample_size: Number of samples compared

        Returns:
            Confidence score between 0 and 1
        """
        base_confidence: float = overlap_ratio

        # Reduce confidence for small samples (< 10 values)
        if sample_size < 10:
            size_penalty: float = sample_size / 10.0
            base_confidence *= size_penalty

        # Boost confidence for large samples (> 100 values)
        elif sample_size > 100:
            size_boost: float = min(1.1, 1.0 + (sample_size - 100) / 1000.0)
            base_confidence *= size_boost

        # Ensure confidence stays in [0, 1] range
        return min(1.0, max(0.0, base_confidence))

    def _fuzzy_match(
        self, source_values: list[str], target_values: list[str]
    ) -> dict[str, Any] | None:
        """Perform fuzzy string matching between values.

        Args:
            source_values: Source string values
            target_values: Target string values

        Returns:
            Relationship dict with similar_values type or None
        """
        # Simple fuzzy matching: check for substring matches
        # More sophisticated approaches (Levenshtein distance) can be added later
        matches: int = 0
        for source in source_values[:20]:  # Limit to first 20 for performance
            source_lower: str = source.lower().strip()
            for target in target_values:
                target_lower: str = target.lower().strip()
                if source_lower in target_lower or target_lower in source_lower:
                    matches += 1
                    break

        if matches == 0:
            return None

        # Calculate fuzzy confidence (conservative estimate)
        fuzzy_confidence: float = matches / min(len(source_values), 20)
        adjusted_confidence: float = fuzzy_confidence * 0.6  # Reduce for fuzzy matches

        return {
            "relationship_type": "similar_values",
            "confidence_score": adjusted_confidence,
        }

    def detect_cross_references(
        self,
        username: str,
        source_dataset_id: str,
        target_dataset_id: str,
        min_confidence: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Detect cross-references between two datasets.

        Args:
            username: Username for schema isolation
            source_dataset_id: Source dataset ID
            target_dataset_id: Target dataset ID
            min_confidence: Minimum confidence threshold (default 0.3)

        Returns:
            List of detected cross-references with metadata

        Raises:
            ValueError: If datasets not found or invalid parameters or pool not configured
        """
        if self.pool is None:
            raise ValueError("ConnectionPool required for detect_cross_references")

        user_schema: str = f"{username}_schema"
        cross_references: list[dict[str, Any]] = []

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # Set search path
                cur.execute(f"SET search_path TO {user_schema}, public")

                # Get columns from both datasets
                source_columns: list[tuple[str, ...]] = self._get_columns(
                    cur, source_dataset_id
                )
                target_columns: list[tuple[str, ...]] = self._get_columns(
                    cur, target_dataset_id
                )

                # Compare all column pairs
                for source_col_name, source_col_type in source_columns:
                    for target_col_name, target_col_type in target_columns:
                        # Only compare columns of compatible types
                        if not self._are_types_compatible(
                            source_col_type, target_col_type
                        ):
                            continue

                        # Get sample values from both columns
                        source_values: list[Any] = self._get_column_values(
                            cur, source_dataset_id, source_col_name
                        )
                        target_values: list[Any] = self._get_column_values(
                            cur, target_dataset_id, target_col_name
                        )

                        # Classify relationship
                        result: dict[str, Any] | None = self.classify_relationship(
                            source_values, target_values, use_fuzzy=True
                        )

                        if result and result["confidence_score"] >= min_confidence:
                            cross_references.append(
                                {
                                    "source_dataset_id": source_dataset_id,
                                    "source_column": source_col_name,
                                    "target_dataset_id": target_dataset_id,
                                    "target_column": target_col_name,
                                    "relationship_type": result["relationship_type"],
                                    "confidence_score": result["confidence_score"],
                                }
                            )

        return cross_references

    def _get_columns(
        self, cur: Any, dataset_id: str
    ) -> list[tuple[str, ...]]:
        """Get column names and types for a dataset.

        Args:
            cur: Database cursor
            dataset_id: Dataset ID

        Returns:
            List of (column_name, column_type) tuples
        """
        cur.execute(
            """
            SELECT column_name, data_type
            FROM column_mappings
            WHERE dataset_id = %s
            AND column_name NOT LIKE '_%'  -- Exclude metadata columns
            ORDER BY column_name
            """,
            (dataset_id,),
        )
        result: list[tuple[str, ...]] = cur.fetchall()
        return result

    def _get_column_values(
        self, cur: Any, dataset_id: str, column_name: str, limit: int = 1000
    ) -> list[Any]:
        """Get sample values from a column.

        Args:
            cur: Database cursor
            dataset_id: Dataset ID
            column_name: Column name
            limit: Maximum number of values to sample

        Returns:
            List of column values
        """
        # Get table name from datasets
        cur.execute(
            "SELECT filename FROM datasets WHERE id = %s",
            (dataset_id,),
        )
        row: tuple[str, ...] | None = cur.fetchone()
        if not row:
            return []

        table_name: str = f"{row[0].replace('.csv', '')}_data"

        # Sample distinct values
        cur.execute(
            f"""
            SELECT DISTINCT "{column_name}"
            FROM {table_name}
            WHERE "{column_name}" IS NOT NULL
            LIMIT %s
            """,
            (limit,),
        )
        rows: list[tuple[Any, ...]] = cur.fetchall()
        return [row[0] for row in rows]

    def _are_types_compatible(self, type1: str, type2: str) -> bool:
        """Check if two column types are compatible for comparison.

        Args:
            type1: First column type
            type2: Second column type

        Returns:
            True if types are compatible
        """
        # Numeric types
        numeric_types: set[str] = {"integer", "bigint", "numeric", "real", "double precision"}

        # Text types
        text_types: set[str] = {"text", "varchar", "character varying", "char"}

        # Date/time types
        date_types: set[str] = {"date", "timestamp", "timestamp with time zone"}

        if type1 in numeric_types and type2 in numeric_types:
            return True
        if type1 in text_types and type2 in text_types:
            return True
        if type1 in date_types and type2 in date_types:
            return True

        return False
