from sqlalchemy import Table, MetaData, select, create_engine, join, update
import os
import urllib.parse
from sqlalchemy import insert
from datetime import datetime, timezone

from multi_agents.utils.logger import setup_logger

logger = setup_logger()
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
        logger.info(f"Error fetching detailed suppliers for SKU {sku_id}: {e}")
        return []


def add_workflow(workflow_id, notification_message, input_data):
    engine = create_engine(db_url)
    metadata = MetaData()
    workflows_table = Table("workflows", metadata, autoload_with=engine)
    workflow_type = notification_message
    created_at = datetime.now(timezone.utc)
    workflow_status = "in-progress"
    with engine.connect() as connection:
        stmt = insert(workflows_table).values(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            input_data=input_data,
            created_at=created_at,
            workflow_status=workflow_status,
        )

        connection.execute(stmt)
        connection.commit()


def update_workflow(workflow_id, status):
    engine = create_engine(db_url)
    metadata = MetaData()
    workflows_table = Table("workflows", metadata, autoload_with=engine)

    with engine.connect() as connection:
        stmt = (
            update(workflows_table)
            .where(workflows_table.c.workflow_id == workflow_id)
            .values(workflow_status=status)
        )

        result = connection.execute(stmt)
        connection.commit()
        return result.rowcount
