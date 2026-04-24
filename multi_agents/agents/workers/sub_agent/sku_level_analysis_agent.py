import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from multi_agents.agents.toolkits import tool_maps
from multi_agents.agents.workers.sub_agent.supplier_analysis_agent import (
    supplier_analysis_agent,
    SupplierAnalysisInput,
)
from multi_agents.utils.db import get_suppliers_for_sku
import json

DEFAULT_FORECAST_DAYS = 30


class SKUState(TypedDict):
    sku_id: str
    sku_name: str
    current_date: str
    current_stock_quantity: int
    region: str
    forecast_result: dict | None
    anomaly_result: dict | None
    supplier_analysis_result: dict | None


async def sku_forecast_node(state: SKUState):
    tool_output = await tool_maps["forecast_orders"].ainvoke(
        {
            "sku_id": state["sku_id"],
            "days": DEFAULT_FORECAST_DAYS,
        }
    )
    forecast = tool_output.content if hasattr(tool_output, "content") else tool_output
    return {"forecast_result": {"sku_id": state["sku_id"], "forecast": forecast}}


async def sku_anomaly_node(state: SKUState):
    tool_output = await tool_maps["anomaly_detection"].ainvoke(
        {
            "sku_id": state["sku_id"],
            "lookback_days": DEFAULT_FORECAST_DAYS,
        }
    )
    anomaly = tool_output.content if hasattr(tool_output, "content") else tool_output
    return {"anomaly_result": {"sku_id": state["sku_id"], "anomaly": anomaly}}


async def sku_parallel_node(state: SKUState):
    """Run forecast + anomaly concurrently, no fan-out needed."""
    forecast_task = tool_maps["forecast_orders"].ainvoke(
        {
            "sku_id": state["sku_id"],
            "days": DEFAULT_FORECAST_DAYS,
        }
    )
    anomaly_task = tool_maps["anomaly_detection"].ainvoke(
        {
            "sku_id": state["sku_id"],
            "lookback_days": DEFAULT_FORECAST_DAYS,
        }
    )
    forecast_out, anomaly_out = await asyncio.gather(forecast_task, anomaly_task)

    return {
        "forecast_result": {
            "sku_id": state["sku_id"],
            "forecast": (
                forecast_out.content
                if hasattr(forecast_out, "content")
                else forecast_out
            ),
        },
        "anomaly_result": {
            "sku_id": state["sku_id"],
            "anomaly": (
                anomaly_out.content if hasattr(anomaly_out, "content") else anomaly_out
            ),
        },
    }


async def sku_supplier_node(state: SKUState):
    forecast = json.loads(state["forecast_result"]["forecast"])
    suppliers = [
        s["supplier_name"] for s in get_suppliers_for_sku(state["sku_id"].lower())
    ]

    result = await supplier_analysis_agent.ainvoke(
        {
            "input_data": SupplierAnalysisInput(
                sku_name=state["sku_name"],
                order_quantity=forecast["order_quantity"],
                delivery_date=forecast["delivery_date"],
                suppliers_list=suppliers,
            ),
            "urls": [],
        }
    )
    return {
        "supplier_analysis_result": {
            "sku_id": state["sku_id"],
            "analysis": result["output_data"].analysis,
            "urls": result["output_data"].urls,
        }
    }


sku_subgraph_builder = StateGraph(SKUState)
sku_subgraph_builder.add_node("parallel_node", sku_parallel_node)
sku_subgraph_builder.add_node("supplier_node", sku_supplier_node)

sku_subgraph_builder.add_edge(START, "parallel_node")
sku_subgraph_builder.add_edge("parallel_node", "supplier_node")
sku_subgraph_builder.add_edge("supplier_node", END)

sku_subgraph = sku_subgraph_builder.compile()
