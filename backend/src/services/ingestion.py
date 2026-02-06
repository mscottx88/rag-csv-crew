"""CSV ingestion service for automatic schema detection and bulk data loading.

Implements FR-013, FR-014, FR-015, FR-022:
- Automatic CSV format detection (delimiter, encoding, quote character)
- Schema inference with type detection (INTEGER, FLOAT, BOOLEAN, DATE, TEXT)
- Dynamic table creation with metadata columns
- Bulk ingestion using PostgreSQL COPY protocol
- Filename conflict detection and resolution

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import csv
from datetime import datetime
from io import BytesIO, StringIO
import re
from typing import Any
import unicodedata
import uuid

import chardet
from psycopg import Connection, sql
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from src.services.vector_search import VectorSearchService


def detect_csv_format(csv_file: BytesIO) -> dict[str, Any]:
    """Auto-detect CSV file format parameters.

    Detects delimiter, encoding, quote character, and header presence.

    Args:
        csv_file: CSV file as BytesIO object

    Returns:
        Dictionary with format information:
        - delimiter: Detected delimiter character (',', ';', '|', '\\t')
        - encoding: Detected encoding ('utf-8', 'latin-1', 'windows-1252', 'utf-16')
        - quotechar: Quote character ('"' or "'")
        - has_header: Boolean indicating if first row is header (optional)

    Per FR-013: Automatic format detection for CSV files
    """
    # Read sample for detection (first 8KB)
    csv_file.seek(0)
    sample_bytes: bytes = csv_file.read(8192)
    csv_file.seek(0)

    # Detect encoding
    encoding_result: dict[str, Any] = chardet.detect(sample_bytes)  # type: ignore[assignment]
    detected_encoding: str = encoding_result.get("encoding", "utf-8") or "utf-8"

    # Normalize encoding names
    encoding_lower: str = detected_encoding.lower()
    if encoding_lower in {"utf-8", "utf8", "utf-8-sig"}:
        encoding: str = "utf-8"
    elif encoding_lower in {"iso-8859-1", "latin-1", "latin1", "iso88591"}:
        encoding = "latin-1"
    elif encoding_lower in {"windows-1252", "windows1252", "cp1252"}:
        encoding = "windows-1252"
    elif encoding_lower in {"utf-16", "utf16", "utf-16-le", "utf-16-be"}:
        encoding = "utf-16"
    else:
        # Default to UTF-8 for unknown encodings
        encoding = "utf-8"

    # Decode sample with detected encoding
    try:
        sample_text: str = sample_bytes.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        # Fallback to UTF-8 if detected encoding fails
        sample_text = sample_bytes.decode("utf-8", errors="ignore")
        encoding = "utf-8"

    # Strip UTF-8 BOM if present
    if sample_text.startswith("\ufeff"):
        sample_text = sample_text[1:]

    # Use csv.Sniffer to detect delimiter and quote character
    try:
        sniffer: csv.Sniffer = csv.Sniffer()
        dialect: Any = sniffer.sniff(sample_text, delimiters=",;\t|")
        delimiter: str = dialect.delimiter
        quotechar: str = dialect.quotechar or '"'

        # Check if file has header (heuristic-based)
        has_header: bool = sniffer.has_header(sample_text)
    except (csv.Error, Exception):  # pylint: disable=broad-exception-caught  # pylint: disable=overlapping-except
        # TODO(pylint-refactor): Catch specific exceptions (csv.Error is already specific)
        # Fallback to comma delimiter if sniffer fails
        delimiter = ","
        quotechar = '"'
        has_header = True

    format_info: dict[str, Any] = {
        "delimiter": delimiter,
        "encoding": encoding,
        "quotechar": quotechar,
        "has_header": has_header,
    }

    return format_info


def detect_csv_schema(csv_file: StringIO, sample_size: int = 1000) -> dict[str, Any]:
    """Auto-detect CSV schema by sampling rows and inferring column types.

    Args:
        csv_file: CSV file as StringIO object
        sample_size: Maximum number of rows to sample for type inference

    Returns:
        Dictionary with schema information:
        - columns: List of column definitions with:
          - name: Column name from header
          - type: Inferred SQL type (INTEGER, FLOAT, BOOLEAN, DATE, TIMESTAMP, TEXT)
          - nullable: Boolean indicating if column has NULL values

    Per FR-013: Automatic schema detection and type inference
    """
    csv_file.seek(0)
    reader: csv.DictReader[str] = csv.DictReader(csv_file)

    # Get column names from header
    fieldnames: list[str] = list(reader.fieldnames or [])

    if not fieldnames:
        # Empty file or no header
        return {"columns": []}

    # Initialize column metadata
    column_stats: dict[str, dict[str, Any]] = {}
    for col_name in fieldnames:
        column_stats[col_name] = {
            "name": col_name,
            "type": "TEXT",  # Default to TEXT
            "nullable": False,
            "types_seen": set(),
            "null_count": 0,
            "total_count": 0,
        }

    # Sample rows for type inference
    row_count: int = 0
    for row in reader:
        row_count += 1
        if row_count > sample_size:
            break

        for col_name in fieldnames:
            value: str | None = row.get(col_name, "").strip()

            column_stats[col_name]["total_count"] += 1

            if not value:
                # Empty value → nullable
                column_stats[col_name]["nullable"] = True
                column_stats[col_name]["null_count"] += 1
                continue

            # Infer type from value
            inferred_type: str = _infer_value_type(value)
            column_stats[col_name]["types_seen"].add(inferred_type)

    # Determine final column types based on sampled values
    columns: list[dict[str, Any]] = []
    for col_name in fieldnames:
        stats: dict[str, Any] = column_stats[col_name]
        types_seen: set[str] = stats["types_seen"]

        # Determine most specific type that fits all values
        final_type: str = _resolve_column_type(types_seen)

        columns.append(
            {
                "name": col_name,
                "type": final_type,
                "nullable": stats["nullable"],
            }
        )

    return {"columns": columns}


# pylint: disable=too-complex  # TODO(T225): Refactor type inference logic
def _infer_value_type(value: str) -> str:
    """Infer SQL type from a single value string.

    Args:
        value: String value from CSV

    Returns:
        Inferred type: 'INTEGER', 'FLOAT', 'BOOLEAN', 'DATE', 'TIMESTAMP', 'TEXT'
    """
    # Try INTEGER
    try:
        int(value)
        return "INTEGER"
    except ValueError:
        pass

    # Try FLOAT
    try:
        float(value)
        return "FLOAT"
    except ValueError:
        pass

    # Try BOOLEAN
    value_lower: str = value.lower()
    if value_lower in ["true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"]:
        return "BOOLEAN"

    # Try DATE/TIMESTAMP (ISO 8601)
    if len(value) >= 8 and ("-" in value or "/" in value):
        # Check for date patterns: YYYY-MM-DD, MM/DD/YYYY, etc.
        try:
            # Try common date formats
            from dateutil import parser  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

            parsed: datetime = parser.parse(value)
            if parsed:
                # Check if it includes time component
                if ":" in value or "T" in value:
                    return "TIMESTAMP"
                return "DATE"
        except (ValueError, ImportError):
            pass

    # Default to TEXT
    return "TEXT"


def _resolve_column_type(types_seen: set[str]) -> str:
    """Resolve final column type from set of observed types.

    Uses type hierarchy: INTEGER < FLOAT < TEXT
    BOOLEAN and DATE are specific types that convert to TEXT if mixed

    Args:
        types_seen: Set of types observed in column samples

    Returns:
        Final SQL type for column
    """
    if not types_seen:
        return "TEXT"

    if len(types_seen) == 1:
        return next(iter(types_seen))

    # Mixed types - resolve to least restrictive compatible type
    if "TEXT" in types_seen:
        return "TEXT"

    if "FLOAT" in types_seen:
        # INTEGER can be cast to FLOAT
        return "FLOAT"

    if "INTEGER" in types_seen and "FLOAT" in types_seen:
        return "FLOAT"

    # If mix of BOOLEAN, DATE, TIMESTAMP with numbers → TEXT
    return "TEXT"


def create_dataset_table(  # pylint: disable=too-many-locals
    # TODO(pylint-refactor): Extract SQL generation and index creation into helper methods
    conn: Connection[tuple[str, ...]],
    username: str,
    filename: str,
    schema: dict[str, Any],
) -> str:
    """Create dynamic dataset table with metadata columns.

    Creates table: {username}_schema.{filename}_data
    Includes metadata columns: _row_id, _dataset_id, _ingested_at, _fulltext
    Plus dynamic columns from CSV schema.

    Args:
        conn: Active PostgreSQL connection
        username: User's username for schema isolation
        filename: Sanitized filename (lowercase, alphanumeric + underscore)
        schema: Schema dict with 'columns' list from detect_csv_schema()

    Returns:
        Full table name: {filename}_data

    Raises:
        ValueError: If schema is invalid or filename is invalid

    Per FR-014: Dynamic table creation per data-model.md
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty")

    # Sanitize filename for table name
    table_name: str = _sanitize_table_name(filename)
    schema_name: str = f"{username}_schema"

    # Extract columns from schema
    columns: list[dict[str, Any]] = schema.get("columns", [])
    if not columns:
        raise ValueError("Schema must have at least one column")

    # Build CREATE TABLE statement using psycopg.sql for SQL injection protection
    column_defs: list[sql.SQL] = [
        sql.SQL("_row_id BIGSERIAL PRIMARY KEY"),
        sql.SQL("_dataset_id UUID NOT NULL"),
        sql.SQL("_ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"),
    ]

    # Add dynamic columns from CSV
    for col in columns:
        col_name: str = col["name"]
        col_type: str = col["type"]
        col_nullable: bool = col.get("nullable", True)

        # Sanitize column name
        safe_col_name: str = _sanitize_column_name(col_name)

        # Map inferred type to PostgreSQL type
        pg_type: str = _map_to_postgres_type(col_type)

        # Build column definition using Identifier for column name
        nullable_clause: str = "" if col_nullable else " NOT NULL"
        column_def: sql.SQL = sql.SQL("{col_name} {col_type}{nullable}").format(
            col_name=sql.Identifier(safe_col_name),
            col_type=sql.SQL(pg_type),
            nullable=sql.SQL(nullable_clause),
        )
        column_defs.append(column_def)

    # Add fulltext column at end
    column_defs.append(sql.SQL("_fulltext TSVECTOR"))

    # Create table using Identifier for schema and table names
    create_table_sql: sql.Composed = sql.SQL(
        "CREATE TABLE IF NOT EXISTS {schema}.{table} ({columns})"
    ).format(
        schema=sql.Identifier(schema_name),
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(column_defs),
    )

    with conn.cursor() as cur:
        cur.execute(create_table_sql)

        # Create fulltext index using Identifier
        fulltext_index_sql: sql.Composed = sql.SQL(
            "CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table} USING GIN (_fulltext)"
        ).format(
            index_name=sql.Identifier(f"{table_name}_fulltext_idx"),
            schema=sql.Identifier(schema_name),
            table=sql.Identifier(table_name),
        )
        cur.execute(fulltext_index_sql)

        # Create dataset_id index using Identifier
        dataset_id_index_sql: sql.Composed = sql.SQL(
            "CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table} (_dataset_id)"
        ).format(
            index_name=sql.Identifier(f"{table_name}_dataset_id_idx"),
            schema=sql.Identifier(schema_name),
            table=sql.Identifier(table_name),
        )
        cur.execute(dataset_id_index_sql)

    conn.commit()

    return table_name


