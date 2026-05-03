from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from multi_agents.prompts.reorder_assessment import (
    positive_points_system_prompt,
    negative_points_system_prompt,
    reorder_assessment_system_prompt,
    reorder_assessment_user_prompt,
)
from multi_agents.utils.llm_inference import get_model
from markdownify import markdownify
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
import json
from multi_agents.utils.logger import setup_logger
from typing import List

logger = setup_logger()

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large")


# ---------------------- STATE ---------------------------
class AssessmentState(MessagesState):
    report: str
    positive_points: str
    negative_points: str
    sku_level_data: list
    per_sku_reports: List[dict]


# ---------------------- STRUCTURED OUTPUT SCHEMAS ---------------------------
class PerSKUData(BaseModel):
    sku_name: str = Field(
        description="The unique identifier or human-readable name of the Stock Keeping Unit."
    )
    reorder_quantity: int = Field(
        description="The specific quantity of the SKU to be replenished in this order cycle."
    )
    supplier: str = Field(
        description="The designated primary supplier selected for this specific SKU."
    )
    reorder_status: str = Field(
        description="A boolean flag indicating whether a replenishment order is recommended (True) or withheld (False)."
    )


class ReorderDecisionSchema(BaseModel):
    reasoning: str = Field(
        description="A detailed justification for the reorder decision, synthesizing the positive and negative feedback from supplier reports."
    )
    sku_level_data: list[PerSKUData] = Field(
        description="A comprehensive list containing granular reorder details for every SKU involved in the decision process."
    )


class PointsSchema(BaseModel):
    points: list[str] = Field(
        description="A collection of qualitative observations, categorized as either strengths or risks, extracted from the audit reports."
    )


# ----------------------- NODES ----------------------------
def format_report_node(state: AssessmentState):
    raw_html = state.get("report", "")
    clean_markdown = markdownify(raw_html, heading_style="ATX")
    return {"report": clean_markdown}


def positive_points_node(state: AssessmentState) -> Command:
    messages = [
        SystemMessage(content=positive_points_system_prompt),
        HumanMessage(
            content=f"Please analyze the following report and advocate for a reorder:\n\n{state['report']}"
        ),
    ]

    structured_model = model.with_structured_output(PointsSchema)
    response = structured_model.invoke(messages)
    node_response = AIMessage(
        content=f"{json.dumps(response.points)}",
        name="final_assessment_node",
    )

    return Command(
        goto="final_assessment_node",
        update={"positive_points": response.points, "messages": [node_response]},
    )


def negative_points_node(state: AssessmentState) -> Command:
    messages = [
        SystemMessage(content=negative_points_system_prompt),
        HumanMessage(
            content=f"Please analyze the following report and advocate against a reorder:\n\n{state['report']}"
        ),
    ]

    structured_model = model.with_structured_output(PointsSchema)
    response = structured_model.invoke(messages)
    node_response = AIMessage(
        content=f"{json.dumps(response.points)}",
        name="final_assessment_node",
    )

    return Command(
        goto="final_assessment_node",
        update={"negative_points": response.points, "messages": [node_response]},
    )


def final_assessment_node(state: AssessmentState) -> Command:

    messages = [
        SystemMessage(content=reorder_assessment_system_prompt),
        HumanMessage(
            content=reorder_assessment_user_prompt.format(
                negative_points=state.get("negative_points"),
                positive_points=state.get("positive_points"),
                sku_level_data=json.dumps(state.get("per_sku_reports")),
            )
        ),
    ]

    structured_model = model.with_structured_output(ReorderDecisionSchema)
    decision_data = structured_model.invoke(messages)
    sku_level_data = [sku.model_dump() for sku in decision_data.sku_level_data]
    reasoning = decision_data.reasoning

    final_message = AIMessage(
        content=f"REASONING: {reasoning}",
        name="final_assessment_node",
    )

    return Command(
        goto=END,
        update={
            "sku_level_data": sku_level_data,
            "messages": [final_message],
        },
    )


# ----------------------- GRAPH BUILDER ----------------------------
reorder_assessment_agent_builder = StateGraph(AssessmentState)

reorder_assessment_agent_builder.add_node("format_report_node", format_report_node)
reorder_assessment_agent_builder.add_node("positive_points_node", positive_points_node)
reorder_assessment_agent_builder.add_node("negative_points_node", negative_points_node)
reorder_assessment_agent_builder.add_node(
    "final_assessment_node", final_assessment_node
)

reorder_assessment_agent_builder.add_edge(START, "format_report_node")
reorder_assessment_agent_builder.add_edge("format_report_node", "positive_points_node")
reorder_assessment_agent_builder.add_edge("format_report_node", "negative_points_node")

reorder_assessment_agent = reorder_assessment_agent_builder.compile().with_config(
    {"recursion_limit": 5}
)
