import operator
from typing import Annotated
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from pydantic import BaseModel, Field

from multi_agents.agents.toolkits import order_and_return_agent_toolkit, tool_maps
from multi_agents.prompts.order_and_returns import system_prompt, user_prompt
from multi_agents.utils.llm_inference import get_model
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------- STATE ---------------------------
class EmailAgentInput(BaseModel):
    workflow_id: str = Field(
        description="Unique workflow identifier (e.g., REORDER-001 or RETURNS-042)"
    )
    instruction_message: str = Field(
        description=(
            "Natural language instruction — either 'send a fresh reorder mail to <supplier>' "
            "or 'read mail from <supplier/customer> and respond to the return'"
        )
    )


class EmailAgentOutput(BaseModel):
    summary: str = Field(
        description="Summary of what the agent did (sent/read/replied)"
    )
    emails_sent: list[str] = Field(
        default_factory=list, description="Recipients of emails sent"
    )
    emails_read: list[str] = Field(
        default_factory=list, description="Thread IDs or senders of emails read"
    )


class EmailAgentState(MessagesState):
    input_data: EmailAgentInput
    emails_sent: Annotated[list, operator.add]
    emails_read: Annotated[list, operator.add]
    output_data: EmailAgentOutput


# ---------------------- MODEL ---------------------------
model = get_model("mistral-large", tools=order_and_return_agent_toolkit)


# ----------------------- NODES ----------------------------
def input_node(state: EmailAgentState):
    """Bootstrap: inject the initial HumanMessage if the thread is empty."""
    if state.get("messages"):
        return {}

    req: EmailAgentInput = state["input_data"]
    return Command(
        goto="model_call_node",
        update={
            "messages": [
                HumanMessage(
                    content=user_prompt.format(
                        workflow_id=req.workflow_id,
                        instruction_message=req.instruction_message,
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
                "output_data": EmailAgentOutput(
                    summary=response.content,
                    emails_sent=state.get("emails_sent", []),
                    emails_read=state.get("emails_read", []),
                ),
            },
        )


def tool_call_node(state: EmailAgentState) -> Command:
    """Execute every tool call the model requested, return ToolMessages."""
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    new_tool_messages = []
    emails_sent = []
    emails_read = []

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

            # Track side effects for the output summary
            if tool_name == "send_email":
                recipient = tool_args.get("to", "unknown")
                emails_sent.append(recipient)
                logger.info(f"Email sent to: {recipient}")

            elif tool_name == "read_email":
                thread_ref = tool_args.get("thread_id") or tool_args.get(
                    "sender", "unknown"
                )
                emails_read.append(thread_ref)
                logger.info(f"Email read from thread/sender: {thread_ref}")

        new_tool_messages.append(
            ToolMessage(
                content=result_content,
                tool_call_id=tool_id,
                name=tool_name,
            )
        )

    return Command(
        goto="model_call_node",
        update={
            "messages": new_tool_messages,
            "emails_sent": emails_sent,
            "emails_read": emails_read,
        },
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
    # --- Test 1: Send a fresh reorder mail ---
    reorder_result = email_agent.invoke(
        {
            "input_data": EmailAgentInput(
                workflow_id="REORDER-001",
                instruction_message=(
                    "Send a fresh reorder email to supplier@acme-parts.com "
                    "for 200 units of SKU NVIDIA-RTX-5090, requesting delivery by 2026-05-15."
                ),
            ),
            "emails_sent": [],
            "emails_read": [],
        }
    )
    print("=== REORDER RESULT ===")
    print(reorder_result["output_data"].summary)

    # --- Test 2: Read a return thread and respond ---
    returns_result = email_agent.invoke(
        {
            "input_data": EmailAgentInput(
                workflow_id="RETURNS-042",
                instruction_message=(
                    "Read the return request email from customer john.doe@gmail.com "
                    "(thread ID: RET-2026-042) and send a professional reply confirming "
                    "the return and issuing a refund within 5 business days."
                ),
            ),
            "emails_sent": [],
            "emails_read": [],
        }
    )
    print("=== RETURNS RESULT ===")
    print(returns_result["output_data"].summary)