def _sanitize_table_name(filename: str) -> str:
    """Sanitize filename for use as table name with comprehensive security checks.

    Handles special characters, Unicode, SQL keywords, length limits, and empty inputs.
    Always uses PostgreSQL Identifier for SQL injection protection.

    Args:
        filename: Original filename (may include .csv extension, spaces, Unicode, etc.)

    Returns:
        Sanitized table name: lowercase, alphanumeric + underscore, ends with _data

    Raises:
        ValueError: If filename is empty or results in empty sanitized name

    Examples:
        >>> _sanitize_table_name("My Data (2024).csv")
        'my_data_2024_data'
        >>> _sanitize_table_name("select.csv")
        'select_table_data'
        >>> _sanitize_table_name("2024_report.csv")
        't_2024_report_data'
        >>> _sanitize_table_name("données.csv")  # Unicode
        'donnees_data'
    """
    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty")

    # Remove .csv extension if present (case-insensitive)
    base_name: str = filename[:-4] if filename.lower().endswith(".csv") else filename

    # Normalize Unicode (decompose accents, etc.) then convert to ASCII
    normalized: str = unicodedata.normalize("NFKD", base_name)
    ascii_name: str = normalized.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase and replace invalid chars with underscore
    # Valid chars: a-z, 0-9, underscore
    sanitized: str = re.sub(r"[^a-z0-9_]+", "_", ascii_name.lower())

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    if not sanitized:
        raise ValueError(f"Filename '{filename}' results in empty table name after sanitization")

    # Ensure starts with letter (not number or underscore)
    if not sanitized[0].isalpha():
        sanitized = f"t_{sanitized}"

    # Check if base name is a SQL reserved keyword
    if _is_sql_reserved_keyword(sanitized):
        sanitized = f"{sanitized}_table"

    # Enforce PostgreSQL identifier limit (63 chars) - leave room for "_data" suffix
    max_length: int = 58
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")

    return f"{sanitized}_data"


