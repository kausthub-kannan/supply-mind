COPY suppliers FROM '/data/suppliers.csv' WITH (FORMAT csv, HEADER true);
COPY inventory FROM '/data/inventory.csv' WITH (FORMAT csv, HEADER true);
--COPY customer_orders FROM '/data/customer_orders.csv' WITH (FORMAT csv, HEADER true);
COPY history_logs FROM '/data/history_logs.csv' WITH (FORMAT csv, HEADER true);
--COPY returns FROM '/data/returns.csv' WITH (FORMAT csv, HEADER true);
--COPY supplier_orders FROM '/data/supplier_orders.csv' WITH (FORMAT csv, HEADER true);
COPY supplier_sku_map FROM '/data/supplier_sku_map.csv' WITH (FORMAT csv, HEADER true);