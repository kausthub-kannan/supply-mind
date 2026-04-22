from sqlalchemy import Table, MetaData, select, create_engine, join
import os
import urllib.parse
import json

user = os.getenv("POSTGRES_USER")
password = urllib.parse.quote_plus(os.getenv("POSTGRES_PASSWORD"))
db_name = os.getenv("POSTGRES_DB")
port = os.getenv("POSTGRES_PORT")
host = os.getenv("POSTGRES_HOST", "localhost")
db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


def get_inventory():
    engine = create_engine(db_url)
    metadata = MetaData()
    inventory_table = Table("inventory", metadata, autoload_with=engine)

    with engine.connect() as connection:
        stmt = select(inventory_table).distinct(
            inventory_table.c.sku_id, inventory_table.c.region
        )
        result = connection.execute(stmt)
        rows_as_dicts = [row._asdict() for row in result]

        return rows_as_dicts


def get_suppliers_for_sku(sku_id: str):
    engine = create_engine(db_url)
    metadata = MetaData()

    map_table = Table("supplier_sku_map", metadata, autoload_with=engine)
    suppliers_table = Table("suppliers", metadata, autoload_with=engine)
    j = join(
        map_table,
        suppliers_table,
        map_table.c.supplier_id == suppliers_table.c.supplier_id,
    )

    try:
        with engine.connect() as connection:
            stmt = (
                select(suppliers_table)
                .select_from(j)
                .where(map_table.c.sku_id == sku_id)
            )

            result = connection.execute(stmt)
            supplier_details = [row._asdict() for row in result]

            return supplier_details

    except Exception as e:
        print(f"Error fetching detailed suppliers for SKU {sku_id}: {e}")
        return []


if __name__ == "__main__":
    print(get_suppliers_for_sku("gpu-nv-rtx5090"))