# PostgreSQL reserved keywords that require quoting
# Source: https://www.postgresql.org/docs/current/sql-keywords-appendix.html
_SQL_RESERVED_KEYWORDS: set[str] = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "asymmetric",
    "both", "case", "cast", "check", "collate", "column", "constraint", "create",
    "current_catalog", "current_date", "current_role", "current_time",
    "current_timestamp", "current_user", "default", "deferrable", "desc", "distinct",
    "do", "else", "end", "except", "false", "fetch", "for", "foreign", "from",
    "grant", "group", "having", "in", "initially", "intersect", "into", "lateral",
    "leading", "limit", "localtime", "localtimestamp", "not", "null", "offset",
    "on", "only", "or", "order", "placing", "primary", "references", "returning",
    "select", "session_user", "some", "symmetric", "table", "then", "to", "trailing",
    "true", "union", "unique", "user", "using", "variadic", "when", "where", "window",
    "with",
}


def _is_sql_reserved_keyword(name: str) -> bool:
    """Check if a name is a SQL reserved keyword.

    Args:
        name: Column or table name to check

    Returns:
        True if name is a reserved keyword requiring quoting
    """
    return name.lower() in _SQL_RESERVED_KEYWORDS


def _sanitize_column_name(col_name: str) -> str:
    """Sanitize column name for PostgreSQL with comprehensive security checks.

    Handles special characters, Unicode, SQL keywords, length limits, and empty inputs.
    Always uses PostgreSQL Identifier for SQL injection protection.

    Args:
        col_name: Original column name from CSV (may contain spaces, Unicode, special chars)

    Returns:
        Sanitized column name: lowercase, alphanumeric + underscore,
        with suffix added if it's a reserved keyword

    Raises:
        ValueError: If column name is empty or results in empty sanitized name

    Examples:
        >>> _sanitize_column_name("Product ID")
        'product_id'
        >>> _sanitize_column_name("group")
        'group_col'
        >>> _sanitize_column_name("2024_value")
        '_2024_value'
        >>> _sanitize_column_name("Prénom")  # Unicode
        'prenom'

    Note:
        Reserved keywords get "_col" suffix to avoid SQL syntax errors
        (e.g., "group" → "group_col", "order" → "order_col")
    """
    if not col_name or not col_name.strip():
        raise ValueError("Column name cannot be empty")

    # Normalize Unicode (decompose accents) then convert to ASCII
    normalized: str = unicodedata.normalize("NFKD", col_name)
    ascii_name: str = normalized.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase and replace invalid chars with underscore
    sanitized: str = re.sub(r"[^a-z0-9_]+", "_", ascii_name.lower())

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    if not sanitized:
        raise ValueError(
            f"Column name '{col_name}' results in empty name after sanitization"
        )

    # Ensure starts with letter or underscore (not number)
    if sanitized[0].isdigit():
        sanitized = f"_{sanitized}"

    # Check if it's a reserved keyword and add suffix to avoid conflicts
    if _is_sql_reserved_keyword(sanitized):
        sanitized = f"{sanitized}_col"

    # Enforce PostgreSQL identifier limit (63 characters)
    if len(sanitized) > 63:
        sanitized = sanitized[:63].rstrip("_")

    return sanitized


