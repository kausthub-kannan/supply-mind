import operator
from typing import Annotated
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, Send

from multi_agents.agents.schemas.sku_graph_input import SKUState
from multi_agents.agents.workers.sub_agent.report_generator_agent import (
    report_generator_agent,
)
from multi_agents.agents.workers.sub_agent.sku_level_analysis_agent import sku_subgraph
from multi_agents.utils.db import get_inventory
from multi_agents.utils.file import upload_file
from multi_agents.utils.llm_inference import get_model
import json
import logging
import agentops

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

agentops.init()

# ──────────────────────────── MODELS ────────────────────────────
model = get_model("mistral-large")


# ──────────────────────────── STATE ─────────────────────────────
class InventoryOptimisationState(MessagesState):
    report: str
    current_date: str
    forecast_data: Annotated[list, operator.add]
    anomaly_detected_data: Annotated[list, operator.add]
    supplier_analysis_data: Annotated[list, operator.add]
    workflow_id: str


# ──────────────────────────── NODES ─────────────────────────────
def input_node(state: InventoryOptimisationState) -> Command:
    """Fetches inventory and triggers parallel processing for each SKU."""
    skus_data = get_inventory()[:2]

    sends = [
        Send(
            "process_sku",
            {
                "sku_id": sku["sku_id"],
                "sku_name": sku["sku_name"],
                "current_date": state["current_date"],
                "current_stock_quantity": sku["current_quantity"],
                "region": sku["region"],
            },
        )
        for sku in skus_data
    ]
    # Use Command to perform the dynamic fan-out
    return Command(goto=sends)


async def process_sku_node(state: SKUState) -> dict:
    result = await sku_subgraph.ainvoke(state)
    return {
        "forecast_data": [result["forecast_result"]],
        "anomaly_detected_data": [result["anomaly_result"]],
        "supplier_analysis_data": [result["supplier_analysis_result"]],
    }


def collect_sku_results(state: InventoryOptimisationState):
    """
    Runs once after ALL sku subgraphs finish.
    Lift subgraph outputs into the parent state.
    LangGraph passes subgraph output via parent state reducers automatically
    when the subgraph node is added with `add_node`.
    """
    return {}


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

    upload_file(f"{state["workflow_id"]}/report.html", result_messages["report"])

    return Command(
        goto="reorder_assessment_node",
        update={"report": result_messages["report"]},
    )


def reorder_assessment_node(state: InventoryOptimisationState) -> Command:
    return Command(goto="db_status_update_node")


def db_status_update_node(state: InventoryOptimisationState) -> Command:
    return Command(goto="supervisor_communication")


def supervisor_communication(state: InventoryOptimisationState) -> Command:
    return Command(goto=END)


# ──────────────────────────── GRAPH ─────────────────────────────
inventory_optimization_agent_builder = StateGraph(InventoryOptimisationState)

inventory_optimization_agent_builder.add_node("input_node", input_node)
inventory_optimization_agent_builder.add_node("process_sku", process_sku_node)
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
inventory_optimization_agent_builder.add_edge("process_sku", "report_generation_node")
inventory_optimization_agent_builder.add_edge(
    "report_generation_node", "reorder_assessment_node"
)
inventory_optimization_agent_builder.add_edge(
    "reorder_assessment_node", "db_status_update_node"
)
inventory_optimization_agent_builder.add_edge(
    "db_status_update_node", "supervisor_communication"
)
inventory_optimization_agent_builder.add_edge("supervisor_communication", END)

inventory_optimization_agent = (
    inventory_optimization_agent_builder.compile().with_config(
        {"recursion_limit": 100, "max_concurrency": 2}
    )
)


async def main():
    from datetime import datetime
    import uuid

    trace = agentops.start_trace("inventory-optimization-agent")
    result = await inventory_optimization_agent.ainvoke(
        {
            "messages": [],
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "forecast_data": [],
            "anomaly_detected_data": [],
            "supplier_analysis_data": [],
            "report": "",
            "workflow_id": str(uuid.uuid4()),
        }
    )
    agentops.end_trace(trace, "Success")
    print(f"FINAL REPORT:\n{result['report']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
