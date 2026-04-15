-- dml.sql
COPY suppliers FROM '/data/suppliers.csv' WITH (FORMAT csv, HEADER true);
COPY inventory FROM '/data/inventory.csv' WITH (FORMAT csv, HEADER true);