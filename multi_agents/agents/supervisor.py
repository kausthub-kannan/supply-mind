import operator
from typing import Annotated, List, TypedDict  # Fixed import

from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command, interrupt
from psycopg_pool import AsyncConnectionPool

from multi_agents.agents.workers.inventory_optimization_agent import (
    run_inventory_optimization_agent,
)
from multi_agents.prompts.supervisor import user_prompt, system_prompt
from multi_agents.utils.db import db_url
from multi_agents.utils.llm_inference import get_model
from multi_agents.utils.logger import setup_logger
import psycopg

logger = setup_logger()

supervisor_workers = [run_inventory_optimization_agent]
worker_maps = {"run_inventory_optimization_agent": run_inventory_optimization_agent}

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large", tools=supervisor_workers)

# ---------------------- CHECKPOINTER ---------------------------
with psycopg.connect(db_url, autocommit=True) as conn:
    PostgresSaver(conn).setup()


# ---------------------- STATE ---------------------------
class SupervisorState(MessagesState):
    workflow_id: str
    notification_message: str
    in_hitl: bool
    feedback: Annotated[List[str], operator.add]


# ----------------------- NODES ----------------------------
def input_node(state: SupervisorState):
    if state.get("messages"):
        return Command(goto="model_call_node")

    return Command(
        goto="model_call_node",
        update={
            "messages": [
                HumanMessage(
                    content=user_prompt.format(
                        notification_message=state["notification_message"],
                    )
                )
            ]
        },
    )


def model_call_node(state: SupervisorState) -> Command:
    messages = [
        SystemMessage(content=system_prompt.format(workflow_id=state["workflow_id"]))
    ] + state["messages"]
    response = model.invoke(messages)

    if response.tool_calls:
        return Command(goto="worker_call_node", update={"messages": [response]})
    else:
        return Command(goto=END, update={"messages": [response]})


async def worker_call_node(state: SupervisorState):  # Added async
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    new_tool_messages = []
    any_hitl_triggered = False

    logger.info(f"Number of tool calls will be done: {len(tool_calls)}")

    for tc in tool_calls:
        worker_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]
        logger.info(f"Executing tool: {worker_name} with ID: {tool_id}")

        tool = worker_maps.get(worker_name)
        tool_result = await tool.ainvoke(tool_args)

        if tool_result.get("in_hitl"):
            any_hitl_triggered = True

        new_tool_messages.append(
            ToolMessage(
                content=tool_result["result"],
                tool_call_id=tool_id,
                name=worker_name,
            )
        )

    if any_hitl_triggered:
        return Command(
            goto="hitl_signal_node",
            update={"messages": new_tool_messages, "in_hitl": True},
        )
    else:
        return Command(
            goto="model_call_node",
            update={"messages": new_tool_messages, "in_hitl": False},
        )


def hitl_signal_node(state: SupervisorState):
    interrupt(
        {
            "task": "Review supervisor plan",
            "last_message": state["messages"][-1].content,
        }
    )

    return Command(goto="model_call_node", update={"in_hitl": False})


# ----------------------- BUILDER ----------------------------
supervisor_builder = StateGraph(SupervisorState)
supervisor_builder.add_node("input_node", input_node)
supervisor_builder.add_node("model_call_node", model_call_node)
supervisor_builder.add_node("worker_call_node", worker_call_node)
supervisor_builder.add_node("hitl_signal_node", hitl_signal_node)

supervisor_builder.add_edge(START, "input_node")

_pool = None
_supervisor_agent = None


async def get_supervisor_agent():
    global _pool, _supervisor_agent
    if _supervisor_agent is None:
        _pool = AsyncConnectionPool(conninfo=db_url, max_size=20)
        await _pool.open()
        checkpointer = AsyncPostgresSaver(_pool)
        await checkpointer.setup()  # also run setup async
        _supervisor_agent = supervisor_builder.compile(checkpointer=checkpointer)
    return _supervisor_agent


import asyncio
import uuid


async def main():
    supervisor_agent = get_supervisor_agent()

    wt_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": wt_id}}
    initial_input = {
        "notification_message": "Start Inventory Optimization",
        "in_hitl": False,
        "workflow_id": wt_id,
    }

    print("--- Starting Supervisor Agent ---")
    async for event in supervisor_agent.astream(initial_input, config=config):
        for node_name, state_update in event.items():
            print(f"\n[Node: {node_name}]")

            if "messages" in state_update:
                last_msg = state_update["messages"][-1]
                print(f"Output: {last_msg.content[:100]}...")

    # 4. Fetch the final state using the async method
    final_state = await supervisor_agent.aget_state(config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
