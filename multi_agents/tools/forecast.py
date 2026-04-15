import json
import random
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from typing import List

class ForecastSchema(BaseModel):
    sku_ids: str = Field(description="The unique SKU identifier to generate the forecast for.")
    days: int = Field(default=30, description="Number of days to forecast into the future.")


@tool(args_schema=ForecastSchema)
def forecast_orders(sku_ids: List[str], days: int = 30) -> str:
    output = []
    for sku_id in sku_ids:
        output.append(generate_forecast(sku_id, days))

    return json.dumps(output, indent=2)


def generate_forecast(sku_id: str, days: int = 30) -> dict:
    """
    Generates a net-demand forecast for a given SKU.
    Returns the data as a JSON string containing dates, expected demand, and confidence intervals.
    """
    try:
        start_date = datetime.now() + timedelta(days=1)
        forecast_list = []

        baseline = random.randint(50, 300)

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            forecast_val = baseline + random.randint(-15, 20)

            forecast_list.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "forecasted_demand": max(0, forecast_val),
                "lower_bound": max(0, forecast_val - int(forecast_val * 0.15)),
                "upper_bound": forecast_val + int(forecast_val * 0.20)
            })

        output_dict = {
            "sku_id": sku_id,
            "forecast_horizon_days": days,
            "data": forecast_list
        }

        return output_dict

    except Exception as e:
        return {"error": f"Failed to generate forecast: {str(e)}"}