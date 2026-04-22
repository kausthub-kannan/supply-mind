from typing import TypedDict


class SKUState(TypedDict):
    sku_id: str
    sku_name: str
    current_date: str
    current_stock_quantity: int
    region: str
    forecast_result: dict | None
    anomaly_result: dict | None
    supplier_analysis_result: dict | None
