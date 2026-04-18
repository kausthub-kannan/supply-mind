import json
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from typing import List
import random
from datetime import datetime, timedelta


class ForecastSchema(BaseModel):
    sku_ids: str = Field(
        description="The unique SKU identifier to generate the forecast for."
    )
    days: int = Field(
        default=30, description="Number of days to forecast into the future."
    )


@tool(args_schema=ForecastSchema)
def forecast_orders(sku_ids: List[str], days: int = 30) -> str:
    """
    Forecast orders for given SKU based on historical data
    :param sku_ids: list - List of sku ids predictions need to be performed on
    :param days: int - number of days for prediction window
    :return: str - JSON string of the forecasted output which contains LIST OF forecast demands for every day and reorder for all skus
    """
    output = []
    for sku_id in sku_ids:
        output.append(generate_forecast(sku_id, days))

    return json.dumps(output, indent=2)


def generate_forecast(sku_id: str, days: int = 30, current_stock: int = 150) -> dict:
    """
    Generates a 30-day forecast.
    Calculates expected_delivery_date to be 5-10 days BEFORE the inventory hits the ROP.
    """
    try:
        forecast_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_date = datetime.now() + timedelta(days=1)
        forecast_list = []

        projected_inventory = current_stock
        reorder_point = 100  # To be calculated by ML model
        buffer_days = 5

        low_inventory_date = None
        expected_delivery_date = None

        baseline = random.randint(50, 300)

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            demand = max(
                0, baseline + random.randint(-15, 20)
            )  # ML Predictions for each day
            projected_inventory -= demand

            if projected_inventory <= reorder_point and low_inventory_date is None:
                low_inventory_date = current_date

                # Calculate the delivery date to be 5-10 days PRIOR
                delivery_dt_obj = low_inventory_date - timedelta(days=buffer_days)
                expected_delivery_date = delivery_dt_obj.strftime("%Y-%m-%d")

            forecast_list.append(
                {"date": current_date.strftime("%Y-%m-%d"), "forecasted_demand": demand}
            )

        return {
            "sku_id": sku_id,
            "forecast_generated_at": forecast_date,
            "forecast_horizon_days": days,
            "expected_delivery_date": expected_delivery_date,
            "data": forecast_list,
        }

    except Exception as e:
        return {"error": f"Failed to generate forecast: {str(e)}"}