def _map_to_postgres_type(inferred_type: str) -> str:
    """Map inferred CSV type to PostgreSQL type.

    Args:
        inferred_type: Type from detect_csv_schema ('INTEGER', 'FLOAT', etc.)

    Returns:
        PostgreSQL column type
    """
    type_mapping: dict[str, str] = {
        "INTEGER": "BIGINT",
        "FLOAT": "DOUBLE PRECISION",
        "BOOLEAN": "BOOLEAN",
        "DATE": "DATE",
        "TIMESTAMP": "TIMESTAMP WITH TIME ZONE",
        "TEXT": "TEXT",
    }

    return type_mapping.get(inferred_type, "TEXT")


def ingest_csv_data(  # pylint: disable=too-many-locals
    # TODO(pylint-refactor): Extract CSV processing logic into smaller helper functions
    conn: Connection[tuple[str, ...]],
    username: str,
    table_name: str,
    csv_file: BytesIO,
    dataset_id: str,
) -> int:
    """Bulk ingest CSV data using PostgreSQL COPY protocol.

    Args:
        conn: Active PostgreSQL connection
        username: User's username for schema isolation
        table_name: Target table name (e.g., "products_data")
        csv_file: CSV file as BytesIO object
        dataset_id: UUID string for _dataset_id column

    Returns:
        Number of rows ingested

    Raises:
        ValueError: If parameters are invalid
        psycopg.Error: If COPY operation fails

    Per FR-015: Bulk ingestion using PostgreSQL COPY for performance
    """
    if not username or not table_name or not dataset_id:
        raise ValueError("Username, table_name, and dataset_id are required")

    # Validate UUID format
    try:
        uuid.UUID(dataset_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID format for dataset_id: {dataset_id}") from e

    schema_name: str = f"{username}_schema"

    # Read CSV to determine columns (excluding metadata columns)
    csv_file.seek(0)
    csv_data: bytes = csv_file.read()
    csv_file.seek(0)

    # Detect format and decode
    format_info: dict[str, Any] = detect_csv_format(csv_file)
    encoding: str = format_info["encoding"]

    try:
        csv_text: str = csv_data.decode(encoding)
    except UnicodeDecodeError:
        csv_text = csv_data.decode("utf-8", errors="ignore")

    # Strip BOM if present
    if csv_text.startswith("\ufeff"):
        csv_text = csv_text[1:]

    # Parse CSV to get column names
    csv_stringio: StringIO = StringIO(csv_text)
    reader: csv.DictReader[str] = csv.DictReader(csv_stringio, delimiter=format_info["delimiter"])
    fieldnames: list[str] = list(reader.fieldnames or [])

    if not fieldnames:
        raise ValueError("CSV file has no columns")

    # Sanitize column names to match table
    sanitized_columns: list[str] = [_sanitize_column_name(col) for col in fieldnames]

    # Build COPY statement with column list using Identifier for SQL injection protection
    column_identifiers: list[sql.Identifier] = [sql.Identifier(col) for col in sanitized_columns]
    copy_sql: sql.Composed = sql.SQL(
        "COPY {schema}.{table} (_dataset_id, {columns}) FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER {delimiter})"
    ).format(
        schema=sql.Identifier(schema_name),
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(column_identifiers),
        delimiter=sql.Literal(format_info["delimiter"]),
    )

    # Prepare CSV with dataset_id column prepended
    csv_stringio.seek(0)
    csv_with_dataset_id: StringIO = _prepend_dataset_id_column(
        csv_stringio, dataset_id, format_info["delimiter"]
    )

    # Execute COPY
    with conn.cursor() as cur, cur.copy(copy_sql) as copy:
        csv_with_dataset_id.seek(0)
        copy.write(csv_with_dataset_id.read())

    conn.commit()

    # Count rows ingested using Identifier for SQL injection protection
    count_sql: sql.Composed = sql.SQL(
        "SELECT COUNT(*) FROM {schema}.{table} WHERE _dataset_id = %s"
    ).format(
        schema=sql.Identifier(schema_name),
        table=sql.Identifier(table_name),
    )

    with conn.cursor() as cur:
        cur.execute(count_sql, (dataset_id,))
        result: tuple[Any, ...] | None = cur.fetchone()
        row_count: int = result[0] if result else 0

    return row_count


def _prepend_dataset_id_column(csv_file: StringIO, dataset_id: str, delimiter: str) -> StringIO:
    """Prepend _dataset_id column to CSV for COPY ingestion.

    Args:
        csv_file: Original CSV StringIO
        dataset_id: UUID to prepend to each row
        delimiter: CSV delimiter character

    Returns:
        New StringIO with _dataset_id column prepended
    """
    csv_file.seek(0)
    lines: list[str] = csv_file.readlines()

    if not lines:
        return StringIO("")

    # Prepend _dataset_id to header
    modified_lines: list[str] = [f"_dataset_id{delimiter}{lines[0]}"]

    # Prepend dataset_id value to each data row
    for line in lines[1:]:
        modified_lines.append(f"{dataset_id}{delimiter}{line}")

    return StringIO("".join(modified_lines))


def store_dataset_metadata(
    conn: Connection[tuple[str, ...]],
    username: str,
    metadata: dict[str, Any],
) -> str:
    """Store dataset metadata in {username}_schema.datasets table.

    Args:
        conn: Active PostgreSQL connection
        username: User's username for schema isolation
        metadata: Dictionary with:
          - filename: Sanitized filename (e.g., "products")
          - original_filename: Original filename with extension (e.g., "products.csv")
          - table_name: Table name (e.g., "products_data")
          - row_count: Number of rows ingested
          - column_count: Number of columns
          - file_size_bytes: File size in bytes
          - schema_json: Schema dict from detect_csv_schema()

    Returns:
        Dataset UUID (as string)

    Raises:
        ValueError: If required metadata fields are missing

    Per FR-015: Dataset metadata tracking per data-model.md
    """
    if not username:
        raise ValueError("Username is required")

    required_fields: list[str] = [
        "filename",
        "original_filename",
        "table_name",
        "row_count",
        "column_count",
        "file_size_bytes",
        "schema_json",
    ]

    for field in required_fields:
        if field not in metadata:
            raise ValueError(f"Missing required metadata field: {field}")

    schema_name: str = f"{username}_schema"

    # Use Identifier for SQL injection protection
    insert_sql: sql.Composed = sql.SQL(
        """
        INSERT INTO {schema}.datasets (
            filename, original_filename, table_name, row_count,
            column_count, file_size_bytes, schema_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
    ).format(schema=sql.Identifier(schema_name))

    with conn.cursor() as cur:
        cur.execute(
            insert_sql,
            (
                metadata["filename"],
                metadata["original_filename"],
                metadata["table_name"],
                metadata["row_count"],
                metadata["column_count"],
                metadata["file_size_bytes"],
                Jsonb(metadata["schema_json"]),  # Wrap dict in Jsonb for psycopg3
            ),
        )
        result: tuple[str, ...] | None = cur.fetchone()
        if result is None:
            raise ValueError("Failed to insert dataset metadata")

        dataset_id: str = str(result[0])

    conn.commit()

    return dataset_id


def check_filename_conflict(
    conn: Connection[tuple[str, ...]],
    username: str,
    filename: str,
) -> dict[str, Any]:
    """Check if filename already exists for user.

    Args:
        conn: Active PostgreSQL connection
        username: User's username for schema isolation
        filename: Filename to check (without .csv extension)

    Returns:
        Dictionary with conflict information:
        - conflict: Boolean indicating if conflict exists
        - suggested_filename: Suggested filename with timestamp suffix (if conflict)

    Per FR-022: Filename conflict detection and resolution
    """
    if not username or not filename:
        raise ValueError("Username and filename are required")

    schema_name: str = f"{username}_schema"

    # Use Identifier for SQL injection protection
    check_sql: sql.Composed = sql.SQL(
        "SELECT COUNT(*) FROM {schema}.datasets WHERE filename = %s"
    ).format(schema=sql.Identifier(schema_name))

    with conn.cursor() as cur:
        cur.execute(check_sql, (filename,))
        result: tuple[Any, ...] | None = cur.fetchone()
        count: int = result[0] if result else 0

    if count == 0:
        return {"conflict": False}

    # Generate suggested filename with timestamp
    timestamp: str = datetime.now().strftime("%Y%m%d%H%M%S")
    suggested_filename: str = f"{filename}_{timestamp}"

    return {
        "conflict": True,
        "suggested_filename": suggested_filename,
    }


def store_column_mappings(
    pool: ConnectionPool, username: str, dataset_id: str, columns: list[dict[str, Any]]
) -> None:
    """Store column mappings WITHOUT embeddings (required for all datasets).

    Creates column_mappings entries for schema metadata. This function MUST succeed
    for dataset functionality. Embeddings are added later as optional enhancement.

    Args:
        pool: Database connection pool
        username: Username for schema isolation
        dataset_id: Dataset UUID
        columns: List of column dictionaries with name, type, description

    Raises:
        RuntimeError: If column mapping storage fails

    Per FR-015: Column metadata tracking
    """
    schema_name: str = f"{username}_schema"

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Use Identifier for SQL injection protection in SET search_path
                set_path_sql: sql.Composed = sql.SQL("SET search_path TO {schema}, public").format(
                    schema=sql.Identifier(schema_name)
                )
                cur.execute(set_path_sql)

                # Insert column mappings without embeddings
                insert_sql: str = """
                    INSERT INTO column_mappings (dataset_id, column_name, inferred_type, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (dataset_id, column_name) DO NOTHING
                """

                for col in columns:
                    col_name_original: str = col.get("name", col.get("column_name", ""))
                    inferred_type: str = col.get("type", col.get("inferred_type", "TEXT"))
                    col_description: str = col.get("description", "")

                    # Sanitize column name to match actual table column
                    # (tables use lowercase sanitized names)
                    col_name_sanitized: str = _sanitize_column_name(col_name_original)

                    cur.execute(
                        insert_sql,
                        (dataset_id, col_name_sanitized, inferred_type, col_description),
                    )

            conn.commit()

    except Exception as e:
        raise RuntimeError(
            f"Failed to store column mappings for dataset {dataset_id}: {e}"
        ) from e


def generate_column_embeddings(
    pool: ConnectionPool, username: str, dataset_id: str, columns: list[dict[str, Any]]
) -> None:
    """Generate and UPDATE embeddings for existing column mappings (optional).

    Creates vector embeddings for each column using OpenAI text-embedding-3-small
    and UPDATES existing column_mappings entries. Column mappings must already exist
    (created by store_column_mappings). If this function fails, basic dataset
    functionality still works - only semantic search is affected.

    Args:
        pool: Database connection pool
        username: Username for schema isolation
        dataset_id: Dataset UUID
        columns: List of column dictionaries with name, data_type, description

    Raises:
        RuntimeError: If embedding generation or database update fails

    Per FR-038: Semantic search using vector embeddings
    """
    vector_service: VectorSearchService = VectorSearchService(pool=pool)
    schema_name: str = f"{username}_schema"

    # Generate embeddings for each column
    embeddings: list[list[float]] = []
    column_names: list[str] = []

    for col in columns:
        column_name: str = col.get("name", col.get("column_name", ""))
        description: str = col.get("description", "")

        # Create embedding text: "column_name description"
        embedding_text: str = f"{column_name} {description}".strip()

        # Generate embedding for this column
        try:
            embedding: list[float] = vector_service.generate_embedding(embedding_text)
            embeddings.append(embedding)
            column_names.append(column_name)
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding for column {column_name}: {e}") from e

    # Update existing column_mappings with embeddings
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Use Identifier for SQL injection protection in SET search_path
                set_path_sql: sql.Composed = sql.SQL("SET search_path TO {schema}, public").format(
                    schema=sql.Identifier(schema_name)
                )
                cur.execute(set_path_sql)

                # UPDATE existing column_mappings with embeddings
                update_sql: str = """
                    UPDATE column_mappings
                    SET embedding = %s
                    WHERE dataset_id = %s AND column_name = %s
                """

                # Update each column with its embedding
                for col in columns:
                    col_name: str = col.get("name", col.get("column_name", ""))
                    if col_name in column_names:
                        # Find the embedding for this column
                        embedding_idx: int = column_names.index(col_name)
                        col_embedding: list[float] = embeddings[embedding_idx]

                        cur.execute(
                            update_sql,
                            (col_embedding, dataset_id, col_name),
                        )

            conn.commit()

    except Exception as e:
        raise RuntimeError(f"Failed to update embeddings for dataset {dataset_id}: {e}") from e


class IngestionService:
    """Service class for CSV ingestion with embedding generation.

    Provides object-oriented interface to ingestion functionality,
    primarily for testing purposes.
    """

    def __init__(self, pool: ConnectionPool) -> None:
        """Initialize ingestion service.

        Args:
            pool: Database connection pool
        """
        self.pool: ConnectionPool = pool

    def generate_column_embeddings(
        self, username: str, dataset_id: str, columns: list[dict[str, Any]]
    ) -> None:
        """Generate and store embeddings for column mappings.

        Delegates to the module-level generate_column_embeddings function.

        Args:
            username: Username for schema isolation
            dataset_id: Dataset UUID
            columns: List of column dictionaries with name, data_type, description

        Raises:
            RuntimeError: If embedding generation or database update fails
        """
        generate_column_embeddings(
            pool=self.pool, username=username, dataset_id=dataset_id, columns=columns
        )

    def detect_and_store_cross_references(
        self, username: str, new_dataset_id: str
    ) -> int:
        """Detect and store cross-references between new dataset and existing datasets.

        Args:
            username: Username for schema isolation
            new_dataset_id: ID of newly uploaded dataset

        Returns:
            Number of cross-references detected and stored

        Raises:
            RuntimeError: If cross-reference detection or storage fails
        """
        from src.services.cross_reference import (  # pylint: disable=import-outside-toplevel
            CrossReferenceService,
        )

        try:
            cross_ref_service: CrossReferenceService = CrossReferenceService(self.pool)
            user_schema: str = f"{username}_schema"
            total_refs: int = 0

            with self.pool.connection() as conn, conn.cursor() as cur:
                # Set search path using Identifier for SQL injection protection
                set_path_sql: sql.Composed = sql.SQL("SET search_path TO {schema}, public").format(
                    schema=sql.Identifier(user_schema)
                )
                cur.execute(set_path_sql)

                # Get all existing datasets for this user
                cur.execute(
                    "SELECT id FROM datasets WHERE id != %s",
                    (new_dataset_id,),
                )
                existing_datasets: list[tuple[str, ...]] = cur.fetchall()

                # Detect cross-references with each existing dataset
                for (existing_dataset_id,) in existing_datasets:
                    # Check both directions
                    refs_forward: list[dict[str, Any]] = (
                        cross_ref_service.detect_cross_references(
                            username=username,
                            source_dataset_id=new_dataset_id,
                            target_dataset_id=existing_dataset_id,
                            min_confidence=0.3,
                        )
                    )

                    refs_backward: list[dict[str, Any]] = (
                        cross_ref_service.detect_cross_references(
                            username=username,
                            source_dataset_id=existing_dataset_id,
                            target_dataset_id=new_dataset_id,
                            min_confidence=0.3,
                        )
                    )

                    # Store detected references
                    for ref in refs_forward + refs_backward:
                        self._store_cross_reference(conn, user_schema, ref)
                        total_refs += 1

                conn.commit()

            return total_refs

        except Exception as e:
            raise RuntimeError(
                f"Failed to detect cross-references: {e!s}"
            ) from e

    def _store_cross_reference(
        self, conn: Any, user_schema: str, ref: dict[str, Any]
    ) -> None:
        """Store a single cross-reference in the database.

        Args:
            conn: Database connection
            user_schema: User schema name
            ref: Cross-reference dictionary with keys:
                source_dataset_id, source_column, target_dataset_id,
                target_column, relationship_type, confidence_score

        Raises:
            Exception: If database insert fails
        """
        with conn.cursor() as cur:
            # Use Identifier for SQL injection protection in SET search_path
            set_path_sql: sql.Composed = sql.SQL("SET search_path TO {schema}, public").format(
                schema=sql.Identifier(user_schema)
            )
            cur.execute(set_path_sql)

            # Insert cross-reference (UPSERT to handle duplicates)
            cur.execute(
                """
                INSERT INTO cross_references (
                    source_dataset_id,
                    source_column,
                    target_dataset_id,
                    target_column,
                    relationship_type,
                    confidence_score
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_dataset_id, source_column, target_dataset_id, target_column)
                DO UPDATE SET
                    relationship_type = EXCLUDED.relationship_type,
                    confidence_score = EXCLUDED.confidence_score
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
