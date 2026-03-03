"""Index manager service for creating and tracking database indexes.

Implements index creation, metadata tracking, and context generation
for the SQL generation task per FR-001 through FR-023.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

from datetime import UTC, datetime
import hashlib
import time
from typing import Any, NamedTuple
from uuid import UUID, uuid4

from psycopg import Connection, sql

from backend.src.models.index_metadata import (
    DataColumnIndexProfile,
    IndexCapability,
    IndexMetadataEntry,
    IndexStatus,
    IndexType,
)
from backend.src.utils.logging import get_structured_logger, log_event

logger = get_structured_logger(__name__)


class IndexCreationError(Exception):
    """Raised when index creation fails during ingestion.

    Contains partial results for diagnostics per FR-012.

    Attributes:
        partial_results: Successfully created index entries before failure
        failed_index: Name of the index that failed to create
    """

    def __init__(
        self,
        message: str,
        partial_results: list[IndexMetadataEntry],
        failed_index: str,
    ) -> None:
        """Initialize IndexCreationError.

        Args:
            message: Human-readable error description
            partial_results: Successfully created index entries before failure
            failed_index: Name of the index that failed to create
        """
        super().__init__(message)
        self.partial_results: list[IndexMetadataEntry] = partial_results
        self.failed_index: str = failed_index


class _IndexParams(NamedTuple):
    """Shared parameters for index creation helpers."""

    conn: Connection[tuple[str, ...]]
    schema_name: str
    table_name: str
    ds_uuid: UUID
    now: datetime
    username: str


_MAX_IDENTIFIER_LENGTH: int = 63
_MAX_INDEX_CONTEXT_CHARS: int = 4000

# SQL template constants (module-level to avoid implicit concat in calls)
_BTREE_CREATE_SQL: str = "CREATE INDEX IF NOT EXISTS {idx_name}" " ON {schema}.{table} ({col})"

_TSVECTOR_ALTER_SQL: str = (
    "ALTER TABLE {schema}.{table}"
    " ADD COLUMN IF NOT EXISTS {ts_col} TSVECTOR"
    " GENERATED ALWAYS AS"
    " (to_tsvector('english', COALESCE({col}, '')))"
    " STORED"
)

_GIN_CREATE_SQL: str = (
    "CREATE INDEX IF NOT EXISTS {idx_name}" " ON {schema}.{table} USING GIN ({ts_col})"
)

_CONTEXT_RULES: list[str] = [
    "RULES:",
    "- ALWAYS use full-text search (@@, ts_rank) instead of "
    + "ILIKE for text searches when available",
    "- Use vector similarity (<=> operator) " + "for semantic/meaning-based queries",
    "- You may combine full-text search and vector " + "similarity in a single query",
    "- B-tree indexes are always available for filtering and sorting",
    "- Columns prefixed with '_ts_' are tsvector columns " + "\u2014 use @@ operator, not ILIKE",
    "- Columns prefixed with '_emb_' are vector columns " + "\u2014 use <=> operator",
]


def generate_index_name(
    table_name: str,
    column_name: str,
    index_type: str,
) -> str:
    """Generate a PostgreSQL index name with 63-character limit handling.

    Pattern: idx_{table}_{column}_{type}
    If the full name exceeds 63 characters, truncates the table+column
    portion and appends an 8-character MD5 hash for uniqueness.

    Truncated pattern: idx_{truncated}_{hash8}_{type}

    Args:
        table_name: Name of the data table
        column_name: Name of the column being indexed
        index_type: Index type suffix (btree, gin, hnsw)

    Returns:
        PostgreSQL-safe index name (max 63 characters)
    """
    full_name: str = f"idx_{table_name}_{column_name}_{index_type}"

    if len(full_name) <= _MAX_IDENTIFIER_LENGTH:
        return full_name

    # Need to truncate: idx_{truncated}_{hash8}_{type}
    # Fixed parts: "idx_" (4) + "_" (1) + hash8 (8) + "_" (1) + type
    hash_input: str = f"{table_name}_{column_name}"
    hash_suffix: str = hashlib.md5(hash_input.encode()).hexdigest()[:8]

    # Calculate available space for the truncated portion
    # Format: idx_{truncated}_{hash8}_{type}
    prefix_len: int = 4  # "idx_"
    separator_len: int = 2  # two underscores around hash
    hash_len: int = 8
    type_len: int = len(index_type)
    overhead: int = prefix_len + separator_len + hash_len + type_len
    available: int = _MAX_IDENTIFIER_LENGTH - overhead

    # Truncate the table+column portion
    truncated: str = f"{table_name}_{column_name}"[:available]

    # Remove trailing underscore if truncation landed on one
    truncated = truncated.rstrip("_")

    return f"idx_{truncated}_{hash_suffix}_{index_type}"


def _is_identifier_column(
    conn: Connection[tuple[str, ...]],
    schema_name: str,
    table_name: str,
    column_name: str,
) -> bool:
    """Check if a TEXT column appears to be an identifier (skip FTS).

    Heuristic per FR-002: cardinality ratio > 0.95 AND avg text length < 50.

    Args:
        conn: Active database connection
        schema_name: User schema name
        table_name: Data table name
        column_name: Column to evaluate

    Returns:
        True if column appears to be an identifier, False otherwise
    """
    with conn.cursor() as cur:
        query: sql.Composed = sql.SQL(
            "SELECT COUNT(DISTINCT {col})::float"
            " / GREATEST(COUNT(*)::float, 1),"
            " AVG(LENGTH({col}))"
            " FROM {schema}.{table}"
            " WHERE {col} IS NOT NULL"
        ).format(
            col=sql.Identifier(column_name),
            schema=sql.Identifier(schema_name),
            table=sql.Identifier(table_name),
        )
        cur.execute(query)
        row: tuple[Any, ...] | None = cur.fetchone()

    if row is None or row[0] is None:
        return False

    cardinality_ratio: float = float(row[0])
    avg_length: float = float(row[1]) if row[1] is not None else 0.0

    return cardinality_ratio > 0.95 and avg_length < 50


def _insert_metadata_entry(
    conn: Connection[tuple[str, ...]],
    schema_name: str,
    entry: IndexMetadataEntry,
) -> None:
    """Insert a single index metadata entry into the registry.

    Args:
        conn: Active database connection
        schema_name: User schema name
        entry: Index metadata entry to insert
    """
    insert_sql: str = (
        f"INSERT INTO {schema_name}.index_metadata "
        "(id, dataset_id, column_name, index_name, index_type, "
        "capability, generated_column_name, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (dataset_id, column_name, index_type) DO UPDATE SET "
        "status = EXCLUDED.status, index_name = EXCLUDED.index_name"
    )
    with conn.cursor() as cur:
        cur.execute(
            insert_sql,
            (
                str(entry.id),
                str(entry.dataset_id),
                entry.column_name,
                entry.index_name,
                entry.index_type.value,
                entry.capability.value,
                entry.generated_column_name,
                entry.status.value,
                entry.created_at,
            ),
        )


def _create_btree_indexes(
    params: _IndexParams,
    columns: list[dict[str, Any]],
) -> list[IndexMetadataEntry]:
    """Create B-tree indexes on all data columns (FR-001).

    Args:
        params: Shared index creation parameters.
        columns: Column definitions with 'name' and 'type' keys.

    Returns:
        List of created IndexMetadataEntry objects.

    Raises:
        IndexCreationError: If any B-tree index creation fails.
    """
    results: list[IndexMetadataEntry] = []

    for col in columns:
        col_name: str = col["name"]
        index_name: str = generate_index_name(params.table_name, col_name, "btree")

        entry: IndexMetadataEntry = IndexMetadataEntry(
            id=uuid4(),
            dataset_id=params.ds_uuid,
            column_name=col_name,
            index_name=index_name,
            index_type=IndexType.BTREE,
            capability=IndexCapability.FILTERING,
            status=IndexStatus.PENDING,
            created_at=params.now,
        )

        start_time: float = time.monotonic()
        try:
            with params.conn.cursor() as cur:
                cur.execute(
                    sql.SQL(_BTREE_CREATE_SQL).format(
                        idx_name=sql.Identifier(index_name),
                        schema=sql.Identifier(params.schema_name),
                        table=sql.Identifier(params.table_name),
                        col=sql.Identifier(col_name),
                    )
                )

            duration_ms: float = (time.monotonic() - start_time) * 1000
            entry = entry.model_copy(update={"status": IndexStatus.CREATED})
            results.append(entry)

            log_event(
                logger=logger,
                level="info",
                event="index_created",
                user=params.username,
                extra={
                    "index_name": index_name,
                    "index_type": "btree",
                    "column_name": col_name,
                    "duration_ms": round(duration_ms, 1),
                },
            )

        except Exception as exc:
            entry = entry.model_copy(update={"status": IndexStatus.FAILED})
            _insert_metadata_entry(params.conn, params.schema_name, entry)
            params.conn.commit()
            raise IndexCreationError(
                message=(f"Failed to create B-tree index" f" on {col_name}: {exc}"),
                partial_results=results,
                failed_index=index_name,
            ) from exc

    return results


def _create_fts_indexes(
    params: _IndexParams,
    text_columns: list[dict[str, Any]],
) -> list[IndexMetadataEntry]:
    """Create tsvector columns and GIN indexes on TEXT columns (FR-002).

    Skips identifier-like columns per FR-002 heuristic.

    Args:
        params: Shared index creation parameters.
        text_columns: TEXT column definitions with 'name' key.

    Returns:
        List of created IndexMetadataEntry objects.

    Raises:
        IndexCreationError: If any FTS index creation fails.
    """
    results: list[IndexMetadataEntry] = []

    for col in text_columns:
        col_name: str = col["name"]

        # FR-002 heuristic: skip identifier-like columns
        if _is_identifier_column(
            params.conn,
            params.schema_name,
            params.table_name,
            col_name,
        ):
            log_event(
                logger=logger,
                level="info",
                event="fts_index_skipped_identifier",
                user=params.username,
                extra={
                    "column_name": col_name,
                    "table_name": params.table_name,
                },
            )
            continue

        ts_col_name: str = f"_ts_{col_name}"
        gin_index_name: str = generate_index_name(params.table_name, col_name, "gin")

        gin_entry: IndexMetadataEntry = IndexMetadataEntry(
            id=uuid4(),
            dataset_id=params.ds_uuid,
            column_name=col_name,
            index_name=gin_index_name,
            index_type=IndexType.GIN,
            capability=IndexCapability.FULL_TEXT_SEARCH,
            generated_column_name=ts_col_name,
            status=IndexStatus.PENDING,
            created_at=params.now,
        )

        start_time: float = time.monotonic()
        try:
            _execute_fts_ddl(params, col_name, ts_col_name, gin_index_name)

            duration_ms: float = (time.monotonic() - start_time) * 1000
            gin_entry = gin_entry.model_copy(update={"status": IndexStatus.CREATED})
            results.append(gin_entry)

            log_event(
                logger=logger,
                level="info",
                event="index_created",
                user=params.username,
                extra={
                    "index_name": gin_index_name,
                    "index_type": "gin",
                    "column_name": col_name,
                    "generated_column": ts_col_name,
                    "duration_ms": round(duration_ms, 1),
                },
            )

        except IndexCreationError:
            raise
        except Exception as exc:
            gin_entry = gin_entry.model_copy(update={"status": IndexStatus.FAILED})
            _insert_metadata_entry(params.conn, params.schema_name, gin_entry)
            params.conn.commit()
            raise IndexCreationError(
                message=(f"Failed to create FTS index on {col_name}: {exc}"),
                partial_results=results,
                failed_index=gin_index_name,
            ) from exc

    return results


def _execute_fts_ddl(
    params: _IndexParams,
    col_name: str,
    ts_col_name: str,
    gin_index_name: str,
) -> None:
    """Execute ALTER TABLE and CREATE INDEX for a single FTS column.

    Args:
        params: Shared index creation parameters.
        col_name: Source text column name.
        ts_col_name: Generated tsvector column name.
        gin_index_name: GIN index name.
    """
    with params.conn.cursor() as cur:
        cur.execute(
            sql.SQL(_TSVECTOR_ALTER_SQL).format(
                schema=sql.Identifier(params.schema_name),
                table=sql.Identifier(params.table_name),
                ts_col=sql.Identifier(ts_col_name),
                col=sql.Identifier(col_name),
            )
        )

    with params.conn.cursor() as cur:
        cur.execute(
            sql.SQL(_GIN_CREATE_SQL).format(
                idx_name=sql.Identifier(gin_index_name),
                schema=sql.Identifier(params.schema_name),
                table=sql.Identifier(params.table_name),
                ts_col=sql.Identifier(ts_col_name),
            )
        )


def create_indexes_for_dataset(
    conn: Connection[tuple[str, ...]],
    username: str,
    dataset_id: str,
    table_name: str,
    columns: list[dict[str, Any]],
) -> list[IndexMetadataEntry]:
    """Create B-tree and full-text search indexes on all data columns.

    For each column: creates a B-tree index. For TEXT columns (unless
    identifier-like per FR-002 heuristic): creates a tsvector generated
    column and GIN index.

    Args:
        conn: Active database connection (caller manages transaction).
        username: User's username (determines schema name).
        dataset_id: UUID of the dataset.
        table_name: Name of the data table (e.g., 'products_data').
        columns: List of column definitions from schema detection.
            Each dict has keys: 'name' (str), 'type' (str).

    Returns:
        List of IndexMetadataEntry objects for all created indexes.

    Raises:
        IndexCreationError: If any index creation fails.
            Contains partial_results with successfully created indexes.
    """
    schema_name: str = f"{username}_schema"
    now: datetime = datetime.now(UTC)
    ds_uuid: UUID = UUID(dataset_id)
    params: _IndexParams = _IndexParams(
        conn=conn,
        schema_name=schema_name,
        table_name=table_name,
        ds_uuid=ds_uuid,
        now=now,
        username=username,
    )

    # Phase 1: B-tree indexes on all columns (FR-001)
    log_event(
        logger=logger,
        level="info",
        event="btree_index_creation_start",
        user=username,
        extra={
            "table_name": table_name,
            "column_count": len(columns),
        },
    )

    btree_results: list[IndexMetadataEntry] = _create_btree_indexes(params, columns)

    # Phase 2: tsvector + GIN indexes on TEXT columns (FR-002)
    text_columns: list[dict[str, Any]] = [c for c in columns if c.get("type", "").upper() == "TEXT"]

    log_event(
        logger=logger,
        level="info",
        event="fts_index_creation_start",
        user=username,
        extra={
            "table_name": table_name,
            "text_column_count": len(text_columns),
        },
    )

    fts_results: list[IndexMetadataEntry] = _create_fts_indexes(params, text_columns)

    results: list[IndexMetadataEntry] = btree_results + fts_results

    # Insert all metadata entries
    for entry in results:
        _insert_metadata_entry(conn, schema_name, entry)

    conn.commit()

    log_event(
        logger=logger,
        level="info",
        event="index_creation_complete",
        user=username,
        extra={
            "table_name": table_name,
            "total_indexes": len(results),
        },
    )

    return results


def _build_grouped_entries(
    rows: list[tuple[Any, ...]],
) -> dict[tuple[str, str], list[IndexMetadataEntry]]:
    """Group raw metadata rows by (dataset_id, column_name).

    Args:
        rows: Raw rows from index_metadata query.

    Returns:
        Dict mapping (dataset_id, column_name) to list of entries.
    """
    grouped: dict[tuple[str, str], list[IndexMetadataEntry]] = {}
    for row in rows:
        entry: IndexMetadataEntry = IndexMetadataEntry(
            id=row[0],
            dataset_id=row[1],
            column_name=row[2],
            index_name=row[3],
            index_type=IndexType(row[4]),
            capability=IndexCapability(row[5]),
            generated_column_name=row[6],
            status=IndexStatus(row[7]),
            created_at=row[8],
        )
        key: tuple[str, str] = (str(entry.dataset_id), entry.column_name)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(entry)
    return grouped


def get_index_profiles(
    conn: Connection[tuple[str, ...]],
    username: str,
    dataset_ids: list[str],
) -> dict[str, list[DataColumnIndexProfile]]:
    """Get index profiles for all columns across specified datasets.

    Args:
        conn: Active database connection.
        username: User's username.
        dataset_ids: List of dataset UUIDs to query.

    Returns:
        Dict mapping dataset_id to list of DataColumnIndexProfile.
        Each profile contains all indexes for a single column.
    """
    if not dataset_ids:
        return {}

    schema_name: str = f"{username}_schema"
    query_sql: str = (
        f"SELECT id, dataset_id, column_name, index_name, "
        f"index_type, capability, generated_column_name, "
        f"status, created_at "
        f"FROM {schema_name}.index_metadata "
        f"WHERE dataset_id IN "
        f"({', '.join(['%s'] * len(dataset_ids))}) "
        f"ORDER BY dataset_id, column_name, index_type"
    )

    with conn.cursor() as cur:
        cur.execute(query_sql, tuple(dataset_ids))
        rows: list[tuple[Any, ...]] = cur.fetchall()

    grouped: dict[tuple[str, str], list[IndexMetadataEntry]] = _build_grouped_entries(rows)

    # Build profiles grouped by dataset_id
    result: dict[str, list[DataColumnIndexProfile]] = {}
    for (ds_id, col_name), entries in grouped.items():
        profile: DataColumnIndexProfile = DataColumnIndexProfile(
            column_name=col_name,
            dataset_id=UUID(ds_id),
            indexes=entries,
        )
        if ds_id not in result:
            result[ds_id] = []
        result[ds_id].append(profile)

    return result


def _format_column_lines(
    profile: DataColumnIndexProfile,
) -> list[str]:
    """Format INDEX CAPABILITIES lines for a single column profile.

    Args:
        profile: Column index profile to format.

    Returns:
        List of formatted text lines for this column.
    """
    has_btree: bool = any(idx.index_type == IndexType.BTREE for idx in profile.indexes)
    col_type: str = "TEXT" if profile.has_fulltext else "NUMERIC"
    lines: list[str] = [f"  Column: {profile.column_name} ({col_type})"]

    if has_btree:
        btree_desc: str = "    - B-tree: supports =, <, >, BETWEEN, ORDER BY"
        if col_type == "TEXT":
            btree_desc += ", LIKE 'prefix%'"
        lines.append(btree_desc)

    if profile.has_fulltext and profile.fulltext_column:
        ts_col: str = profile.fulltext_column
        lines.append(f"    - Full-text search via '{ts_col}':")
        lines.append(f"      WHERE {ts_col} @@ " + "plainto_tsquery('english', %s)")
        lines.append(f"      ORDER BY ts_rank({ts_col}, " + "plainto_tsquery('english', %s)) DESC")
        lines.append("      PREFER full-text search over ILIKE" + " for text searches.")

    if profile.has_vector and profile.embedding_column:
        emb_col: str = profile.embedding_column
        lines.append(f"    - Vector similarity via '{emb_col}' (1536d):")
        lines.append(f"      ORDER BY {emb_col} <=> %s::vector LIMIT 10")
        lines.append("      Use for semantic/meaning-based searches.")

    lines.append("")
    return lines


def build_index_context(
    profiles: dict[str, list[DataColumnIndexProfile]],
    table_names: dict[str, str],
) -> str:
    """Build the INDEX CAPABILITIES context for SQL generation task.

    Produces a formatted text block per sql-generation-task-context
    contract. Enforces 4000-char cap per FR-018.

    Args:
        profiles: Index profiles from get_index_profiles().
        table_names: Dict mapping dataset_id to table_name.

    Returns:
        Formatted text block describing available indexes.
        Empty string if no profiles.
    """
    if not profiles:
        return ""

    lines: list[str] = [
        "INDEX CAPABILITIES (use these for optimal query" + " performance):",
        "=" * 80,
    ]

    for ds_id, column_profiles in profiles.items():
        t_name: str = table_names.get(ds_id, "unknown_table")
        lines.append(f"Table: {t_name}")
        lines.append("")

        for profile in column_profiles:
            lines.extend(_format_column_lines(profile))

    lines.append("=" * 80)
    lines.extend(_CONTEXT_RULES)

    context: str = "\n".join(lines)

    # Enforce 4000-char cap per FR-018
    if len(context) > _MAX_INDEX_CONTEXT_CHARS:
        context = context[: _MAX_INDEX_CONTEXT_CHARS - 3] + "..."

    return context


def identify_qualifying_columns(
    conn: Connection[tuple[str, ...]],
    username: str,
    table_name: str,
    text_columns: list[str],
    *,
    min_avg_length: int = 50,
    sample_size: int = 1000,
) -> list[str]:
    """Identify text columns with sufficient content for embeddings.

    Args:
        conn: Active database connection.
        username: User's username.
        table_name: Data table name.
        text_columns: List of TEXT column names to evaluate.
        min_avg_length: Minimum average character length threshold.
        sample_size: Number of rows to sample for average calculation.

    Returns:
        List of column names that qualify for embedding generation.
    """
    if not text_columns:
        return []

    schema_name: str = f"{username}_schema"
    qualifying: list[str] = []

    for col_name in text_columns:
        query: sql.Composed = sql.SQL(
            "SELECT AVG(LENGTH({col})) FROM ("
            "  SELECT {col} FROM {schema}.{table}"
            "  WHERE {col} IS NOT NULL AND {col} != ''"
            "  LIMIT {limit}"
            ") sub"
        ).format(
            col=sql.Identifier(col_name),
            schema=sql.Identifier(schema_name),
            table=sql.Identifier(table_name),
            limit=sql.Literal(sample_size),
        )

        with conn.cursor() as cur:
            cur.execute(query)
            row: tuple[Any, ...] | None = cur.fetchone()

        if row and row[0] is not None:
            avg_len: float = float(row[0])
            if avg_len >= min_avg_length:
                qualifying.append(col_name)

    return qualifying
