import operator
from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, Send

from multi_agents.agents.schemas.supplier_request_input import SupplierRequestInputs
from multi_agents.agents.toolkits import tool_maps
from multi_agents.agents.workers.sub_agent.report_generator_agent import report_generator_agent
from multi_agents.agents.workers.sub_agent.supplier_analysis_agent import (
    supplier_analysis_agent,
)
from multi_agents.utils.db import get_inventory, get_suppliers_for_sku
from multi_agents.utils.llm_inference import get_model
import json
import logging
import agentops

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_FORECAST_DAYS = 30

# ──────────────────────────── MODELS ────────────────────────────
model = get_model("mistral-large")


# ──────────────────────────── STATE ─────────────────────────────
@agentops.agent
class InventoryOptimisationState(MessagesState):
    report: str
    current_date: str
    total_sku_count: int  # ← NEW: set once in input_node
    forecast_data: Annotated[list, operator.add]
    anomaly_detected_data: Annotated[list, operator.add]
    supervisor_reply_message: str
    human_approval_status: bool
    supplier_analysis_data: Annotated[list, operator.add]


class SKUState(TypedDict):
    sku_id: str
    sku_name: str
    current_date: str
    current_stock_quantity: int
    region: str
    forecast_data: Annotated[list, operator.add]
    anomaly_detected_data: Annotated[list, operator.add]
    supplier_analysis_data: Annotated[list, operator.add]
    total_sku_count: int


# ──────────────────────────── NODES ─────────────────────────────


@agentops.operation(name="Initialize Agent Input")
def input_node(state: InventoryOptimisationState):
    skus_data = get_inventory()[:1]
    total = len(skus_data)
    sends = []
    for sku_data in skus_data:
        payload = {
            "sku_id": sku_data["sku_id"],
            "sku_name": sku_data["sku_name"],
            "current_date": state["current_date"],
            "current_stock_quantity": sku_data["current_quantity"],
            "region": sku_data["region"],
            "total_sku_count": total,
        }
        sends.append(Send("forecast_node", payload))
        sends.append(Send("anomaly_detection_node", payload))

    return Command(
        goto=sends,
        update={"total_sku_count": total},
    )


@agentops.tool(name="Forecast Inventory Stocks")
def forecast_node(state: SKUState) -> Command:
    sku_id = state["sku_id"]

    tool_output = tool_maps["forecast_orders"].invoke(
        {
            "sku_id": sku_id,
            "days": DEFAULT_FORECAST_DAYS,
        }
    )
    forecast_result = (
        tool_output.content if hasattr(tool_output, "content") else tool_output
    )

    return Command(
        goto=Send(
            "supplier_analysis_node",
            {
                **state,
                "forecast_data": [{"sku_id": sku_id, "forecast": forecast_result}],
            },
        ),
        update={"forecast_data": [{"sku_id": sku_id, "forecast": forecast_result}]},
    )


@agentops.tool(name="Detect Anomaly Inventory Stocks")
def anomaly_detection_node(state: SKUState) -> Command:
    """Detect anomalies for one SKU and forward to the barrier node."""
    sku_id = state["sku_id"]

    anomaly_result = {"sku_id": sku_id, "anomaly": "..."}

    return Command(
        goto="join_node",
        update={"anomaly_detected_data": [anomaly_result]},
    )


@agentops.tool(name="Supplier Analysis")
def supplier_analysis_node(state: SKUState) -> Command:
    sku_id = state["sku_id"]

    forecast_entry = next(
        (d for d in state.get("forecast_data", []) if d["sku_id"] == sku_id),
        None,
    )
    if forecast_entry is None:
        logger.warning(
            "No forecast data for sku_id=%s; skipping supplier analysis.", sku_id
        )
        return Command(
            goto="join_node",
            update={"supplier_analysis_data": [{"sku_id": sku_id, "analysis": None}]},
        )

    forecast = json.loads(forecast_entry["forecast"])
    order_quantity = forecast["order_quantity"]
    delivery_date = forecast["delivery_date"]

    suppliers_list = [s["supplier_name"] for s in get_suppliers_for_sku(sku_id.lower())]

    result_messages = supplier_analysis_agent.invoke(
        {
            "input_data": SupplierRequestInputs(
                sku_name=state["sku_name"],
                order_quantity=order_quantity,
                delivery_date=delivery_date,
                suppliers_list=suppliers_list,
            ),
            "urls": [],
        }
    )

    return Command(
        goto="join_node",
        update={
            "supplier_analysis_data": [
                {"sku_id": sku_id, "analysis": result_messages["messages"][-1].content}
            ]
        },
    )


