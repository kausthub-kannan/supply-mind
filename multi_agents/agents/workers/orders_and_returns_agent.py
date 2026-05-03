from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from datetime import datetime
from langchain_core.tools import tool
from multi_agents.agents.toolkits import order_and_return_agent_toolkit, tool_maps
from multi_agents.prompts.order_and_returns import system_prompt, user_prompt
from multi_agents.utils.llm_inference import get_model
from multi_agents.utils.logger import setup_logger
import json

logger = setup_logger()


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

            if tool_name == "read_email":
                from multi_agents.guardrails.input.email_guard import (
                    email_injection_guardrail,
                )

                result_content = email_injection_guardrail(result_content)

        new_tool_messages.append(
            ToolMessage(content=result_content, tool_call_id=tool_id, name=tool_name)
        )

    return Command(
        goto="model_call_node",
        update={"messages": new_tool_messages},
    )


# ----------------------- GRAPH BUILDER ----------------------------
orders_and_returns_agent_builder = StateGraph(EmailAgentState)

orders_and_returns_agent_builder.add_node("input_node", input_node)
orders_and_returns_agent_builder.add_node("model_call_node", model_call_node)
orders_and_returns_agent_builder.add_node("tool_call_node", tool_call_node)

orders_and_returns_agent_builder.add_edge(START, "input_node")

orders_and_returns_agent = orders_and_returns_agent_builder.compile().with_config(
    {"recursion_limit": 50}
)


@tool
async def run_orders_and_returns_agent(
    workflow_id: str,
    instruction_message: str,
    agent_data: str,
    in_hitl: bool = False,
):
    """
    Sub Agent (wrapped as a tool) which processes order and return requests
    including analyzing customer instructions, accessing order/return data,
    and generating appropriate responses or actions.

    :param workflow_id: To track the flow
    :param instruction_message: The customer instruction or query (e.g., "I want to return order #123")
    :param agent_data: Relevant data context (e.g., order details, customer info, return policy)
    :param in_hitl: Whether to flag for human-in-the-loop review
    :return: result of the agent workflow which includes output_data and hitl status
    """
    try:
        logger.info(f"Starting orders and returns agent for workflow {workflow_id}")

        # Invoke the agent with the required state
        result = await orders_and_returns_agent.ainvoke(
            {
                "workflow_id": workflow_id,
                "instruction_message": instruction_message,
                "agent_data": agent_data,
                "messages": [],
                "output_data": "",
            }
        )

        output_content = ""
        for message in reversed(result.get("messages", [])):
            if hasattr(message, "content") and isinstance(message.content, str):
                output_content = message.content
                break

        final_output = result.get("output_data") or output_content
        logger.info(f"Agent completed for workflow {workflow_id}")

        return {
            "result": json.dumps(
                {
                    "output_data": final_output,
                    "workflow_id": workflow_id,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            "in_hitl": in_hitl,
        }

    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {e}", exc_info=True)
        raise e
