from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command

from multi_agents.agents.toolkits import order_and_return_agent_toolkit, tool_maps
from multi_agents.prompts.order_and_returns import system_prompt, user_prompt
from multi_agents.utils.llm_inference import get_model
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------- STATE ---------------------------
class EmailAgentState(MessagesState):
    workflow_id: str
    instruction_message: str
    agent_data: str
    output_data: str


# ---------------------- MODEL ---------------------------
model = get_model("mistral-large", tools=order_and_return_agent_toolkit)


# ----------------------- NODES ----------------------------
def input_node(state: EmailAgentState):
    """Bootstrap: inject the initial HumanMessage if the thread is empty."""
    if state.get("messages"):
        return {}

    return Command(
        goto="model_call_node",
        update={
            "messages": [
                HumanMessage(
                    content=user_prompt.format(
                        instruction_message=state["instruction_message"],
                        agent_data=state["agent_data"],
                    )
                )
            ]
        },
    )


def model_call_node(state: EmailAgentState) -> Command:
    """ReAct reasoning step — either calls a tool or decides it's done."""
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    if response.tool_calls:
        logger.info(f"Model decided to call {len(response.tool_calls)} tool(s)")
        return Command(goto="tool_call_node", update={"messages": [response]})
    else:
        logger.info("Model finished — compiling output")
        return Command(
            goto=END,
            update={
                "messages": [response],
                "output_data": response.content,
            },
        )


def tool_call_node(state: EmailAgentState) -> Command:
    """Execute every tool call the model requested, return ToolMessages."""
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    new_tool_messages = []

    logger.info(f"Executing {len(tool_calls)} tool call(s)")

    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]
        logger.info(f"Tool: {tool_name} | ID: {tool_id} | Args: {tool_args}")

        tool = tool_maps.get(tool_name)
        if not tool:
            result_content = f"Error: Tool '{tool_name}' not found."
        else:
            tool_result = tool.invoke(tool_args)
            result_content = (
                tool_result if isinstance(tool_result, str) else str(tool_result)
            )

        new_tool_messages.append(
            ToolMessage(content=result_content, tool_call_id=tool_id, name=tool_name)
        )

    return Command(
        goto="model_call_node",
        update={"messages": new_tool_messages},
    )


# ----------------------- GRAPH BUILDER ----------------------------
email_agent_builder = StateGraph(EmailAgentState)

email_agent_builder.add_node("input_node", input_node)
email_agent_builder.add_node("model_call_node", model_call_node)
email_agent_builder.add_node("tool_call_node", tool_call_node)

email_agent_builder.add_edge(START, "input_node")

email_agent = email_agent_builder.compile().with_config({"recursion_limit": 10})


# ----------------------- ENTRYPOINTS ----------------------------
if __name__ == "__main__":
    import json
    reorder_result = email_agent.invoke(
        {
            "workflow_id": "REORDER-001",
            "instruction_message": "Send a fresh reorder email to Supplier XYZ",
            "agent_data": json.dumps(
                {
                    "supplier_email": "kausthubkannan961@gmail.com",
                    "sku": "NVIDIA-RTX-5090",
                    "quantity": 200,
                    "delivery_date": "2026-05-15",
                    "sku_name": "XYZ",
                }
            ),
        }
    )
    print(f"Workflow ID: {reorder_result['workflow_id']}")
    print(f"Output: {reorder_result['output_data']}")
