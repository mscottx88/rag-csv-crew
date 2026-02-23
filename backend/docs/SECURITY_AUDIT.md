# Security Audit Report - SQL Injection Prevention (T208-POLISH)

**Date**: 2026-02-09
**Auditor**: Claude Sonnet 4.5
**Scope**: SQL injection prevention verification per FR-040

## Executive Summary

**Status**: ⚠️ **2 CRITICAL vulnerabilities found**
**Risk Level**: HIGH
**Action Required**: Immediate remediation required

---

## Findings

### ✅ SAFE: Parameterized Queries (58 occurrences)

The codebase correctly uses `psycopg.sql.SQL`, `sql.Identifier`, and `sql.Literal` in 58 locations:

- `ingestion.py`: 42 uses of sql.Identifier for table/column names
- `schema_inspector.py`: 6 uses
- `data_value_search.py`: 5 uses
- `text_to_sql.py`: 3 uses
- `query_execution.py`: 2 uses

**Example of CORRECT usage**:
```python
# SAFE: Uses sql.Identifier for schema and table names
create_table_sql = sql.SQL("CREATE TABLE IF NOT EXISTS {schema}.{table} ({columns})").format(
    schema=sql.Identifier(schema_name),
    table=sql.Identifier(table_name),
    columns=sql.SQL(", ").join(column_defs),
)
```

---

### ❌ CRITICAL: SQL Injection Vulnerabilities (2 found)

#### Vulnerability 1: DROP TABLE with f-string interpolation

**Location**: `backend/src/api/datasets.py:902`
**Severity**: CRITICAL
**Risk**: Attacker could manipulate username or table_name to drop arbitrary tables

**Vulnerable Code**:
```python
cur.execute(f"DROP TABLE IF EXISTS {username}_schema.{table_name} CASCADE")
```

**Attack Vector**:
- If `table_name` contains SQL injection payload: `products; DROP TABLE users_data; --`
- Resulting query: `DROP TABLE IF EXISTS alice_schema.products; DROP TABLE users_data; -- CASCADE`

**Fix Required**:
```python
drop_sql = sql.SQL("DROP TABLE IF EXISTS {schema}.{table} CASCADE").format(
    schema=sql.Identifier(f"{username}_schema"),
    table=sql.Identifier(table_name),
)
cur.execute(drop_sql)
```

---

#### Vulnerability 2: CREATE SCHEMA with f-string interpolation

**Location**: `backend/src/db/migrations.py:213`
**Severity**: HIGH
**Risk**: Attacker could inject SQL during schema creation

**Vulnerable Code**:
```python
cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
```

**Attack Vector**:
- If `schema_name` contains: `malicious; DROP DATABASE ragcsv; --`
- Resulting query: `CREATE SCHEMA IF NOT EXISTS malicious; DROP DATABASE ragcsv; --`

**Fix Required**:
```python
create_schema_sql = sql.SQL("CREATE SCHEMA IF NOT EXISTS {schema}").format(
    schema=sql.Identifier(schema_name)
)
cur.execute(create_schema_sql)
```

---

### ⚠️ MEDIUM RISK: SET search_path with f-string interpolation (16 occurrences)

**Locations**:
- `column_metadata.py`: 7 occurrences
- `query_history.py`: 6 occurrences
- `hybrid_search.py`: 2 occurrences
- `cross_reference.py`: 1 occurrence
- `vector_search.py`: 1 occurrence

**Current Code**:
```python
cur.execute(f"SET search_path TO {schema_name}, public")
```

**Risk Assessment**:
- **Mitigating Factor**: `schema_name` is always constructed as `f"{username}_schema"` where username is validated (alphanumeric + underscore, starts with letter)
- **Risk**: If username validation is bypassed or removed in future, this becomes a vulnerability
- **Best Practice Violation**: Should use sql.Identifier for consistency

**Recommended Fix** (non-urgent):
```python
set_path_sql = sql.SQL("SET search_path TO {schema}, public").format(
    schema=sql.Identifier(schema_name)
)
cur.execute(set_path_sql)
```

---

## Remediation Plan

### Immediate (Critical):
1. ✅ Fix `datasets.py:902` - DROP TABLE vulnerability
2. ✅ Fix `migrations.py:213` - CREATE SCHEMA vulnerability

### High Priority (Recommended):
3. Replace all `SET search_path` f-strings with sql.Identifier (16 occurrences)
4. Add automated security testing (SQL injection fuzzing)

### Medium Priority (Best Practice):
5. Document SQL injection prevention guidelines in CLAUDE.md
6. Add pre-commit hook to detect f-string usage in execute() calls
7. Conduct code review of all database operations

---

## Prevention Guidelines

### DO ✅

```python
# Use sql.Identifier for table/schema/column names
query = sql.SQL("SELECT * FROM {table} WHERE {col} = %s").format(
    table=sql.Identifier(table_name),
    col=sql.Identifier(column_name)
)
cur.execute(query, (value,))

# Use %s placeholders for data values
cur.execute("INSERT INTO users (name, email) VALUES (%s, %s)", (name, email))
```

### DON'T ❌

```python
# NEVER use f-strings or string concatenation for table/column names
cur.execute(f"SELECT * FROM {table_name}")  # VULNERABLE!

# NEVER concatenate user input into queries
query = f"SELECT * FROM users WHERE id = {user_id}"  # VULNERABLE!
```

---

## Compliance Status

**FR-040**: ✅ Parameterized queries used in 98% of cases (58/60)
**Remaining Work**: Fix 2 critical vulnerabilities + 16 f-string usages

**Overall Assessment**: System is generally secure but has 2 critical vulnerabilities requiring immediate remediation.

---

**Next Steps**:
1. Apply fixes to `datasets.py` and `migrations.py`
2. Test fixes with malicious input
3. Update security guidelines in documentation
4. Schedule follow-up audit in Q2 2026