# ──────────────────────────── BARRIER / JOIN NODE ───────────────


@agentops.operation(name="Join Barrier")
def join_node(state: InventoryOptimisationState) -> Command:
    """
    Fan-in barrier. Each SKU contributes:
      - 1 anomaly result  (from anomaly_detection_node)
      - 1 supplier result (from supplier_analysis_node, after forecast)

    We only proceed to report_generation_node once ALL SKUs have
    delivered both results.
    """
    total = state.get("total_sku_count", 0)
    anomaly_count = len(state.get("anomaly_detected_data", []))
    supplier_count = len(state.get("supplier_analysis_data", []))

    logger.info(
        "join_node: total_skus=%d  anomalies=%d  supplier_analyses=%d",
        total,
        anomaly_count,
        supplier_count,
    )

    if anomaly_count >= total and supplier_count >= total:
        logger.info("All SKUs processed, moving to report generation")
        return Command(goto="report_generation_node")
    else:
        # Still waiting for more results — stay idle (return empty update)
        return Command(
            goto=END if total == 0 else []
        )  # no-op; LangGraph will re-invoke when more updates arrive


# ──────────────────────────── DOWNSTREAM NODES ──────────────────


@agentops.operation(name="Report Generation")
def report_generation_node(state: InventoryOptimisationState) -> Command:
    """Merge forecast, anomaly, and supplier data into a per-SKU report."""
    logger.info("Entered report generation")
    forecast_by_sku = {d["sku_id"]: d for d in state.get("forecast_data", [])}
    anomaly_by_sku = {d["sku_id"]: d for d in state.get("anomaly_detected_data", [])}
    supplier_by_sku = {d["sku_id"]: d for d in state.get("supplier_analysis_data", [])}

    all_sku_ids = set(forecast_by_sku) | set(anomaly_by_sku) | set(supplier_by_sku)
    per_sku_reports = [
        {
            "sku_id": sku_id,
            "forecast": forecast_by_sku.get(sku_id),
            "anomaly": anomaly_by_sku.get(sku_id),
            "supplier": supplier_by_sku.get(sku_id),
        }
        for sku_id in all_sku_ids
    ]

    result_messages = report_generator_agent.invoke(
        {
            "analysis_raw_data": json.dumps(per_sku_reports),
            "graphs": [],
            "content_cards": [],
            "report": "",
        }
    )

    return Command(
        goto="reorder_assessment_node",
        update={"report": result_messages["report"]},
    )


@agentops.operation(name="Reorder Assessment")
def reorder_assessment_node(state: InventoryOptimisationState) -> Command:
    return Command(goto="db_status_update_node")


@agentops.operation(name="DB Changes - Reorder SKUs")
def db_status_update_node(state: InventoryOptimisationState) -> Command:
    return Command(goto="supervisor_communication")


@agentops.operation(name="Supervisor Communication")
def supervisor_communication(state: InventoryOptimisationState) -> Command:
    return Command(goto=END)


# ──────────────────────────── GRAPH ─────────────────────────────
inventory_optimization_agent_builder = StateGraph(InventoryOptimisationState)

inventory_optimization_agent_builder.add_node("input_node", input_node)
inventory_optimization_agent_builder.add_node("forecast_node", forecast_node)
inventory_optimization_agent_builder.add_node(
    "anomaly_detection_node", anomaly_detection_node
)
inventory_optimization_agent_builder.add_node(
    "supplier_analysis_node", supplier_analysis_node
)
inventory_optimization_agent_builder.add_node("join_node", join_node)  # ← NEW
inventory_optimization_agent_builder.add_node(
    "report_generation_node", report_generation_node
)
inventory_optimization_agent_builder.add_node(
    "reorder_assessment_node", reorder_assessment_node
)
inventory_optimization_agent_builder.add_node(
    "db_status_update_node", db_status_update_node
)
inventory_optimization_agent_builder.add_node(
    "supervisor_communication", supervisor_communication
)

inventory_optimization_agent_builder.add_edge(START, "input_node")

inventory_optimization_agent = (
    inventory_optimization_agent_builder.compile().with_config(
        {"recursion_limit": 100, "max_concurrency": 2}
    )
)


if __name__ == "__main__":
    from datetime import datetime

    agentops.init()
    result = inventory_optimization_agent.invoke(
        {
            "messages": [],
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "total_sku_count": 0,
            "forecast_data": [],
            "anomaly_detected_data": [],
            "supplier_analysis_data": [],
            "report": "",
            "supervisor_reply_message": "",
            "human_approval_status": False,
        }
    )
    print(result["report"])
