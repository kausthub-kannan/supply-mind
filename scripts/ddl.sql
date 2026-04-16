CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id       TEXT            PRIMARY KEY,
    supplier_name     TEXT            NOT NULL,
    lead_time_days    INTEGER         NOT NULL CHECK (lead_time_days > 0),
    contact_email     TEXT            NOT NULL,
    reliability_score DOUBLE PRECISION    NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id      TEXT          PRIMARY KEY,
    sku_id            TEXT          NOT NULL,
    sku_name          TEXT            NOT NULL,
    current_quantity  INTEGER         NOT NULL DEFAULT 0,
    unit_cost         DOUBLE PRECISION   NOT NULL CHECK (unit_cost >= 0),
    category          TEXT            NOT NULL,
    region            TEXT            NOT NULL,
    specs_level       TEXT            NOT NULL CHECK (specs_level IN (
                                        'entry',
                                        'mid',
                                        'high'
                                      ))
);

CREATE TABLE IF NOT EXISTS supplier_sku_map (
    map_id            TEXT          PRIMARY KEY,
    sku_id            TEXT            NOT NULL,
    supplier_id       TEXT            NOT NULL
);

CREATE TABLE IF NOT EXISTS history_logs (
    log_id            TEXT          PRIMARY KEY,
    sku_id            TEXT            NOT NULL,
    date              DATE            NOT NULL,
    opening_stock     INTEGER         NOT NULL,
    units_sold        INTEGER         NOT NULL CHECK (units_sold >= 0),
    units_received    INTEGER         NOT NULL,
    units_returned    INTEGER         NOT NULL,
    closing_stock     INTEGER         NOT NULL,
    region            TEXT            NOT NULL,
    season            TEXT            NOT NULL,
    price             DOUBLE PRECISION NOT NULL,
    supplier_id       TEXT            NOT NULL,
    category          TEXT            NOT NULL,
    specs_level       TEXT            NOT NULL CHECK (specs_level IN (
                                              'entry',
                                              'mid',
                                              'high'
                                          ))
);

CREATE TABLE IF NOT EXISTS customer_orders (
    order_id              TEXT            PRIMARY KEY,
    sku_id                TEXT            NOT NULL,
    quantity_ordered      INTEGER         NOT NULL CHECK (quantity_ordered > 0),
    status                TEXT            NOT NULL CHECK (status IN (
                                              'confirmed',
                                              'shipped',
                                              'delivered',
                                              'cancelled'
                                          )),
    created_at            TIMESTAMP       NOT NULL,
    expected_delivery     TIMESTAMP       NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_orders (
    order_id              TEXT            PRIMARY KEY,
    sku_id                TEXT            NOT NULL,
    supplier_id           TEXT            NOT NULL REFERENCES suppliers (supplier_id),
    quantity_ordered      INTEGER         NOT NULL CHECK (quantity_ordered > 0),
    order_value           NUMERIC(12,2)   NOT NULL CHECK (order_value >= 0),
    status                TEXT            NOT NULL CHECK (status IN (
                                              'pending',
                                              'confirmed',
                                              'shipped',
                                              'delivered',
                                              'cancelled'
                                          )),
    email_thread_id       TEXT            NOT NULL,
    email_thread_summary  TEXT            NOT NULL,
    created_at            TIMESTAMP       NOT NULL,
    expected_delivery     TIMESTAMP       NOT NULL
);

CREATE TABLE IF NOT EXISTS returns (
    return_id             TEXT            PRIMARY KEY,
    order_id              TEXT            NOT NULL REFERENCES customer_orders (order_id),
    customer_email        TEXT            NOT NULL,
    reason                TEXT            NOT NULL,
    status                TEXT            NOT NULL CHECK (status IN (
                                              'open',
                                              'under_review',
                                              'approved',
                                              'rejected',
                                              'refunded'
                                          )),
    email_thread_id       TEXT            NOT NULL,
    email_thread_summary  TEXT            NOT NULL,
    created_at            TIMESTAMP       NOT NULL,
    resolved_at           TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id        TEXT             PRIMARY KEY,
    workflow_type      TEXT             NOT NULL,
    input_data         TEXT             NOT NULL,
    created_at         TIMESTAMP        NOT NULL,
    workflow_status    TEXT             NOT NULL CHECK (workflow_status IN (
                                            'completed',
                                            'in-progress',
                                            'failed',
                                            'in-review'
                                        ))
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- inventory
CREATE INDEX IF NOT EXISTS idx_inventory_sku         ON inventory        (sku_id);

-- supplier_sku_map
CREATE INDEX IF NOT EXISTS idx_map_sku               ON supplier_sku_map (sku_id);
CREATE INDEX IF NOT EXISTS idx_map_supplier          ON supplier_sku_map (supplier_id);

-- history_logs
CREATE INDEX IF NOT EXISTS idx_history_sku           ON history_logs     (sku_id);
CREATE INDEX IF NOT EXISTS idx_history_date          ON history_logs     (date);

-- supplier_orders
CREATE INDEX IF NOT EXISTS idx_orders_sku            ON supplier_orders  (sku_id);
CREATE INDEX IF NOT EXISTS idx_orders_supplier       ON supplier_orders  (supplier_id);
CREATE INDEX IF NOT EXISTS idx_orders_status         ON supplier_orders  (status);

-- returns
CREATE INDEX IF NOT EXISTS idx_returns_order         ON returns          (order_id);
CREATE INDEX IF NOT EXISTS idx_returns_status        ON returns          (status);