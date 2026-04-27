from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command

from multi_agents.prompts.reorder_assessment import (
    POSITIVE_SYSTEM_PROMPT,
    NEGATIVE_SYSTEM_PROMPT,
    FINAL_ASSESSMENT_SYSTEM_PROMPT,
)
from multi_agents.utils.llm_inference import get_model
import logging
import agentops
from markdownify import markdownify
from dotenv import load_dotenv
from multi_agents.guardrails.output.assessment_guard import ReorderDecision
from langchain_core.messages import AIMessage

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


# ----------------------- NODES ----------------------------
def format_report_node(state: AssessmentState):
    raw_html = state.get("report", "")

    # Convert HTML to Markdown
    clean_markdown = markdownify(raw_html, heading_style="ATX")

    return {"report": clean_markdown}


def positive_critique_node(state: AssessmentState) -> Command:
    messages = [
        SystemMessage(content=POSITIVE_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Please analyze the following report and advocate for a reorder:\n\n{state['report']}"
        ),
    ]

    response = model.invoke(messages)
    response.name = "positive_critique_node"

    return Command(
        goto="final_assessment_node",
        update={"positive_critique": response.content, "messages": [response]},
    )


def negative_critique_node(state: AssessmentState) -> Command:
    messages = [
        SystemMessage(content=NEGATIVE_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Please analyze the following report and advocate against a reorder:\n\n{state['report']}"
        ),
    ]

    response = model.invoke(messages)
    response.name = "negative_critique_node"

    return Command(
        goto="final_assessment_node",
        update={"negative_critique": response.content, "messages": [response]},
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
        HumanMessage(content=human_input),
    ]
    
    # Guardrail for structured output
    structured_model = model.with_structured_output(ReorderDecision)
    decision_data = structured_model.invoke(messages)
    
    reorder_status = decision_data.reorder_status
    reasoning = decision_data.reasoning
    
    logger.info(f"Final Reorder Assessment: {reorder_status} | Reason: {reasoning}")
    
    # Create a dummy AI message to append to the graph's memory state
    final_message = AIMessage(
        content=f"DECISION: {reorder_status}\nREASONING: {reasoning}", 
        name="final_assessment_node"
    )
    
    return Command(
        goto=END, 
        update={"reorder_status": reorder_status, "messages": [final_message]}
    )


# ----------------------- GRAPH BUILDER ----------------------------
reorder_assessment_agent_builder = StateGraph(AssessmentState)

reorder_assessment_agent_builder.add_node("format_report_node", format_report_node)
reorder_assessment_agent_builder.add_node(
    "positive_critique_node", positive_critique_node
)
reorder_assessment_agent_builder.add_node(
    "negative_critique_node", negative_critique_node
)
reorder_assessment_agent_builder.add_node(
    "final_assessment_node", final_assessment_node
)

# START -> Format
reorder_assessment_agent_builder.add_edge(START, "format_report_node")

# Format -> Parallel Critiques
reorder_assessment_agent_builder.add_edge(
    "format_report_node", "positive_critique_node"
)
reorder_assessment_agent_builder.add_edge(
    "format_report_node", "negative_critique_node"
)

reorder_assessment_agent = reorder_assessment_agent_builder.compile().with_config(
    {"recursion_limit": 5}
)

if __name__ == "__main__":
    mock_html_report = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Supplier Report - OrionForge Systems</title>
</head>
<body>

<h1>Supplier Evaluation Report</h1>

<p>Supplier Name: OrionForge Systems</p>
<p>Industry: High-End Graphics Processing Units</p>
<p>Date: April 2026</p>

<h2>Overview</h2>
<p>
OrionForge Systems develops and supplies high-performance GPUs used in artificial intelligence workloads,
gaming systems, and enterprise computing environments.
</p>

<h2>Customer Reputation</h2>
<ul>
<li>Customer satisfaction ratings reported as consistently high across enterprise clients.</li>
<li>Positive feedback regarding driver stability and long-term software support.</li>
<li>Customer support response times reported as timely and technically competent.</li>
<li>Low frequency of complaints in public forums and review platforms.</li>
</ul>

<h2>Track Record</h2>
<ul>
<li>Five consecutive GPU product generations released without major delays.</li>
<li>Reported defect rates below industry average.</li>
<li>On-time delivery performance exceeding 90% across multiple quarters.</li>
<li>Long-term contracts with cloud service providers and research institutions.</li>
</ul>

<h2>Operational Data</h2>
<ul>
<li>Consistent firmware updates and driver patches released post-launch.</li>
<li>Documented improvements in thermal efficiency across product iterations.</li>
<li>Established supply chain with multiple manufacturing partners.</li>
<li>Stable pricing trends with moderate fluctuations during peak demand periods.</li>
</ul>

<h2>Controversies</h2>
<ul>
<li>Minor criticism related to pricing increases during periods of high demand.</li>
<li>No major legal disputes or regulatory violations recorded.</li>
<li>No documented cases of undisclosed product defects.</li>
</ul>

</body>
</html>"""

    result = reorder_assessment_agent.invoke(
        {"report": mock_html_report, "messages": []}
    )

    print("--- FINAL STATE ---")
    print(f"Positive Critique:\n{result['positive_critique']}\n")
    print(f"Negative Critique:\n{result['negative_critique']}\n")
    print(f"Reorder Status: {result['reorder_status']}")

    print(
        f"LOGS\n\nPOSITIVE:\n"
        f"{result['positive_critique']}\n"
        f"NEGATIVE:\n"
        f"{result['negative_critique']}"
    )
