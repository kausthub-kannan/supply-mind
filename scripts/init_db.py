"""
db_init.py
Creates the SupplyMind PostgreSQL schema, builds all tables with constraints,
and bulk-loads data from the CSV files produced by data_generator.py.

Dependencies:
    pip install psycopg2-binary

Usage:
    python data_generator.py          # generate CSVs first
    python db_init.py                 # create schema and load data

Connection is configured via environment variables (recommended) or by
editing the DB_CONFIG dict below directly.

    export PG_HOST=localhost
    export PG_PORT=5432
    export PG_DB=supplymind
    export PG_USER=postgres
    export PG_PASSWORD=yourpassword
"""

import csv
import json
import os
import sys

import psycopg2
import psycopg2.extras

# ── Connection config ─────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST",     "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname":   os.getenv("POSTGRES_DB",       "supplymind"),
    "user":     os.getenv("POSTGRES_USER",     "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

DATA_DIR = "data"

CSV_FILES = {
    "suppliers":      f"{DATA_DIR}/suppliers.csv",
    "inventory":      f"{DATA_DIR}/inventory.csv",
    "consumption_log":f"{DATA_DIR}/consumption_log.csv",
    "supplier_orders":f"{DATA_DIR}/supplier_orders.csv",
    "returns":        f"{DATA_DIR}/returns.csv",
}

# ── DDL ───────────────────────────────────────────────────────────────────────
# Each statement is a separate string so they can be executed individually.
# Postgres-specific choices:
#   - SERIAL           → auto-incrementing PK
#   - NUMERIC(10,2)    → exact decimal for costs / order values
#   - TIMESTAMPTZ      → timestamps with timezone
#   - DATE             → date-only column
#   - JSONB            → binary JSON with indexing support
#   - ON CONFLICT DO NOTHING → idempotent re-runs

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id       SERIAL          PRIMARY KEY,
        supplier_name     TEXT            NOT NULL,
        lead_time_days    INTEGER         NOT NULL CHECK (lead_time_days > 0),
        contact_email     TEXT            NOT NULL,
        reliability_score NUMERIC(4,2)   NOT NULL CHECK (reliability_score BETWEEN 0 AND 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory (
        sku_id            SERIAL          PRIMARY KEY,
        sku_name          TEXT            NOT NULL,
        location          TEXT            NOT NULL,
        current_quantity  INTEGER         NOT NULL DEFAULT 0,
        reorder_threshold INTEGER         NOT NULL,
        unit_cost         NUMERIC(10,2)   NOT NULL CHECK (unit_cost >= 0),
        supplier_id       INTEGER         NOT NULL REFERENCES suppliers (supplier_id),
        last_updated      TIMESTAMPTZ     NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consumption_log (
        log_id            SERIAL          PRIMARY KEY,
        sku_id            INTEGER         NOT NULL REFERENCES inventory (sku_id),
        quantity_consumed INTEGER         NOT NULL CHECK (quantity_consumed > 0),
        date              DATE            NOT NULL,
        location          TEXT            NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS supplier_orders (
        order_id          SERIAL          PRIMARY KEY,
        email_thread_id   TEXT            NOT NULL,
        sku_id            INTEGER         NOT NULL REFERENCES inventory (sku_id),
        supplier_id       INTEGER         NOT NULL REFERENCES suppliers (supplier_id),
        quantity_ordered  INTEGER         NOT NULL CHECK (quantity_ordered > 0),
        order_value       NUMERIC(12,2)   NOT NULL CHECK (order_value >= 0),
        status            TEXT            NOT NULL
                              CHECK (status IN ('pending','confirmed','shipped','delivered','cancelled')),
        created_at        TIMESTAMPTZ     NOT NULL,
        expected_delivery TIMESTAMPTZ     NOT NULL,
        agent_trace       JSONB
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS returns (
        return_id         SERIAL          PRIMARY KEY,
        email_thread_id   TEXT            NOT NULL,
        customer_email    TEXT            NOT NULL,
        order_id          INTEGER         NOT NULL REFERENCES supplier_orders (order_id),
        reason            TEXT            NOT NULL,
        status            TEXT            NOT NULL
                              CHECK (status IN ('open','under_review','approved','rejected','refunded')),
        agent_decision    JSONB,
        created_at        TIMESTAMPTZ     NOT NULL,
        resolved_at       TIMESTAMPTZ
    )
    """,
    # B-tree indexes
    "CREATE INDEX IF NOT EXISTS idx_inventory_supplier   ON inventory       (supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_sku      ON consumption_log (sku_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_date     ON consumption_log (date)",
    "CREATE INDEX IF NOT EXISTS idx_orders_sku           ON supplier_orders (sku_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_supplier      ON supplier_orders (supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_status        ON supplier_orders (status)",
    "CREATE INDEX IF NOT EXISTS idx_returns_order        ON returns         (order_id)",
    "CREATE INDEX IF NOT EXISTS idx_returns_status       ON returns         (status)",
    "CREATE INDEX IF NOT EXISTS idx_orders_agent_trace   ON supplier_orders USING GIN (agent_trace)",
    "CREATE INDEX IF NOT EXISTS idx_returns_agent_dec    ON returns         USING GIN (agent_decision)",
]

# ── Column type hints (drives CSV → Python coercion) ──────────────────────────
INT_COLS  = {
    "supplier_id", "lead_time_days",
    "sku_id", "current_quantity", "reorder_threshold",
    "log_id", "quantity_consumed",
    "order_id", "quantity_ordered",
    "return_id",
}
FLOAT_COLS = {"reliability_score", "unit_cost", "order_value"}
JSON_COLS  = {"agent_trace", "agent_decision"}   # stored as JSONB

def _coerce(value: str, col_name: str):
    if value == "":
        return None
    if col_name in JSON_COLS:
        return psycopg2.extras.Json(json.loads(value))
    if col_name in INT_COLS:
        return int(value)
    if col_name in FLOAT_COLS:
        return float(value)
    return value


# ── Loader ────────────────────────────────────────────────────────────────────

def load_csv(cur, table: str, filepath: str) -> int:
    """Read *filepath* and bulk-insert into *table*. Returns inserted row count."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"CSV not found: {filepath}\n"
            "Run  python data_generator.py  first."
        )

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    if not rows:
        print(f"  [!] {filepath} is empty — skipping {table}")
        return 0

    cols = list(rows[0].keys())
    data = [tuple(_coerce(row[c], c) for c in cols) for row in rows]

    # execute_values is significantly faster than executemany for bulk loads
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    return len(data)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']} "
          f"→ database '{DB_CONFIG['dbname']}' …")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] Could not connect to PostgreSQL:\n  {e}", file=sys.stderr)
        sys.exit(1)

    conn.autocommit = False
    cur = conn.cursor()

    # ── Schema ────────────────────────────────────────────────────────────────
    print("\n── Creating schema ──────────────────────────────────")
    try:
        for stmt in DDL_STATEMENTS:
            cur.execute(stmt)
        conn.commit()
        print("  Tables and indexes created (or already exist).")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"\n[ERROR] Schema creation failed:\n  {e}", file=sys.stderr)
        cur.close(); conn.close()
        sys.exit(1)

    # ── Data load (FK-safe order) ─────────────────────────────────────────────
    load_order = [
        ("suppliers",       CSV_FILES["suppliers"]),
        ("inventory",       CSV_FILES["inventory"]),
        ("consumption_log", CSV_FILES["consumption_log"]),
        ("supplier_orders", CSV_FILES["supplier_orders"]),
        ("returns",         CSV_FILES["returns"]),
    ]

    print("\n── Loading CSV data ─────────────────────────────────")
    total = 0
    for table, filepath in load_order:
        try:
            n = load_csv(cur, table, filepath)
            conn.commit()
            print(f"  [✓] {table:<20} {n:>4} rows loaded")
            total += n
        except FileNotFoundError as e:
            conn.rollback()
            print(f"\n[ERROR] {e}", file=sys.stderr)
            cur.close(); conn.close()
            sys.exit(1)
        except (psycopg2.Error, json.JSONDecodeError) as e:
            conn.rollback()
            print(f"\n[ERROR] Failed loading {table}:\n  {e}", file=sys.stderr)
            cur.close(); conn.close()
            sys.exit(1)

    # ── Sync sequences so future INSERTs don't collide with seeded IDs ────────
    print("\n── Syncing sequences ────────────────────────────────")
    seq_map = {
        "suppliers":       "supplier_id",
        "inventory":       "sku_id",
        "consumption_log": "log_id",
        "supplier_orders": "order_id",
        "returns":         "return_id",
    }
    for tbl, pk in seq_map.items():
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{tbl}', '{pk}'), MAX({pk})) FROM {tbl}"
        )
    conn.commit()
    print("  Sequences updated.")

    # ── Verification ─────────────────────────────────────────────────────────
    print("\n── Row counts (verification) ────────────────────────")
    for table, _ in load_order:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        (count,) = cur.fetchone()
        print(f"  {table:<25} {count:>4} rows")

    cur.close()
    conn.close()
    print(f"\n✓ Done — {total} total rows loaded into '{DB_CONFIG['dbname']}'\n")


if __name__ == "__main__":
    main()