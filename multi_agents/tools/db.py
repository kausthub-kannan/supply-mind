import os
import re
import logging
from typing import Any, Optional
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import sql, OperationalError, DatabaseError
from langchain_core.tools import tool

from schemas.db import SelectInput, UpdateInput, InsertInput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     os.getenv(""),
    "port":     os.getenv(""),
    "dbname":   os.getenv(""),
    "user":     os.getenv(""),
    "password": os.getenv(""),
}

MAX_ROWS = 500
ALLOWED_TABLES: set[str] = set()

@contextmanager
def get_connection(autocommit: bool = False):
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = autocommit
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def _validate_table(table: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", table):
        raise ValueError(f"Invalid table name: '{table}'")
    if ALLOWED_TABLES and table not in ALLOWED_TABLES:
        raise PermissionError(f"Table '{table}' is not in the allowed list.")


def _validate_columns(columns: list[str]) -> None:
    for col in columns:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", col):
            raise ValueError(f"Invalid column name: '{col}'")


def _format_rows(rows: list[dict]) -> str:
    if not rows:
        return "No rows returned."
    header = " | ".join(rows[0].keys())
    sep    = "-" * len(header)
    lines  = [header, sep] + [" | ".join(str(v) for v in r.values()) for r in rows]
    return "\n".join(lines)

# ── Tools ─────────────────────────────────────────────────────────────────────
@tool(args_schema=SelectInput)
def sql_select(
    table: str,
    columns: list[str] = ["*"],
    where: Optional[str] = None,
    params: Optional[list] = None,
    order_by: Optional[str] = None,
    limit: int = 50,
) -> str:
    try:
        _validate_table(table)
        if columns != ["*"]:
            _validate_columns(columns)

        actual_limit = min(limit, MAX_ROWS)
        col_clause   = ", ".join(columns)  # safe: validated above

        # Build query with psycopg2.sql for identifier safety
        query = sql.SQL("SELECT {cols} FROM {tbl}").format(
            cols=sql.SQL(col_clause) if columns == ["*"] else sql.SQL(", ").join(
                map(sql.Identifier, columns)
            ),
            tbl=sql.Identifier(table),
        )

        if where:
            query = sql.SQL("{q} WHERE {w}").format(q=query, w=sql.SQL(where))
        if order_by:
            query = sql.SQL("{q} ORDER BY {o}").format(q=query, o=sql.SQL(order_by))
        query = sql.SQL("{q} LIMIT {l}").format(q=query, l=sql.Literal(actual_limit))

        logger.info("SELECT on table '%s' (limit %d)", table, actual_limit)

        with get_connection(autocommit=True) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params or [])
                rows = [dict(r) for r in cur.fetchall()]

        result = _format_rows(rows)
        if len(rows) == actual_limit:
            result += f"\n\n[Result capped at {actual_limit} rows]"
        return result

    except (ValueError, PermissionError) as e:
        return f"Validation error: {e}"
    except OperationalError as e:
        logger.error("DB connection error: %s", e)
        return "Database connection failed. Check your configuration."
    except DatabaseError as e:
        logger.error("Query error: %s", e)
        return f"Query failed: {e.pgerror or 'unknown database error'}"
    except Exception as e:
        logger.exception("Unexpected error in sql_select")
        return f"Unexpected error: {type(e).__name__}"


