import operator
from typing import Annotated
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from multi_agents.prompts.report_generation import system_prompt, user_prompt
from multi_agents.utils.llm_inference import get_model
from multi_agents.agents.toolkits import report_generation_toolkit, tool_maps
from multi_agents.utils.logger import setup_logger

logger = setup_logger()


# ---------------------- MODELS ---------------------------
model = get_model("mistral-large", tools=report_generation_toolkit)


# ---------------------- STATE ---------------------------
class ReportGeneratorState(MessagesState):
    analysis_raw_data: str
    graphs: Annotated[list, operator.add]
    content_cards: Annotated[list, operator.add]
    table_cards: Annotated[list, operator.add]
    report: str


# ----------------------- NODES ----------------------------
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


def model_call_node(state: ReportGeneratorState) -> Command:
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    if response.tool_calls:
        return Command(goto="tool_call_node", update={"messages": [response]})
    else:
        return Command(
            goto=END, update={"messages": [response], "report": response.content}
        )


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
