"""CrewAI tools for schema inspection.

Provides tools that agents can use to inspect database schemas,
retrieve column information, and discover relationships between datasets.

Uses global state injection pattern for service instance.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from typing import Any
from uuid import UUID

from crewai.tools import tool

from src.services.schema_inspector import SchemaInspectorService

# Global state for schema inspector context
_schema_inspector_service: SchemaInspectorService | None = None
_schema_inspector_username: str | None = None


def set_schema_inspector_context(service: SchemaInspectorService, username: str) -> None:
    """Set global schema inspector context for tool access.

    Args:
        service: SchemaInspectorService instance
        username: Current username for schema isolation

    Note:
        This must be called before using schema inspector tools.
        Uses module-level globals for CrewAI tool compatibility.
    """
    global _schema_inspector_service, _schema_inspector_username  # noqa: PLW0603
    _schema_inspector_service = service
    _schema_inspector_username = username


@tool("list_datasets")  # type: ignore[misc]
def list_datasets_tool() -> str:
    """List all available datasets with metadata.

    Returns:
        JSON string with list of datasets including:
        - dataset_id: Unique identifier
        - filename: Original CSV filename
        - table_name: PostgreSQL table name
        - row_count: Number of rows
        - column_count: Number of columns

    Use this tool to:
    - Discover what datasets are available to query
    - Get table names for SQL generation
    - Understand dataset sizes
    """
    if _schema_inspector_service is None or _schema_inspector_username is None:
        return "Error: Schema inspector context not set"

    try:
        datasets: list[dict[str, Any]] = _schema_inspector_service.get_available_datasets(
            username=_schema_inspector_username
        )

        # Format as readable text for agent
        result: str = f"Available Datasets ({len(datasets)}):\n\n"

        for dataset in datasets:
            result += f"Dataset: {dataset['filename']}\n"
            result += f"  Table Name: {dataset['table_name']}\n"
            result += f"  Rows: {dataset['row_count']:,}\n"
            result += f"  Columns: {dataset['column_count']}\n"
            result += f"  ID: {dataset['id']}\n\n"

        return result

    except Exception as e:
        return f"Error listing datasets: {e!s}"


@tool("inspect_schema")  # type: ignore[misc]
def inspect_schema_tool(dataset_id: str) -> str:
    """Inspect the complete schema of a specific dataset.

    Args:
        dataset_id: UUID of the dataset to inspect

    Returns:
        JSON string with complete schema including:
        - table_name: PostgreSQL table name
        - columns: List of column details (name, type, description)

    Use this tool to:
    - Get exact table and column names for SQL queries
    - Understand column types and descriptions
    - Discover available columns before generating SQL
    """
    if _schema_inspector_service is None or _schema_inspector_username is None:
        return "Error: Schema inspector context not set"

    try:
        dataset_uuid: UUID = UUID(dataset_id)
        schema: dict[str, Any] = _schema_inspector_service.get_dataset_schema(
            username=_schema_inspector_username, dataset_id=dataset_uuid
        )

        # Format as readable text for agent
        result: str = f"Schema for {schema['filename']}:\n\n"
        result += f"Table Name: {schema['table_name']}\n"
        result += f"Row Count: {schema['row_count']:,}\n"
        result += f"Column Count: {schema['column_count']}\n\n"
        result += "Columns:\n"

        for column in schema["columns"]:
            result += f"  - {column['name']} ({column['type']})"
            if column["description"]:
                result += f": {column['description']}"
            result += "\n"

        return result

    except ValueError as e:
        return f"Error: {e!s}"
    except Exception as e:
        return f"Error inspecting schema: {e!s}"


@tool("get_sample_data")  # type: ignore[misc]
def get_sample_data_tool(dataset_id: str, limit: int = 3) -> str:
    """Get sample rows from a dataset to understand data structure.

    Args:
        dataset_id: UUID of the dataset
        limit: Number of sample rows (default: 3, max: 10)

    Returns:
        Sample rows formatted as text

    Use this tool to:
    - See example data values for context
    - Understand data formats and patterns
    - Generate appropriate WHERE clauses
    """
    if _schema_inspector_service is None or _schema_inspector_username is None:
        return "Error: Schema inspector context not set"

    # Limit to max 10 rows
    limited: int = min(limit, 10)

    try:
        dataset_uuid: UUID = UUID(dataset_id)
        sample: dict[str, Any] = _schema_inspector_service.get_sample_data(
            username=_schema_inspector_username, dataset_id=dataset_uuid, limit=limited
        )

        # Format as readable text for agent
        result: str = f"Sample Data from {sample['table_name']} ({limited} rows):\n\n"
        result += "Columns: " + ", ".join(sample["columns"]) + "\n\n"

        for i, row in enumerate(sample["rows"], 1):
            result += f"Row {i}:\n"
            for col_name, col_value in zip(sample["columns"], row, strict=False):
                # Truncate long values
                value_str: str = str(col_value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                result += f"  {col_name}: {value_str}\n"
            result += "\n"

        return result

    except ValueError as e:
        return f"Error: {e!s}"
    except Exception as e:
        return f"Error getting sample data: {e!s}"