@tool(args_schema=InsertInput)
def sql_insert(
    table: str,
    rows: list[dict],
    returning: list[str] = [],
    on_conflict: Optional[str] = None,
) -> str:
    """
    Insert one or more rows into a PostgreSQL table using executemany.

    Supports ON CONFLICT clauses and RETURNING.
    Rolls back the entire batch on any failure.
    """
    try:
        if not rows:
            return "Nothing to insert: 'rows' list is empty."

        _validate_table(table)
        columns = list(rows[0].keys())
        _validate_columns(columns)

        # Ensure every row has the same columns
        if any(list(r.keys()) != columns for r in rows):
            return "All rows must have identical column sets."

        col_ids  = sql.SQL(", ").join(map(sql.Identifier, columns))
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))

        query = sql.SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals})").format(
            tbl=sql.Identifier(table), cols=col_ids, vals=placeholders
        )
        if on_conflict:
            query = sql.SQL("{q} ON CONFLICT {oc}").format(
                q=query, oc=sql.SQL(on_conflict)
            )
        if returning:
            _validate_columns(returning)
            ret_clause = sql.SQL(", ").join(map(sql.Identifier, returning))
            query = sql.SQL("{q} RETURNING {r}").format(q=query, r=ret_clause)

        values = [[r[c] for c in columns] for r in rows]

        logger.info("INSERT %d row(s) into '%s'", len(rows), table)

        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if returning:
                    returned = []
                    for row_vals in values:
                        cur.execute(query, row_vals)
                        returned.extend(dict(r) for r in cur.fetchall())
                    return (
                        f"Inserted {len(rows)} row(s).\nReturned:\n"
                        + _format_rows(returned)
                    )
                else:
                    psycopg2.extras.execute_batch(cur, query, values, page_size=100)
                    return f"Successfully inserted {len(rows)} row(s) into '{table}'."

    except (ValueError, PermissionError) as e:
        return f"Validation error: {e}"
    except OperationalError as e:
        logger.error("DB connection error: %s", e)
        return "Database connection failed."
    except DatabaseError as e:
        logger.error("Insert error: %s", e)
        return f"Insert failed: {e.pgerror or 'unknown database error'}"
    except Exception as e:
        logger.exception("Unexpected error in sql_insert")
        return f"Unexpected error: {type(e).__name__}"


@tool(args_schema=UpdateInput)
def sql_update(
    table: str,
    values: dict[str, Any],
    where: str,
    params: Optional[list] = None,
    returning: list[str] = [],
) -> str:
    """
    Execute a safe parameterized UPDATE on a PostgreSQL table.

    A WHERE clause is mandatory to prevent accidental full-table updates.
    Supports RETURNING for confirmation of changed values.
    """
    try:
        if not values:
            return "Nothing to update: 'values' dict is empty."
        if not where.strip():
            return "Safety error: WHERE clause cannot be empty."

        _validate_table(table)
        _validate_columns(list(values.keys()))

        # Build SET clause:  col1 = %s, col2 = %s, ...
        set_clause = sql.SQL(", ").join(
            sql.SQL("{col} = {ph}").format(
                col=sql.Identifier(col), ph=sql.Placeholder()
            )
            for col in values
        )

        query = sql.SQL("UPDATE {tbl} SET {set} WHERE {where}").format(
            tbl=sql.Identifier(table),
            set=set_clause,
            where=sql.SQL(where),
        )

        if returning:
            _validate_columns(returning)
            ret_clause = sql.SQL(", ").join(map(sql.Identifier, returning))
            query = sql.SQL("{q} RETURNING {r}").format(q=query, r=ret_clause)

        # params order: SET values first, then WHERE params
        all_params = list(values.values()) + (params or [])

        logger.info("UPDATE table '%s' WHERE %s", table, where)

        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, all_params)
                affected = cur.rowcount

                if returning:
                    returned = [dict(r) for r in cur.fetchall()]
                    return (
                        f"Updated {affected} row(s).\nReturned:\n"
                        + _format_rows(returned)
                    )
                return f"Successfully updated {affected} row(s) in '{table}'."

    except (ValueError, PermissionError) as e:
        return f"Validation error: {e}"
    except OperationalError as e:
        logger.error("DB connection error: %s", e)
        return "Database connection failed."
    except DatabaseError as e:
        logger.error("Update error: %s", e)
        return f"Update failed: {e.pgerror or 'unknown database error'}"
    except Exception as e:
        logger.exception("Unexpected error in sql_update")
        return f"Unexpected error: {type(e).__name__}"