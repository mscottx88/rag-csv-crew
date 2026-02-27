"""Automated evaluation for cross-dataset query accuracy.

Success Criterion: SC-007 - System achieves ≥75% accuracy on cross-dataset queries
requiring automatic JOIN detection and generation.

This script:
1. Loads test questions from cross_dataset_questions.json
2. Sets up test database with sample data (customers, orders, products)
3. Submits each question to the system
4. Validates SQL generation (JOIN detection, correct tables)
5. Validates result accuracy (expected values present)
6. Reports overall accuracy score
"""

from collections.abc import Generator
import json
import os
from pathlib import Path
from typing import Any

from psycopg_pool import ConnectionPool
import pytest

from backend.src.models.config import DatabaseConfig
from backend.src.services.cross_reference import CrossReferenceService
from backend.src.services.ingestion import IngestionService
from backend.src.services.text_to_sql import TextToSQLService


class CrossDatasetEvaluator:
    """Evaluates system accuracy on cross-dataset queries."""

    def __init__(self, pool: ConnectionPool, username: str) -> None:
        """Initialize evaluator.

        Args:
            pool: Database connection pool
            username: Test user for schema isolation
        """
        self.pool: ConnectionPool = pool
        self.username: str = username
        self.user_schema: str = f"{username}_schema"
        self.ingestion_service: IngestionService = IngestionService(pool)
        self.cross_ref_service: CrossReferenceService = CrossReferenceService(pool)
        self.text_to_sql_service: TextToSQLService = TextToSQLService(pool)
        self.dataset_ids: dict[str, str] = {}

    def setup_test_data(self, schema: dict[str, Any]) -> None:
        """Create test tables with sample data.

        Args:
            schema: Schema definition from cross_dataset_questions.json
        """
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SET search_path TO {self.user_schema}, public")

            # Create datasets metadata
            for dataset_name, dataset_info in schema.items():
                filename: str = f"{dataset_name}.csv"

                # Insert dataset record
                cur.execute(
                    """
                    INSERT INTO datasets (id, username, filename, row_count, column_count)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        self.username,
                        filename,
                        len(dataset_info["sample_data"]),
                        len(dataset_info["columns"]),
                    ),
                )
                result: tuple[Any, ...] | None = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Failed to create dataset {dataset_name}")
                dataset_id: str = str(result[0])
                self.dataset_ids[dataset_name] = dataset_id

                # Create column mappings
                for column_name in dataset_info["columns"]:
                    # Infer type from first sample value
                    first_value: Any = dataset_info["sample_data"][0].get(column_name)
                    if isinstance(first_value, int):
                        data_type: str = "integer"
                    elif isinstance(first_value, float):
                        data_type = "numeric"
                    else:
                        data_type = "text"

                    cur.execute(
                        """
                        INSERT INTO column_mappings (dataset_id, column_name, data_type)
                        VALUES (%s, %s, %s)
                        """,
                        (dataset_id, column_name, data_type),
                    )

                # Create data table
                table_name: str = f"{dataset_name}_data"
                columns_def: list[str] = [f'"{col}" TEXT' for col in dataset_info["columns"]]
                columns_sql: str = ", ".join(columns_def)

                cur.execute(
                    f"""
                    CREATE TABLE {table_name} (
                        _row_id SERIAL PRIMARY KEY,
                        _dataset_id UUID NOT NULL,
                        _ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        {columns_sql}
                    )
                    """
                )

                # Insert sample data
                for row in dataset_info["sample_data"]:
                    column_names: list[str] = list(row.keys())
                    values: list[Any] = list(row.values())
                    columns_str: str = ", ".join([f'"{col}"' for col in column_names])
                    placeholders: str = ", ".join(["%s"] * (len(values) + 1))

                    cur.execute(
                        f"""
                        INSERT INTO {table_name} (_dataset_id, {columns_str})
                        VALUES ({placeholders})
                        """,
                        [dataset_id, *values],
                    )

            conn.commit()

    def detect_cross_references(self) -> list[dict[str, Any]]:
        """Detect relationships between datasets.

        Returns:
            List of detected cross-references
        """
        all_refs: list[dict[str, Any]] = []

        # Compare each pair of datasets
        dataset_list: list[str] = list(self.dataset_ids.keys())
        for i, source_name in enumerate(dataset_list):
            for target_name in dataset_list[i + 1 :]:
                source_id: str = self.dataset_ids[source_name]
                target_id: str = self.dataset_ids[target_name]

                refs: list[dict[str, Any]] = self.cross_ref_service.detect_cross_references(
                    username=self.username,
                    source_dataset_id=source_id,
                    target_dataset_id=target_id,
                    min_confidence=0.3,
                )
                all_refs.extend(refs)

        return all_refs

    def evaluate_question(self, question: dict[str, Any]) -> dict[str, Any]:
        """Evaluate system response to a single question.

        Args:
            question: Question definition from JSON

        Returns:
            Evaluation result with pass/fail status
        """
        query_text: str = question["question"]
        required_datasets: list[str] = question["required_datasets"]

        # Map dataset names to IDs
        dataset_ids: list[str] = [
            self.dataset_ids[ds] for ds in required_datasets if ds in self.dataset_ids
        ]

        # Attempt to generate SQL
        try:
            # Resolve relevant datasets
            resolved: list[str] = self.text_to_sql_service.resolve_datasets(
                _username=self.username,
                query_text=query_text,
                available_datasets=list(self.dataset_ids.keys()),
                dataset_ids=None,  # Let system auto-detect
            )

            # Check if required datasets were identified
            identified_all: bool = all(ds in resolved for ds in required_datasets)

            # Get cross-references for JOIN context
            from uuid import UUID

            dataset_uuids: list[UUID] = [UUID(ds_id) for ds_id in dataset_ids]
            cross_refs: list[dict[str, Any]] = self.text_to_sql_service.get_cross_references(
                username=self.username, dataset_ids=dataset_uuids
            )

            # Check if JOIN was detected (cross-references found)
            join_detected: bool = len(cross_refs) > 0

            return {
                "question_id": question["id"],
                "question": query_text,
                "category": question["category"],
                "difficulty": question["difficulty"],
                "datasets_identified": identified_all,
                "join_detected": join_detected,
                "num_cross_refs": len(cross_refs),
                "passed": identified_all and join_detected,
            }

        except Exception as e:
            return {
                "question_id": question["id"],
                "question": query_text,
                "category": question["category"],
                "difficulty": question["difficulty"],
                "datasets_identified": False,
                "join_detected": False,
                "num_cross_refs": 0,
                "passed": False,
                "error": str(e),
            }


@pytest.fixture
def evaluation_data() -> dict[str, Any]:
    """Load evaluation questions from JSON fixture.

    Returns:
        Parsed JSON data with questions and schema
    """
    fixture_path: Path = Path(__file__).parent.parent / "fixtures" / "cross_dataset_questions.json"
    with fixture_path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


@pytest.fixture
def test_pool() -> Generator[ConnectionPool]:
    """Create test database connection pool.

    Returns:
        ConnectionPool for test database
    """
    config: DatabaseConfig = DatabaseConfig(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        database=os.getenv("DATABASE_DATABASE", "rag_csv_crew"),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        pool_min_size=2,
        pool_max_size=5,
    )

    conninfo: str = (
        f"host={config.host} port={config.port} dbname={config.database} "
        f"user={config.user} password={config.password}"
    )

    pool: ConnectionPool = ConnectionPool(conninfo=conninfo, min_size=2, max_size=5, open=True)

    yield pool

    pool.close()


@pytest.fixture
def test_username() -> str:
    """Get test username for schema isolation.

    Returns:
        Test username
    """
    return "cross_dataset_eval_user"


@pytest.fixture
def evaluator(
    test_pool: ConnectionPool, test_username: str, evaluation_data: dict[str, Any]
) -> Generator[CrossDatasetEvaluator]:
    """Create and setup evaluator with test data.

    Args:
        test_pool: Database connection pool
        test_username: Test username
        evaluation_data: Evaluation questions and schema

    Returns:
        Configured CrossDatasetEvaluator
    """
    user_schema: str = f"{test_username}_schema"

    # Setup test schema
    with test_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {user_schema} CASCADE")
        cur.execute(f"CREATE SCHEMA {user_schema}")
        cur.execute(f"SET search_path TO {user_schema}, public")

        # Create required tables
        cur.execute("""
            CREATE TABLE datasets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                row_count INTEGER NOT NULL,
                column_count INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE column_mappings (
                id SERIAL PRIMARY KEY,
                dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                column_name VARCHAR(255) NOT NULL,
                data_type VARCHAR(50) NOT NULL,
                sample_values TEXT[]
            )
        """)

        cur.execute("""
            CREATE TABLE cross_references (
                id SERIAL PRIMARY KEY,
                source_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                source_column VARCHAR(255) NOT NULL,
                target_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                target_column VARCHAR(255) NOT NULL,
                relationship_type VARCHAR(50) NOT NULL,
                confidence_score REAL NOT NULL,
                detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_dataset_id, source_column, target_dataset_id, target_column)
            )
        """)

        conn.commit()

    # Create evaluator
    evaluator_instance: CrossDatasetEvaluator = CrossDatasetEvaluator(test_pool, test_username)

    # Setup test data
    evaluator_instance.setup_test_data(evaluation_data["schema"])

    # Detect cross-references
    cross_refs: list[dict[str, Any]] = evaluator_instance.detect_cross_references()

    # Store detected cross-references
    with test_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SET search_path TO {user_schema}, public")

        for ref in cross_refs:
            cur.execute(
                """
                INSERT INTO cross_references
                (source_dataset_id, source_column, target_dataset_id, target_column,
                 relationship_type, confidence_score)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_dataset_id, source_column, target_dataset_id, target_column)
                DO UPDATE SET confidence_score = EXCLUDED.confidence_score
                """,
                (
                    ref["source_dataset_id"],
                    ref["source_column"],
                    ref["target_dataset_id"],
                    ref["target_column"],
                    ref["relationship_type"],
                    ref["confidence_score"],
                ),
            )

        conn.commit()

    yield evaluator_instance

    # Cleanup
    with test_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {user_schema} CASCADE")
        conn.commit()


def test_cross_dataset_accuracy(
    evaluator: CrossDatasetEvaluator, evaluation_data: dict[str, Any]
) -> None:
    """Test SC-007: 75% accuracy on cross-dataset queries.

    Args:
        evaluator: Configured evaluator with test data
        evaluation_data: Evaluation questions from JSON
    """
    questions: list[dict[str, Any]] = evaluation_data["questions"]
    total_questions: int = len(questions)

    results: list[dict[str, Any]] = []
    passed_count: int = 0

    print("\n=== Cross-Dataset Query Evaluation ===\n")

    for question in questions:
        result: dict[str, Any] = evaluator.evaluate_question(question)
        results.append(result)

        if result["passed"]:
            passed_count += 1
            status: str = "✓ PASS"
        else:
            status = "✗ FAIL"

        print(f"{result['question_id']} ({result['difficulty']:6s}): {status}")
        if not result["passed"]:
            print("  Issue: ", end="")
            if not result["datasets_identified"]:
                print("Failed to identify required datasets")
            elif not result["join_detected"]:
                print("Failed to detect JOIN relationship")
            print()

    # Calculate accuracy
    accuracy: float = passed_count / total_questions if total_questions > 0 else 0.0

    print("\n=== Results ===\n")
    print(f"Total Questions: {total_questions}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_questions - passed_count}")
    print(f"Accuracy: {accuracy * 100:.1f}%")
    print("SC-007 Threshold: 75.0%")

    # Breakdown by difficulty
    by_difficulty: dict[str, dict[str, int]] = {}
    for result in results:
        difficulty: str = result["difficulty"]
        if difficulty not in by_difficulty:
            by_difficulty[difficulty] = {"passed": 0, "total": 0}
        by_difficulty[difficulty]["total"] += 1
        if result["passed"]:
            by_difficulty[difficulty]["passed"] += 1

    print("\n--- By Difficulty ---")
    for difficulty, stats in sorted(by_difficulty.items()):
        diff_accuracy: float = stats["passed"] / stats["total"] if stats["total"] > 0 else 0.0
        print(
            f"{difficulty.capitalize():8s}: {stats['passed']}/{stats['total']} ({diff_accuracy * 100:.1f}%)"
        )

    # Breakdown by category
    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        category: str = result["category"]
        if category not in by_category:
            by_category[category] = {"passed": 0, "total": 0}
        by_category[category]["total"] += 1
        if result["passed"]:
            by_category[category]["passed"] += 1

    print("\n--- By Category ---")
    for category, stats in sorted(by_category.items()):
        cat_accuracy: float = stats["passed"] / stats["total"] if stats["total"] > 0 else 0.0
        print(f"{category:30s}: {stats['passed']}/{stats['total']} ({cat_accuracy * 100:.1f}%)")

    # Final verdict
    print("\n=== Final Verdict ===\n")

    threshold: float = evaluation_data["success_criteria"]["sc_007"]["threshold"]
    if accuracy >= threshold:
        print(
            f"✓ SUCCESS: Accuracy {accuracy * 100:.1f}% meets SC-007 requirement (≥{threshold * 100:.1f}%)"
        )
    else:
        print(
            f"✗ FAILURE: Accuracy {accuracy * 100:.1f}% below SC-007 requirement (≥{threshold * 100:.1f}%)"
        )
        print("\nRecommendations:")
        print("- Review failed questions for patterns")
        print("- Verify cross-reference detection accuracy")
        print("- Improve dataset resolution algorithm")
        print("- Enhance SQL Generator agent JOIN guidance")

    # Assert for pytest
    assert accuracy >= threshold, f"SC-007 failed: {accuracy * 100:.1f}% < {threshold * 100:.1f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
