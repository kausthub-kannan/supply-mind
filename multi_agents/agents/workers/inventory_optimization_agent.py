import operator
from typing import Annotated
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, Send
from multi_agents.agents.workers.sub_agent.reorder_assessment_agent import (
    reorder_assessment_agent,
)
from multi_agents.agents.workers.sub_agent.report_generator_agent import (
    report_generator_agent,
)
from multi_agents.agents.workers.sub_agent.sku_level_analysis_agent import (
    sku_subgraph,
    SKUState,
)
from multi_agents.utils.db import get_inventory
from multi_agents.utils.file import upload_file
import json
from datetime import datetime
from langchain_core.tools import tool
from multi_agents.utils.logger import setup_logger

logger = setup_logger()


# ──────────────────────────── STATE ─────────────────────────────
class InventoryOptimisationState(MessagesState):
    workflow_id: str
    skus_data: dict
    current_date: str
    report: str
    forecast_data: Annotated[list, operator.add]
    anomaly_detected_data: Annotated[list, operator.add]
    supplier_analysis_data: Annotated[list, operator.add]
    decision_report: str
    sku_order_data: str
    in_hitl: bool


# ──────────────────────────── NODES ─────────────────────────────
def input_node(state: InventoryOptimisationState) -> Command:
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
        for sku in state["skus_data"]
    ]

    return Command(goto=sends)


async def process_sku_node(state: SKUState) -> dict:
    try:
        result = await sku_subgraph.ainvoke(state)
        return {
            "forecast_data": [result["forecast_result"]],
            "anomaly_detected_data": [result["anomaly_result"]],
            "supplier_analysis_data": [result["supplier_analysis_result"]],
        }
    except Exception as e:
        err_msg = f"Failed to process SKU {state.get('sku_id')}: {e}"
        logger.error(err_msg)
        raise err_msg


def report_generation_node(state: InventoryOptimisationState) -> Command:
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

    try:
        result_messages = report_generator_agent.invoke(
            {
                "analysis_raw_data": json.dumps(per_sku_reports),
                "graphs": [],
                "content_cards": [],
                "report": "",
            }
        )
    except Exception as e:
        err_msg = (
            f"Failed to generate report for workflow {state.get('workflow_id')}: {e}"
        )
        logger.error(err_msg)
        raise err_msg

    return Command(
        goto="reorder_assessment_node",
        update={"report": result_messages["report"]},
    )


def reorder_assessment_node(state: InventoryOptimisationState) -> Command:
    result = reorder_assessment_agent.invoke(
        {"report": state["report"], "messages": []}
    )

    decision_report = (
        f"LOGS\n\nPOSITIVE:\n"
        f"{result['positive_points']}\n"
        f"NEGATIVE:\n"
        f"{result['negative_points']}"
    )
    return Command(
        goto=END,
        update={
            "in_hitl": True,
            "decision_report": decision_report,
            "sku_order_data": result["sku_level_data"],
        },
    )


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

inventory_optimization_agent_builder.add_edge(START, "input_node")
inventory_optimization_agent_builder.add_edge("process_sku", "report_generation_node")
inventory_optimization_agent_builder.add_edge(
    "report_generation_node", "reorder_assessment_node"
)
inventory_optimization_agent_builder.add_edge("reorder_assessment_node", END)

inventory_optimization_agent = (
    inventory_optimization_agent_builder.compile().with_config(
        {"recursion_limit": 100, "max_concurrency": 2}
    )
)


@tool
async def run_inventory_optimization_agent(workflow_id: str):
    """
    Sub Agent (wrapped as a tool) which starts inventory optimization which includes generating demand forecast and anomaly report based on realtime news and historical data and to decide if and how much reorder needs to be done
    :param workflow_id: To track the flow
    :return: result of the agent workflow which includes reorder status, sku level data (suppliers and order quantity for each sku)
    """
    try:
        # skus_data = get_inventory()[:1]
        # result = await inventory_optimization_agent.ainvoke(
        #     {
        #         "skus_data": skus_data,
        #         "messages": [],
        #         "current_date": datetime.now().strftime("%Y-%m-%d"),
        #         "forecast_data": [],
        #         "anomaly_detected_data": [],
        #         "supplier_analysis_data": [],
        #         "report": "",
        #         "workflow_id": workflow_id,
        #     }
        # )
        # upload_file(f"{workflow_id}/report.html", result["report"])
        # upload_file(f"{workflow_id}/decision_report.html", result["report"])
        return {
            "result": json.dumps(
                {
                    # "sku_order_data": result["sku_order_data"],
                    "sku_order_data": [
                        {
                            "sku_name": "MB-X870-AM5 (MSI MEG X870E GODLIKE)",
                            "reorder_quantity": 6545,
                            "supplier_name": "D&H Distributing",
                            "reorder_status": "True",
                        }
                    ]
                }
            ),
            # "in_hitl": result["in_hitl"],
            "in_hitl": True,
        }

    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {e}")
        raise e


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(
        run_inventory_optimization_agent.ainvoke({"workflow_id": "ex-id-123"})
    )
    print(result)
