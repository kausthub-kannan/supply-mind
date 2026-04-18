import operator
from typing import Annotated
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command, Send
from multi_agents.utils.llm_inference import get_model
from multi_agents.agents.toolkits import tool_maps
from multi_agents.utils.helper import summarizer
import logging
import agentops

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large")


# ---------------------- STATE ---------------------------
@agentops.agent
class InventoryOptimisationState(MessagesState):
    report: str
    current_date: str
    forecast_data: str
    anomaly_detected_data: str
    supervisor_reply_message: str
    human_approval_status: bool
    supplier_analysis_data: str


# ----------------------- NODES ----------------------------
@agentops.operation(name="Initialize Agent Input")
def input_node(state: InventoryOptimisationState):
    number_of_skus = 1
    return [
        Send("forecast_node", state),
        Send("anomaly_detection_node", state),
        Send("supplier_analysis_node", state),
    ] * number_of_skus


@agentops.tool(name="Forecast Inventory Stocks")
def forecast_node(state: InventoryOptimisationState) -> Command:
    return Command(goto="report_generation_node", update={"forecast_data": ""})


@agentops.tool(name="Supplier Analysis")
def supplier_analysis_node(state: InventoryOptimisationState) -> Command:
    return Command(goto="report_generation_node", update={"supplier_analysis_data": ""})


@agentops.tool(name="Detect Anomaly Inventory Stocks")
def anomaly_detection_node(state: InventoryOptimisationState):
    return Command(goto="report_generation_node", update={"anomaly_detected_data": ""})


@agentops.operation(name="Report Generation")
def report_generation_node(state: InventoryOptimisationState):
    return Command(goto="reorder_assessment_node", update={"report": ""})


@agentops.operation(name="Reorder Assessment")
def reorder_assessment_node(state: InventoryOptimisationState):
    return Command(goto="db_status_update_node", update={"report": ""})


@agentops.operation(name="DB Chnages - Reorder SKUs")
def db_status_update_node(state: InventoryOptimisationState):
    return Command(goto="supervisor_communication", update={"messages": []})


@agentops.operation(name="Supervisor Communication")
def supervisor_communication(state: InventoryOptimisationState):
    return Command(goto=END, update={"messages": []})


# ----------------------- GRAPH BUILDER ----------------------------
inventory_optimization_agent_builder = StateGraph(InventoryOptimisationState)

inventory_optimization_agent_builder.add_node("input_node", input_node)
inventory_optimization_agent_builder.add_node("forecast_node", forecast_node)
inventory_optimization_agent_builder.add_node(
    "anomaly_detection_node", anomaly_detection_node
)
inventory_optimization_agent_builder.add_node(
    "supplier_analysis_node", supplier_analysis_node
)
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
    inventory_optimization_agent_builder.compile().with_config({"recursion_limit": 5})
)

if __name__ == "__main__":
    # agentops.init()
    pass
