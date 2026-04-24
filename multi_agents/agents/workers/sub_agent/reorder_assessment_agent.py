import operator
from typing import Annotated
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command, Send
from multi_agents.utils.llm_inference import get_model
import logging
import agentops
from markdownify import markdownify
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

agentops.init()

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large")


# ---------------------- STATE ---------------------------
class AssessmentState(MessagesState):
    report: str
    positive_critique: str
    negative_critique: str
    reorder_status: bool


# ----------------------- PROMPTS --------------------------
from multi_agents.agents.prompts.assessment_agent import (
    POSITIVE_SYSTEM_PROMPT,
    NEGATIVE_SYSTEM_PROMPT,
    FINAL_ASSESSMENT_SYSTEM_PROMPT
)


# ----------------------- NODES ----------------------------
def format_report_node(state: AssessmentState):
    raw_html = state.get("report", "")

    # Convert HTML to Markdown
    clean_markdown = markdownify(raw_html, heading_style="ATX")

    return {"report": clean_markdown}


def positive_critique_node(state: AssessmentState) -> Command:
    messages = [
        SystemMessage(content=POSITIVE_SYSTEM_PROMPT),
        HumanMessage(content=f"Please analyze the following report and advocate for a reorder:\n\n{state['report']}")
    ]

    response = model.invoke(messages)
    response.name = "positive_critique_node"

    return Command(
        goto="final_assessment_node",
        update={
            "positive_critique": response.content,
            "messages": [response]
        }
    )


def negative_critique_node(state: AssessmentState) -> Command:
    messages = [
        SystemMessage(content=NEGATIVE_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Please analyze the following report and advocate against a reorder:\n\n{state['report']}")
    ]

    response = model.invoke(messages)
    response.name = "negative_critique_node"

    return Command(
        goto="final_assessment_node",
        update={
            "negative_critique": response.content,
            "messages": [response]
        }
    )


def final_assessment_node(state: AssessmentState) -> Command:
    human_input = f"""Please make the final reorder decision based on the following information:

### POSITIVE POINTS:
{state['positive_critique']}

### NEGATIVE POINTS:
{state['negative_critique']}
"""

    messages = [
        SystemMessage(content=FINAL_ASSESSMENT_SYSTEM_PROMPT),
        HumanMessage(content=human_input)
    ]

    response = model.invoke(messages)
    raw_content = response.content.strip()

    # Try to parse the JSON response
    import json
    try:
        # Clean markdown code blocks if the LLM wraps it
        if "```json" in raw_content:
            clean_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
            clean_content = raw_content.split("```")[1].split("```")[0].strip()
        else:
            clean_content = raw_content

        parsed_json = json.loads(clean_content)
        decision = parsed_json.get("decision", "").upper()
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        decision = raw_content.upper()

    # Parse the decision into a boolean
    reorder_status = True if "REORDER" in decision and "DO NOT REORDER" not in decision else False
    logger.info(f"Final Reorder Assessment: {reorder_status} (Parsed from: {decision})")

    return Command(
        goto=END,
        update={"reorder_status": reorder_status, "messages": [response]}
    )


# ----------------------- GRAPH BUILDER ----------------------------
assessment_agent_builder = StateGraph(AssessmentState)

assessment_agent_builder.add_node("format_report_node", format_report_node)
assessment_agent_builder.add_node("positive_critique_node", positive_critique_node)
assessment_agent_builder.add_node("negative_critique_node", negative_critique_node)
assessment_agent_builder.add_node("final_assessment_node", final_assessment_node)

# START -> Format
assessment_agent_builder.add_edge(START, "format_report_node")

# Format -> Parallel Critiques
assessment_agent_builder.add_edge("format_report_node", "positive_critique_node")
assessment_agent_builder.add_edge("format_report_node", "negative_critique_node")

assessment_agent = assessment_agent_builder.compile().with_config(
    {"recursion_limit": 5}
)

if __name__ == "__main__":
    mock_html_report = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Supplier Report - NovaCore Dynamics</title>
</head>
<body>

<h1>Supplier Evaluation Report</h1>

<p>Supplier Name: NovaCore Dynamics</p>
<p>Industry: High-End Graphics Processing Units</p>
<p>Date: April 2026</p>

<h2>Overview</h2>
<p>
NovaCore Dynamics manufactures GPUs for gaming, artificial intelligence, and enterprise applications,
with a focus on high-performance hardware specifications.
</p>

<h2>Customer Reputation</h2>
<ul>
<li>Mixed customer satisfaction ratings across enterprise and individual users.</li>
<li>Reported issues related to driver instability and software bugs.</li>
<li>Customer support response times described as inconsistent.</li>
<li>Increased frequency of complaints on public forums and review platforms.</li>
</ul>

<h2>Track Record</h2>
<ul>
<li>Multiple instances of delayed product releases.</li>
<li>Reported defect rates above industry average in certain product batches.</li>
<li>Inconsistent on-time delivery performance across recent quarters.</li>
<li>Limited long-term contracts with major enterprise clients.</li>
</ul>

<h2>Operational Data</h2>
<ul>
<li>Irregular firmware updates and delayed bug fixes reported.</li>
<li>Variability in thermal performance across different GPU models.</li>
<li>Supply chain disruptions during high-demand periods.</li>
<li>Significant price fluctuations observed during market shortages.</li>
</ul>

<h2>Controversies</h2>
<ul>
<li>Allegations of price inflation during GPU shortages.</li>
<li>Reports of preferential allocation to large clients.</li>
<li>Delayed disclosure of known hardware and firmware issues.</li>
<li>Criticism related to power consumption and efficiency.</li>
</ul>

</body>
</html>"""

    result = assessment_agent.invoke(
        {
            "report": mock_html_report,
            "messages": []
        }
    )

    print("--- FINAL STATE ---")
    print(f"Positive Critique:\n{result['positive_critique']}\n")
    print(f"Negative Critique:\n{result['negative_critique']}\n")
    print(f"Reorder Status: {result['reorder_status']}")
