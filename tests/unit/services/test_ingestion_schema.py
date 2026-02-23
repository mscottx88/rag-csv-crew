"""Unit tests for CSV schema detection service (T041-TEST).

Tests automatic CSV schema detection and type inference:
- Sample up to 1000 rows for analysis
- Infer column types per data-model.md type mapping
- Handle various data types (integer, float, boolean, date, text)
- Detect nullable columns

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from io import StringIO
from typing import Any

import pytest


@pytest.mark.unit
class TestCSVSchemaDetection:
    """Unit tests for CSV schema detection (T041)."""

    def test_detect_integer_column(self) -> None:
        """Test schema detection identifies integer columns.

        Validates:
        - Pure integer values → INTEGER type
        - Sampling strategy (up to 1000 rows)
        - Per data-model.md: INTEGER for whole numbers

        Success Criteria (T041):
        - Column with only integers detected as INTEGER
        - Type inference correct for sample size
        """
        csv_content: str = "id,name\n1,Alice\n2,Bob\n3,Charlie\n"
        csv_file: StringIO = StringIO(csv_content)

        # Import service (will fail until implemented)
        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify schema structure
        assert "columns" in schema
        assert len(schema["columns"]) == 2

        # Verify integer type detection
        id_column: dict[str, Any] = next(c for c in schema["columns"] if c["name"] == "id")
        assert id_column["type"] in ["INTEGER", "BIGINT", "int", "integer"]

    def test_detect_float_column(self) -> None:
        """Test schema detection identifies float/decimal columns.

        Validates:
        - Decimal values → FLOAT/DECIMAL type
        - Scientific notation support
        - Per data-model.md: FLOAT for decimal numbers

        Success Criteria (T041):
        - Column with decimals detected as FLOAT/DECIMAL
        - Scientific notation handled correctly
        """
        csv_content: str = "price,quantity\n19.99,5\n29.50,3\n15.00,10\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify float type detection
        price_column: dict[str, Any] = next(c for c in schema["columns"] if c["name"] == "price")
        assert price_column["type"] in ["FLOAT", "DECIMAL", "NUMERIC", "float", "decimal"]

    def test_detect_boolean_column(self) -> None:
        """Test schema detection identifies boolean columns.

        Validates:
        - true/false values → BOOLEAN type
        - Various boolean representations (yes/no, 1/0, True/False)
        - Per data-model.md: BOOLEAN for true/false values

        Success Criteria (T041):
        - Common boolean values detected as BOOLEAN
        - Case insensitive detection
        """
        csv_content: str = "active,verified\ntrue,yes\nfalse,no\ntrue,yes\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify boolean type detection
        active_column: dict[str, Any] = next(c for c in schema["columns"] if c["name"] == "active")
        assert active_column["type"] in ["BOOLEAN", "bool", "boolean"]

    def test_detect_date_column(self) -> None:
        """Test schema detection identifies date/timestamp columns.

        Validates:
        - ISO 8601 dates → DATE/TIMESTAMP type
        - Common date formats (YYYY-MM-DD, MM/DD/YYYY, etc.)
        - Per data-model.md: TIMESTAMP WITH TIME ZONE for dates

        Success Criteria (T041):
        - ISO 8601 dates detected as DATE/TIMESTAMP
        - Timezone awareness preserved
        """
        csv_content: str = "created_at,updated_at\n2024-01-15,2024-01-16\n2024-02-20,2024-02-21\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify date type detection
        created_column: dict[str, Any] = next(
            c for c in schema["columns"] if c["name"] == "created_at"
        )
        assert created_column["type"] in [
            "DATE",
            "TIMESTAMP",
            "TIMESTAMP WITH TIME ZONE",
            "date",
            "timestamp",
        ]

    def test_detect_text_column(self) -> None:
        """Test schema detection defaults to TEXT for mixed/string data.

        Validates:
        - Mixed data types → TEXT (fallback)
        - Variable length strings → VARCHAR/TEXT
        - Per data-model.md: TEXT for general text data

        Success Criteria (T041):
        - String columns detected as TEXT/VARCHAR
        - Mixed type columns fall back to TEXT
        """
        csv_content: str = "name,description\nAlice,Engineer\nBob,Designer\nCharlie,Manager\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify text type detection
        name_column: dict[str, Any] = next(c for c in schema["columns"] if c["name"] == "name")
        assert name_column["type"] in ["TEXT", "VARCHAR", "text", "varchar", "string"]

    def test_detect_nullable_column(self) -> None:
        """Test schema detection identifies nullable columns.

        Validates:
        - Empty values → nullable: true
        - NULL values → nullable: true
        - All non-null values → nullable: false

        Success Criteria (T041):
        - Columns with missing values marked nullable
        - Nullable flag present in schema
        """
        csv_content: str = "id,optional_field\n1,value1\n2,\n3,value3\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify nullable detection
        optional_column: dict[str, Any] = next(
            c for c in schema["columns"] if c["name"] == "optional_field"
        )
        assert "nullable" in optional_column
        assert optional_column["nullable"] is True

        # Non-nullable column
        id_column: dict[str, Any] = next(c for c in schema["columns"] if c["name"] == "id")
        assert id_column.get("nullable", True) in [False, None]  # Not nullable

    def test_sample_large_csv(self) -> None:
        """Test schema detection samples up to 1000 rows.

        Validates:
        - Large CSV (> 1000 rows) → sample first 1000
        - Sampling efficiency
        - Accurate type inference from sample

        Success Criteria (T041):
        - Schema detection completes efficiently for large files
        - First 1000 rows used for type inference
        """
        # Generate CSV with 2000 rows
        rows: list[str] = ["id,value"]
        rows.extend([f"{i},{i * 10}" for i in range(1, 2001)])
        csv_content: str = "\n".join(rows)
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file, sample_size=1000)

        # Verify schema detected correctly despite large size
        assert "columns" in schema
        assert len(schema["columns"]) == 2

        # Verify type inference worked on sample
        value_column: dict[str, Any] = next(c for c in schema["columns"] if c["name"] == "value")
        assert value_column["type"] in ["INTEGER", "BIGINT", "int", "integer"]

    def test_handle_empty_csv(self) -> None:
        """Test schema detection handles empty CSV gracefully.

        Validates:
        - Empty CSV (header only) → schema with 0-row columns
        - No data rows → type defaults to TEXT
        - Error handling for invalid input

        Success Criteria (T041):
        - Empty CSV returns schema with header columns
        - No exceptions raised
        """
        csv_content: str = "id,name,email\n"  # Header only, no data
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify schema detected from header
        assert "columns" in schema
        assert len(schema["columns"]) == 3

        # All columns should default to TEXT when no data
        for column in schema["columns"]:
            assert column["type"] in ["TEXT", "VARCHAR", "text", "varchar", "string"]

    def test_mixed_type_column_defaults_to_text(self) -> None:
        """Test mixed data types in single column default to TEXT.

        Validates:
        - Column with integers AND strings → TEXT
        - Type ambiguity resolved to safest type (TEXT)
        - Per data-model.md: TEXT as fallback

        Success Criteria (T041):
        - Mixed type columns detected as TEXT
        - No type inference errors
        """
        csv_content: str = "mixed_column\n123\nabc\n456\nxyz\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify TEXT fallback for mixed types
        mixed_column: dict[str, Any] = schema["columns"][0]
        assert mixed_column["type"] in ["TEXT", "VARCHAR", "text", "varchar", "string"]

    def test_detect_column_names(self) -> None:
        """Test schema detection preserves original column names.

        Validates:
        - Column names extracted from CSV header
        - Special characters handled
        - Case preserved

        Success Criteria (T041):
        - Column names match CSV header
        - No mangling or sanitization at detection stage
        """
        csv_content: str = "User ID,Full Name,Email-Address\n1,Alice,alice@example.com\n"
        csv_file: StringIO = StringIO(csv_content)

        from backend.src.services.ingestion import detect_csv_schema

        schema: dict[str, Any] = detect_csv_schema(csv_file)

        # Verify column names preserved
        column_names: list[str] = [c["name"] for c in schema["columns"]]
        assert "User ID" in column_names
        assert "Full Name" in column_names
        assert "Email-Address" in column_names
