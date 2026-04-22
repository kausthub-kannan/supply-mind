import operator
from typing import Annotated
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from multi_agents.agents.prompts.report_generation import system_prompt, user_prompt
from multi_agents.utils.llm_inference import get_model
from multi_agents.agents.toolkits import report_generation_toolkit, tool_maps
import logging
import agentops

logger = logging.getLogger()
logger.setLevel(logging.INFO)

agentops.init()

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large", tools=report_generation_toolkit)


# ---------------------- STATE ---------------------------
@agentops.agent
class ReportGeneratorState(MessagesState):
    analysis_raw_data: str
    graphs: Annotated[list, operator.add]
    content_cards: Annotated[list, operator.add]
    table_cards: Annotated[list, operator.add]
    report: str


# ----------------------- NODES ----------------------------
@agentops.task(name="Initialize Input")
def input_node(state: ReportGeneratorState):
    if state.get("messages"):
        return Command(goto="model_call_node")

    return Command(
        goto="model_call_node",
        update={
            "messages": [
                HumanMessage(
                    content=user_prompt.format(
                        analysis_raw_data=state["analysis_raw_data"],
                    )
                )
            ]
        },
    )


@agentops.operation(name="Model Inference")
def model_call_node(state: ReportGeneratorState) -> Command:
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    if response.tool_calls:
        return Command(goto="tool_call_node", update={"messages": [response]})
    else:
        return Command(
            goto=END, update={"messages": [response], "report": response.content}
        )


@agentops.tool(name="Report Generation Tool Execution")
def tool_call_node(state: ReportGeneratorState):
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    new_tool_messages = []
    tool_results = {"graphs": [], "content_cards": []}

    logger.info(f"Number of tool calls will be done: {len(tool_calls)}")
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]
        logger.info(f"Executing tool: {tool_name} with ID: {tool_id}")

        tool = tool_maps.get(tool_name)
        if not tool:
            tool_result = f"Error: Tool {tool_name} not found."
        else:
            tool_result = tool.invoke(tool_args)

        if "chart" in tool_name or "plot" in tool_name:
            tool_results["graphs"].append(tool_result)
        else:
            tool_results["content_cards"].append(tool_result)

        new_tool_messages.append(
            ToolMessage(
                content=tool_result,
                tool_call_id=tool_id,
                name=tool_name,
            )
        )

    return Command(
        goto="model_call_node",
        update={"messages": new_tool_messages, **tool_results},
    )


# ----------------------- GRAPH BUILDER ----------------------------
report_generator_agent_builder = StateGraph(ReportGeneratorState)
report_generator_agent_builder.add_node("input_node", input_node)
report_generator_agent_builder.add_node("model_call_node", model_call_node)
report_generator_agent_builder.add_node("tool_call_node", tool_call_node)

report_generator_agent_builder.add_edge(START, "input_node")
report_generator_agent = report_generator_agent_builder.compile().with_config(
    {"recursion_limit": 25}
)


if __name__ == "__main__":
    data_dump = '{"current_date": "2026-04-22", "total_sku_count": 1, "human_approval_status": false, "supervisor_reply_message": "", "forecast_data": [{"sku_id": "MB-X870-AM5", "forecast": {"sku_id": "MB-X870-AM5", "forecast_generated_at": "2026-04-22 17:54:47", "forecast_horizon_days": 30, "delivery_date": "2026-04-18", "data": [{"date": "2026-04-23", "forecasted_demand": 223}, {"date": "2026-04-24", "forecasted_demand": 214}, {"date": "2026-04-25", "forecasted_demand": 202}, {"date": "2026-04-26", "forecasted_demand": 224}, {"date": "2026-04-27", "forecasted_demand": 227}, {"date": "2026-04-28", "forecasted_demand": 217}, {"date": "2026-04-29", "forecasted_demand": 212}, {"date": "2026-04-30", "forecasted_demand": 212}, {"date": "2026-05-01", "forecasted_demand": 213}, {"date": "2026-05-02", "forecasted_demand": 224}, {"date": "2026-05-03", "forecasted_demand": 219}, {"date": "2026-05-04", "forecasted_demand": 217}, {"date": "2026-05-05", "forecasted_demand": 197}, {"date": "2026-05-06", "forecasted_demand": 220}, {"date": "2026-05-07", "forecasted_demand": 198}, {"date": "2026-05-08", "forecasted_demand": 199}, {"date": "2026-05-09", "forecasted_demand": 226}, {"date": "2026-05-10", "forecasted_demand": 223}, {"date": "2026-05-11", "forecasted_demand": 197}, {"date": "2026-05-12", "forecasted_demand": 225}, {"date": "2026-05-13", "forecasted_demand": 205}, {"date": "2026-05-14", "forecasted_demand": 209}, {"date": "2026-05-15", "forecasted_demand": 220}, {"date": "2026-05-16", "forecasted_demand": 229}, {"date": "2026-05-17", "forecasted_demand": 210}, {"date": "2026-05-18", "forecasted_demand": 229}, {"date": "2026-05-19", "forecasted_demand": 220}, {"date": "2026-05-20", "forecasted_demand": 227}, {"date": "2026-05-21", "forecasted_demand": 217}, {"date": "2026-05-22", "forecasted_demand": 212}], "order_quantity": 6467}}], "anomaly_detected_data": [{"sku_id": "MB-X870-AM5", "anomaly": "..."}], "supplier_analysis_data": [{"sku_id": "MB-X870-AM5", "analysis": "### SKU: MSI MEG X870E GODLIKE (AMD) | Recommended Supplier: D&H Distributing\\n\\n**Selection Rationale**\\n\\nD&H Distributing emerges as the preferred supplier for the MSI MEG X870E GODLIKE due to its proven operational scale, North American logistics infrastructure, and financial stability. D&H\\u2019s $5.5B+ annual revenue (FY24) and 106-year track record demonstrate resilience in high-volume IT hardware distribution.\\n\\n**Why Other Candidates Were Not Selected**\\n\\nASI Corp: Operational and ethical risks disqualify it for high-stakes procurement. Documented failures include unfulfilled in-stock orders and channel policy violations.\\n\\n**Risk Assessment & Mitigation**\\n\\n1. Operational Variability: Potential inconsistencies in order processing.\\n2. Certification Gaps: No publicly verified ISO 9001 identified.\\n3. Geographic Concentration: Primary hubs in PA and FL introduce regional risk.\\n\\n**Recommended Mitigations**\\n\\n- Contractual SLAs: Secure written guarantees for lead times.\\n- Dual Sourcing: Qualify a secondary supplier for 20\\u201330% of volume.\\n- Compliance Audit: Request third-party certification documentation.\\n- Inventory Buffer: Allocate 10% contingency stock."}]}'
    result_messages = report_generator_agent.invoke(
        {
            "analysis_raw_data": data_dump,
            "graphs": [],
            "content_cards": [],
            "report": "",
        }
    )

    print(result_messages["report"])
