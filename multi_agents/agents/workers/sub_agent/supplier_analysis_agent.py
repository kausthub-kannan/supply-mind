import operator
from typing import Annotated
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from multi_agents.agents.prompts.supplier_analysis import (
    system_prompt,
    summarizer_prompt,
    user_prompt,
)
from multi_agents.agents.schemas.supplier_request_input import SupplierRequestInputs
from multi_agents.utils.llm_inference import get_model
from multi_agents.agents.toolkits import supplier_analysis_agent_toolkit, tool_maps
from multi_agents.utils.helper import summarizer
import agentops
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

agentops.init(default_tags=['supplier_analysis'])

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large", tools=supplier_analysis_agent_toolkit)


# ---------------------- STATE ---------------------------
class SearchState(MessagesState):
    input_data: SupplierRequestInputs
    urls: Annotated[list, operator.add]


# ----------------------- NODES ----------------------------
def input_node(state: SearchState):
    if state.get("messages"):
        return {}

    req: SupplierRequestInputs = state["input_data"]

    return Command(
        goto="model_call_node",
        update={
            "messages": [
                HumanMessage(
                    content=user_prompt.format(
                        sku_name=req.sku_name,
                        order_quantity=req.order_quantity,
                        delivery_date=req.delivery_date,
                        suppliers_list=",".join(req.suppliers_list),
                    )
                )
            ]
        },
    )


def model_call_node(state: SearchState) -> Command:
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    if response.tool_calls:
        return Command(goto="tool_call_node", update={"messages": [response]})
    else:
        return Command(goto=END, update={"messages": [response]})


def tool_call_node(state: SearchState):
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    new_tool_messages = []
    all_extracted_urls = []

    logger.info(f"Number of tool calls will be done: {len(tool_calls)}")
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]
        logger.info(f"Executing tool: {tool_name} with ID: {tool_id}")

        tool = tool_maps.get(tool_name)
        if not tool:
            final_content = f"Error: Tool {tool_name} not found."
        else:
            tool_result = tool.invoke(tool_args)
            current_urls = [
                item.get("url", "") for item in tool_result if "url" in item
            ]
            all_extracted_urls.extend(current_urls)
            final_content = [item.get("content", "") for item in tool_result]

        new_tool_messages.append(
            ToolMessage(
                content=summarizer(
                    system_prompt=summarizer_prompt, content="\n\n".join(final_content)
                ),
                tool_call_id=tool_id,
                name=tool_name,
            )
        )

    return Command(
        goto="model_call_node",
        update={"messages": new_tool_messages, "urls": all_extracted_urls},
    )


# ----------------------- GRAPH BUILDER ----------------------------
supplier_analysis_agent_builder = StateGraph(SearchState)
supplier_analysis_agent_builder.add_node("input_node", input_node)
supplier_analysis_agent_builder.add_node("model_call_node", model_call_node)
supplier_analysis_agent_builder.add_node("tool_call_node", tool_call_node)

supplier_analysis_agent_builder.add_edge(START, "input_node")
supplier_analysis_agent = supplier_analysis_agent_builder.compile()

if __name__ == "__main__":
    result_messages = supplier_analysis_agent.invoke(
        {
            "input_data": SupplierRequestInputs(
                sku_name="NVIDIA RTX 5090 32GB (ASUS/MSI)",
                order_quantity=100,
                delivery_date="22-04-2026",
                suppliers_list=["Central Computers (CA)", "Newegg Commerce (CA)"],
            ),
            "urls": [],
        },
        config={"recursion_limit": 10},
    )

    result_messages["messages"][-1].pretty_print()
