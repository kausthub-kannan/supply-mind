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
import logging
import agentops
from markdownify import markdownify
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
import json

load_dotenv()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

agentops.init()

# ---------------------- MODELS ---------------------------
model = get_model("mistral-large")


# ---------------------- STATE ---------------------------
class AssessmentState(MessagesState):
    report: str
    positive_points: str
    negative_points: str
    sku_level_data: list


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

if __name__ == "__main__":
    mock_html_report = """```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demand Forecast & Supply Chain Report</title>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>
    <style>
        :root {
            --brand-light: #D5E7B5;
            --brand-primary: #72BAA9;
            --brand-secondary: #AE2448;
            --brand-dark: #6E1A37;
            --text-primary: #333333;
            --text-secondary: #666666;
            --background: #FFFFFF;
            --card-bg: #F9F9F9;
            --border-color: #EAEAEA;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background-color: var(--background);
            margin: 0;
            padding: 0;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 30px;
        }

        h1 {
            color: var(--brand-dark);
            margin: 0;
            font-size: 2.2em;
        }

        .report-date {
            color: var(--text-secondary);
            font-size: 0.9em;
            margin-top: 10px;
        }

        .executive-summary {
            background-color: var(--card-bg);
            border-left: 4px solid var(--brand-primary);
            padding: 20px;
            margin-bottom: 40px;
            border-radius: 0 4px 4px 0;
        }

        .executive-summary h2 {
            color: var(--brand-dark);
            margin-top: 0;
        }

        .kpi-banner {
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 40px;
        }

        .kpi-card {
            background-color: var(--background);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            flex: 1;
            min-width: 200px;
            text-align: center;
        }

        .kpi-card h3 {
            color: var(--text-secondary);
            font-size: 1em;
            margin-top: 0;
        }

        .kpi-card p {
            font-size: 2em;
            color: var(--brand-dark);
            margin: 10px 0 0;
            font-weight: 600;
        }

        section {
            margin-bottom: 50px;
            background-color: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }

        .sku-header {
            background-color: var(--brand-light);
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .sku-header h2 {
            margin: 0;
            color: var(--brand-dark);
        }

        .sku-header p {
            margin: 0;
            color: var(--text-secondary);
            font-size: 0.9em;
        }

        .section-content {
            padding: 25px;
        }

        .section-content h3 {
            color: var(--brand-secondary);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }

        .chart-container {
            width: 100%;
            height: 450px;
            margin: 20px 0;
        }

        .data-card {
            background-color: var(--background);
            border-left: 4px solid var(--brand-primary);
            padding: 15px;
            margin: 20px 0;
            border-radius: 0 4px 4px 0;
        }

        .data-card h4 {
            margin-top: 0;
            color: var(--brand-dark);
        }

        ul {
            padding-left: 20px;
        }

        li {
            margin-bottom: 8px;
        }

        blockquote {
            border-left: 4px solid var(--brand-secondary);
            background-color: rgba(174, 36, 72, 0.05);
            padding: 15px;
            margin: 20px 0;
            font-style: italic;
            color: var(--text-secondary);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }

        th {
            background-color: var(--brand-light);
            color: var(--brand-dark);
            font-weight: 600;
        }

        tr:hover {
            background-color: rgba(114, 186, 169, 0.1);
        }

        footer {
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.8em;
            border-top: 1px solid var(--border-color);
            margin-top: 40px;
        }

        .sources {
            text-align: left;
            max-width: 1200px;
            margin: 0 auto;
        }

        .sources h3 {
            color: var(--brand-dark);
        }

        .sources ul {
            columns: 2;
        }

        .sources li {
            margin-bottom: 5px;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Demand Forecast & Supply Chain Report</h1>
            <p class="report-date">Generated on: <strong>2026-04-24</strong></p>
        </header>

        <div class="executive-summary">
            <h2>Executive Summary</h2>
            <p>This report provides a comprehensive analysis of the 30-day demand forecast, anomaly detection, and supplier strategy for two high-priority SKUs: <strong>ASUS ROG Maximus Z890 (LGA1851)</strong> and <strong>MSI MEG X870E GODLIKE (AM5)</strong>. The analysis is designed to support data-driven inventory optimization and procurement decisions.</p>
            <p>The forecast data indicates a <strong>stable demand trend</strong> for both SKUs, with minor fluctuations. However, <strong>one medium-severity anomaly</strong> was detected for each SKU, requiring further review to determine potential root causes and corrective actions.</p>
            <p>Supplier analysis reveals that <strong>Newegg Commerce</strong> and <strong>ASI Corp</strong> are the optimal suppliers for the Z890 and X870E SKUs, respectively, based on their capacity, logistics infrastructure, and bulk-order flexibility. However, <strong>residual risks</strong> such as financial volatility and geographic concentration necessitate proactive mitigation strategies, including dual sourcing and contractual safeguards.</p>
        </div>

        <div class="kpi-banner">
            <div class="kpi-card">
                <h3>Total Order Quantity (Z890)</h3>
                <p>8,785</p>
            </div>
            <div class="kpi-card">
                <h3>Total Order Quantity (X870E)</h3>
                <p>6,542</p>
            </div>
            <div class="kpi-card">
                <h3>Total Anomalies Detected</h3>
                <p>2</p>
            </div>
            <div class="kpi-card">
                <h3>Forecast Horizon (Days)</h3>
                <p>30</p>
            </div>
        </div>

        <!-- SKU: MB-Z890-LGA1851 -->
        <section>
            <div class="sku-header">
                <h2>ASUS ROG Maximus Z890 (Intel LGA1851)</h2>
                <p>SKU ID: MB-Z890-LGA1851</p>
            </div>
            <div class="section-content">
                <h3>30-Day Demand Forecast</h3>
                <div class="chart-container" id="forecast-z890"></div>
                <script>
                    var forecastData = {
                        x: [
                            "2026-04-25", "2026-04-26", "2026-04-27", "2026-04-28", "2026-04-29", "2026-04-30",
                            "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05", "2026-05-06",
                            "2026-05-07", "2026-05-08", "2026-05-09", "2026-05-10", "2026-05-11", "2026-05-12",
                            "2026-05-13", "2026-05-14", "2026-05-15", "2026-05-16", "2026-05-17", "2026-05-18",
                            "2026-05-19", "2026-05-20", "2026-05-21", "2026-05-22", "2026-05-23", "2026-05-24"
                        ],
                        y: [
                            285, 308, 308, 309, 295, 295, 300, 281, 293, 280, 293, 275, 304, 291, 309, 300, 299,
                            306, 281, 280, 279, 306, 282, 281, 304, 287, 292, 279, 294, 289
                        ]
                    };
                    var trace = {
                        x: forecastData.x,
                        y: forecastData.y,
                        type: 'line',
                        mode: 'lines+markers',
                        marker: { color: '#72BAA9', size: 8 },
                        line: { color: '#AE2448', width: 3 }
                    };
                    var layout = {
                        title: '30-Day Forecasted Demand for ASUS ROG Maximus Z890',
                        xaxis: { title: 'Date', gridcolor: '#EAEAEA' },
                        yaxis: { title: 'Forecasted Demand (Units)', gridcolor: '#EAEAEA' },
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        paper_bgcolor: 'rgba(0,0,0,0)'
                    };
                    Plotly.newPlot('forecast-z890', [trace], layout);
                </script>

                <div class="data-card">
                    <h4>Key Insights</h4>
                    <p>The demand forecast for the ASUS ROG Maximus Z890 shows a <strong>stable trend</strong> with minor fluctuations, averaging <strong>~293 units per day</strong>. The highest demand is projected on <strong>2026-05-12 (306 units)</strong>, while the lowest is on <strong>2026-05-06 (275 units)</strong>. The total order quantity required to meet this demand is <strong>8,785 units</strong>.</p>
                </div>

                <h3>Anomaly Detection</h3>
                <div class="chart-container" id="anomaly-z890"></div>
                <script>
                    var anomalyData = {
                        x: ["2026-04-17"],
                        y: [1],
                        text: ["Return Rates Anomaly"],
                        type: 'scatter',
                        mode: 'markers',
                        marker: { color: '#AE2448', size: 12 }
                    };
                    var forecastTrace = {
                        x: forecastData.x,
                        y: forecastData.y,
                        type: 'line',
                        mode: 'lines',
                        line: { color: '#72BAA9', width: 2 },
                        name: 'Forecasted Demand'
                    };
                    var layout = {
                        title: 'Detected Anomalies in Historical Data',
                        xaxis: { title: 'Date', gridcolor: '#EAEAEA' },
                        yaxis: { title: 'Anomaly Indicator', showgrid: false },
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        showlegend: true
                    };
                    Plotly.newPlot('anomaly-z890', [forecastTrace, anomalyData], layout);
                </script>

                <div class="data-card">
                    <h4>Anomaly Breakdown</h4>
                    <ul>
                        <li><strong>Date:</strong> 2026-04-17</li>
                        <li><strong>Type:</strong> Return Rates</li>
                        <li><strong>Severity:</strong> Medium</li>
                        <li><strong>Description:</strong> Statistical deviation detected matching a 'Return Rates' profile. This may indicate a temporary spike in product returns, potentially due to quality control issues, shipping damage, or customer dissatisfaction.</li>
                        <li><strong>Action Required:</strong> No immediate human review is required, but it is recommended to investigate the root cause (e.g., batch quality, logistics partners) to prevent recurrence.</li>
                    </ul>
                </div>

                <h3>Supplier Strategy</h3>
                <p>The following supplier has been identified as the optimal choice for fulfilling the order:</p>
                <blockquote>
                    <strong>Recommended Supplier:</strong> Newegg Commerce (CA)
                </blockquote>
                <div class="data-card">
                    <h4>Selection Rationale</h4>
                    <p>Newegg Commerce is the <strong>only viable supplier</strong> for fulfilling an order of <strong>8,785 units</strong> by <strong>April 20, 2026</strong>. Key advantages include:</p>
                    <ul>
                        <li><strong>B2B/3PL Services:</strong> Newegg offers established business-to-business and third-party logistics services, enabling bulk inventory aggregation and flexible order fulfillment.</li>
                        <li><strong>National Distribution Network:</strong> Their Cincinnati distribution hub reduces transit risks for nationwide delivery.</li>
                        <li><strong>Supplier Leverage:</strong> Direct relationships with ASUS and major distributors (e.g., Ingram Micro, Synnex) ensure priority access to inventory.</li>
                        <li><strong>Custom Quoting:</strong> Newegg's hybrid retail-fulfillment model allows for negotiable pricing and flexible minimum order quantities (MOQs).</li>
                    </ul>
                </div>

                <div class="data-card">
                    <h4>Why Other Candidates Were Not Selected</h4>
                    <p><strong>Central Computers (CA):</strong></p>
                    <ul>
                        <li><strong>Limited Scale:</strong> Central Computers is a regional retailer with ~$19M annual revenue and five physical locations in Northern California. It lacks the inventory capacity and logistics infrastructure to fulfill large-scale orders.</li>
                        <li><strong>Indirect Supplier Relationships:</strong> Their reliance on distributors like Ingram Micro limits their ability to negotiate lead times or secure bulk inventory.</li>
                        <li><strong>Operational Constraints:</strong> Their focus on SMB/reseller channels and lack of transparent SLAs make them unreliable for time-sensitive, large-scale deployments.</li>
                    </ul>
                </div>

                <div class="data-card">
                    <h4>Risk Assessment & Mitigation</h4>
                    <p><strong>Residual Risks:</strong></p>
                    <ul>
                        <li><strong>Financial Volatility:</strong> Newegg's publicly traded status (NASDAQ: NEGG) and historical profitability fluctuations introduce counterparty risk.</li>
                        <li><strong>Single-Hub Logistics:</strong> Reliance on a single U.S. distribution center (Cincinnati) creates bottleneck risks.</li>
                        <li><strong>Component Shortages:</strong> Potential supply constraints for PCIe 5.0 M.2 slots and WiFi 7 modules due to controller IC shortages.</li>
                    </ul>
                    <p><strong>Recommended Mitigations:</strong></p>
                    <ul>
                        <li><strong>Dual Sourcing:</strong> Secure a secondary supplier (e.g., ASUS direct B2B portal or Ingram Micro) for 20-30% of the order.</li>
                        <li><strong>Contractual Safeguards:</strong> Negotiate firm lead-time guarantees and price-lock clauses to protect against volatility.</li>
                        <li><strong>Logistics Redundancy:</strong> Require Newegg to pre-stage inventory by February 2026 and provide weekly shipment tracking updates.</li>
                        <li><strong>Compliance Audit:</strong> Verify Newegg's PCI DSS and ISO 9001 compliance before finalizing the contract.</li>
                    </ul>
                </div>
            </div>
        </section>

        <!-- SKU: MB-X870-AM5 -->
        <section>
            <div class="sku-header">
                <h2>MSI MEG X870E GODLIKE (AMD AM5)</h2>
                <p>SKU ID: MB-X870-AM5</p>
            </div>
            <div class="section-content">
                <h3>30-Day Demand Forecast</h3>
                <div class="chart-container" id="forecast-x870"></div>
                <script>
                    var forecastDataX870 = {
                        x: [
                            "2026-04-25", "2026-04-26", "2026-04-27", "2026-04-28", "2026-04-29", "2026-04-30",
                            "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05", "2026-05-06",
                            "2026-05-07", "2026-05-08", "2026-05-09", "2026-05-10", "2026-05-11", "2026-05-12",
                            "2026-05-13", "2026-05-14", "2026-05-15", "2026-05-16", "2026-05-17", "2026-05-18",
                            "2026-05-19", "2026-05-20", "2026-05-21", "2026-05-22", "2026-05-23", "2026-05-24"
                        ],
                        y: [
                            218, 220, 211, 229, 226, 222, 202, 227, 235, 207, 208, 221, 234, 202, 200, 209, 219,
                            229, 229, 227, 204, 203, 234, 234, 230, 229, 214, 200, 219, 200
                        ]
                    };
                    var trace = {
                        x: forecastDataX870.x,
                        y: forecastDataX870.y,
                        type: 'line',
                        mode: 'lines+markers',
                        marker: { color: '#72BAA9', size: 8 },
                        line: { color: '#AE2448', width: 3 }
                    };
                    var layout = {
                        title: '30-Day Forecasted Demand for MSI MEG X870E GODLIKE',
                        xaxis: { title: 'Date', gridcolor: '#EAEAEA' },
                        yaxis: { title: 'Forecasted Demand (Units)', gridcolor: '#EAEAEA' },
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        paper_bgcolor: 'rgba(0,0,0,0)'
                    };
                    Plotly.newPlot('forecast-x870', [trace], layout);
                </script>

                <div class="data-card">
                    <h4>Key Insights</h4>
                    <p>The demand forecast for the MSI MEG X870E GODLIKE shows a <strong>consistent trend</strong> with an average daily demand of <strong>~218 units</strong>. The peak demand is projected on <strong>2026-05-03 and 2026-05-17 (235 and 234 units, respectively)</strong>, while the lowest demand is on <strong>2026-05-01 (202 units)</strong>. The total order quantity required is <strong>6,542 units</strong>.</p>
                </div>

                <h3>Anomaly Detection</h3>
                <div class="chart-container" id="anomaly-x870"></div>
                <script>
                    var anomalyDataX870 = {
                        x: ["2026-04-18"],
                        y: [1],
                        text: ["Demand Spikes Anomaly"],
                        type: 'scatter',
                        mode: 'markers',
                        marker: { color: '#AE2448', size: 12 }
                    };
                    var forecastTrace = {
                        x: forecastDataX870.x,
                        y: forecastDataX870.y,
                        type: 'line',
                        mode: 'lines',
                        line: { color: '#72BAA9', width: 2 },
                        name: 'Forecasted Demand'
                    };
                    var layout = {
                        title: 'Detected Anomalies in Historical Data',
                        xaxis: { title: 'Date', gridcolor: '#EAEAEA' },
                        yaxis: { title: 'Anomaly Indicator', showgrid: false },
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        showlegend: true
                    };
                    Plotly.newPlot('anomaly-x870', [forecastTrace, anomalyDataX870], layout);
                </script>

                <div class="data-card">
                    <h4>Anomaly Breakdown</h4>
                    <ul>
                        <li><strong>Date:</strong> 2026-04-18</li>
                        <li><strong>Type:</strong> Demand Spikes</li>
                        <li><strong>Severity:</strong> Medium</li>
                        <li><strong>Description:</strong> Statistical deviation detected matching a 'Demand Spikes' profile. This may indicate a sudden surge in demand, potentially driven by external factors such as promotions, competitor stockouts, or market trends.</li>
                        <li><strong>Action Required:</strong> Human review is required to assess the cause of the spike and determine if adjustments to the forecast or inventory strategy are necessary.</li>
                    </ul>
                </div>

                <h3>Supplier Strategy</h3>
                <p>The following supplier has been identified as the optimal choice for fulfilling the order:</p>
                <blockquote>
                    <strong>Recommended Supplier:</strong> ASI Corp
                </blockquote>
                <div class="data-card">
                    <h4>Selection Rationale</h4>
                    <p>ASI Corp demonstrates <strong>superior supply chain agility and bulk-order flexibility</strong> for the MSI MEG X870E GODLIKE. Key advantages include:</p>
                    <ul>
                        <li><strong>Tier 1 Distributor Status:</strong> Direct access to MSI's production pipeline reduces lead times to 8-12 weeks.</li>
                        <li><strong>Negotiable MOQs:</strong> Flexible minimum order quantities (as low as 500 units for established partners).</li>
                        <li><strong>Consolidated Shipping:</strong> Shipping from CA/Houston hubs minimizes logistics complexity.</li>
                        <li><strong>Pricing Stability:</strong> Verified 2025-2026 pricing stability via partner portals.</li>
                    </ul>
                </div>

                <div class="data-card">
                    <h4>Why Other Candidates Were Not Selected</h4>
                    <p><strong>D&H Distributing:</strong></p>
                    <ul>
                        <li><strong>Lack of Transparency:</strong> No published lead times, MOQs, or pricing tiers for the X870E GODLIKE.</li>
                        <li><strong>Rigid Logistics:</strong> Mandatory preapproved carriers and focus on SMB/reseller channels limit flexibility.</li>
                        <li><strong>Limited Experience:</strong> No verifiable track record for handling enterprise-scale orders (6,500+ units).</li>
                    </ul>
                </div>

                <div class="data-card">
                    <h4>Risk Assessment & Mitigation</h4>
                    <p><strong>Residual Risks:</strong></p>
                    <ul>
                        <li><strong>Geographic Concentration:</strong> Reliance on CA/Houston warehouses creates vulnerability to regional disruptions.</li>
                        <li><strong>Production Bottlenecks:</strong> Potential allocation limits if AMD Ryzen 9000 adoption lags.</li>
                    </ul>
                    <p><strong>Recommended Mitigations:</strong></p>
                    <ul>
                        <li><strong>Dual Sourcing:</strong> Allocate 20% of the order to a backup supplier like Synnex.</li>
                        <li><strong>Contractual Guarantees:</strong> Include penalties for delays exceeding 10%.</li>
                        <li><strong>Air Freight Contingencies:</strong> Pre-negotiate air freight options for critical shipments.</li>
                    </ul>
                </div>
            </div>
        </section>

        <div class="sources">
            <h3>References</h3>
            <p>The following sources were used to compile the supplier analysis and recommendations:</p>
            <ul>
                <li><a href="https://www.newegg.com/asus-rog-maximus-z890-hero-atx-motherboard-intel-z890-lga-1851/p/N82E16813119691?srsltid=AfmBOop33kwKF5nkaMi-ozDtu09_2GRt26AUoF9rnJSAY3QWygMeWKRE" target="_blank">Newegg: ASUS ROG Maximus Z890 Hero</a></li>
                <li><a href="https://www.newegg.com/asus-rog-maximus-z890-hero-atx-motherboard-intel-z890-lga-1851/p/N82E16813119691?srsltid=AfmBOopyfU1hYFnF-dM_fFPfk3CRjp-BTMPjTR-JRBlY7SugBsxDmOJo" target="_blank">Newegg: ASUS ROG Maximus Z890 Hero (Alternate Link)</a></li>
                <li><a href="https://www.newegg.com/p/pl?d=rog+maximus+z890&srsltid=AfmBOoq1ogkgbtOR-aE0a_MX10tnBZkHmXb-eHMwHGjBiSJVqdLWA5Jh" target="_blank">Newegg: ROG Maximus Z890 Product Search</a></li>
                <li><a href="https://www.newegg.com/p/pl?d=asus+rog+maximus+z890&srsltid=AfmBOooU3xzZZg2Z6qHZIzoq5IuGzfQQwyTn74BV7fAqOmOmBanOXYBU" target="_blank">Newegg: ASUS ROG Maximus Z890 Product Search</a></li>
                <li><a href="https://www.newegg.com/p/pl?d=asus+rog+maximus+z890&srsltid=AfmBOopQUSfYWUsAu6qjcGLkQQIbMQj2LmdJeWHw1TQPcDB5eQSg4rBo" target="_blank">Newegg: ASUS ROG Maximus Z890 Product Search (Alternate)</a></li>
                <li><a href="https://www.centralcomputer.com/all-products/hardware/motherboards/cc/in_store:Yes/price:600-700/processor_socket:Socket+AM5.html?amp%3Bproduct_type=3601&srsltid=AfmBOoqTwPfHhGLnyVMGWx-zKIpKvRhB1KFEQdi1J7StODGVjSQDtPf-" target="_blank">Central Computers: Motherboard Inventory</a></li>
                <li><a href="https://rog.asus.com/motherboards/rog-maximus/rog-maximus-z890-apex/" target="_blank">ASUS ROG: Maximus Z890 Apex</a></li>
                <li><a href="https://rog.asus.com/motherboards/rog-maximus/rog-maximus-z890-extreme/" target="_blank">ASUS ROG: Maximus Z890 Extreme</a></li>
                <li><a href="https://www.centralcomputer.com/asus-rog-maximus-z890-apex-intel-z890-lga-1851-atx-motherboard-advanced-ai-pc-ready-22-2-1-2-stages-ddr5-wifi-7-5g-lan.html?srsltid=AfmBOopDJaAmdWDH60hF-HZZLtdakTHBF_4izuQE9oqGINT8JD0fjMww" target="_blank">Central Computers: ASUS ROG Maximus Z890 Apex</a></li>
                <li><a href="https://www.centralcomputer.com/asus-rog-maximus-z890-apex-intel-z890-lga-1851-atx-motherboard-advanced-ai-pc-ready-22-2-1-2-stages-ddr5-wifi-7-5g-lan.html?srsltid=AfmBOoqw1hj3vLxbvzrBN5FJ5_jkjqno7PrjHkhT5StNtjH9Oaa23act" target="_blank">Central Computers: ASUS ROG Maximus Z890 Apex (Alternate Link)</a></li>
                <li><a href="https://leadiq.com/c/newegg/5a1d8aa72400002400648da9" target="_blank">LeadIQ: Newegg Company Profile</a></li>
                <li><a href="https://productfulfillmentsolutions.com/product-fulfillment-solutions-resources/minimum-order-quantity-meaning-how-to-calculate-moq-product-fulfillment-solutions/" target="_blank">Product Fulfillment Solutions: MOQ Guide</a></li>
                <li><a href="https://www.newegg.com/corporate/about?srsltid=AfmBOoqmPVHMY8N4VoWZnkxBeyO56x1O83ASD0WxIw7tBdHEsHou88c7" target="_blank">Newegg: Corporate Information</a></li>
                <li><a href="https://rocketreach.co/central-computers-profile_b5c7a2faf42e0d56" target="_blank">RocketReach: Central Computers Profile</a></li>
                <li><a href="https://dclcorp.com/blog/inventory/minimum-order-quantity-moq/" target="_blank">DCL Corp: MOQ Explanation</a></li>
                <li><a href="https://www.netsuite.com/portal/resource/articles/inventory-management/minimum-order-quantity-moq.shtml" target="_blank">NetSuite: MOQ Best Practices</a></li>
                <li><a href="https://pcpartpicker.com/product/pRLdnQ/msi-meg-x870e-godlike-eatx-am5-motherboard-meg-x870e-godlike" target="_blank">PCPartPicker: MSI MEG X870E GODLIKE</a></li>
                <li><a href="https://www.techpowerup.com/344087/msi-meg-x870e-godlike-x-edition-starts-selling-at-usd-1-300" target="_blank">TechPowerUp: MSI MEG X870E GODLIKE X Edition</a></li>
                <li><a href="https://hothardware.com/news/msi-meg-x870e-godlike-x-motherboard-debuts-1300" target="_blank">HotHardware: MSI MEG X870E GODLIKE X Debut</a></li>
                <li><a href="https://us-store.msi.com/MEG-X870E-GODLIKE?srsltid=AfmBOopKZU8zF21-Mf5u5Skf5MU1-SNzMUmgu7_EbV9sWxYn-uhc_UuV" target="_blank">MSI US Store: MEG X870E GODLIKE</a></li>
                <li><a href="https://us-store.msi.com/MEG-X870E-GODLIKE?srsltid=AfmBOooR5hxFFqTnh6xuZuOXrk1l_-qi7x-t20vsKCTtucZ_RJjZ0ZSQ" target="_blank">MSI US Store: MEG X870E GODLIKE (Alternate Link)</a></li>
                <li><a href="https://us-store.msi.com/MEG-X870E-GODLIKE-X-EDITION?srsltid=AfmBOoqCwlbpSOAvZS-gy4zkVbdlD6huk6doUf9MBMqZkTRLruiU9d1f" target="_blank">MSI US Store: MEG X870E GODLIKE X Edition</a></li>
                <li><a href="https://us-store.msi.com/MEG-X870E-GODLIKE-X-EDITION?srsltid=AfmBOor8XemJgmaOtfklQ-4q4aHF8cShKyTsNZA0xBV7SvAHsAf33Gs7" target="_blank">MSI US Store: MEG X870E GODLIKE X Edition (Alternate Link)</a></li>
                <li><a href="https://www.asipartner.com/resources/asi-insider/" target="_blank">ASI Corp: ASI Insider Resources</a></li>
                <li><a href="https://www.asipartner.com/industrial/" target="_blank">ASI Corp: Industrial Solutions</a></li>
                <li><a href="https://www.taipeitimes.com/News/biz/archives/2026/03/14/2003853776" target="_blank">Taipei Times: ASI Corp Business News</a></li>
                <li><a href="https://www.dandh.com/v4/view?pageReq=Press&cmsId=2025&int_cid=PRSS&utm_campaign=PR-2025" target="_blank">D&H Distributing: Press Releases</a></li>
                <li><a href="https://www.dandh.com/v4/view?pageReq=focusedlanding&focus=OPSB1&cid=PR27" target="_blank">D&H Distributing: Focused Landing Page</a></li>
                <li><a href="https://www.dandh.com/" target="_blank">D&H Distributing: Homepage</a></li>
                <li><a href="https://pangoly.com/en/price-history/msi-meg-x870e-godlike" target="_blank">Pangoly: MSI MEG X870E GODLIKE Price History</a></li>
                <li><a href="https://www.cdw.com/product/msi-meg-x870e-godlike-gaming-desktop-motherboard-amd-x870e-chipset-sock/8236153" target="_blank">CDW: MSI MEG X870E GODLIKE Product Page</a></li>
                <li><a href="https://geizhals.de/msi-meg-x870e-godlike-a3295178.html?hloc=&va=b&vl=&plz=&mobile=1" target="_blank">Geizhals: MSI MEG X870E GODLIKE (Germany)</a></li>
                <li><a href="https://geizhals.at/msi-meg-x870e-godlike-a3295178.html?mobile=1" target="_blank">Geizhals: MSI MEG X870E GODLIKE (Austria)</a></li>
                <li><a href="https://gbgmt.com/bulk-customers-questions-moq-lead-time-samples-costs" target="_blank">GBGMT: Bulk Customer FAQs</a></li>
                <li><a href="https://www.xianxingbeauty.com/buying-wholesale-press-on-nails-moq-shipping.html" target="_blank">XianXing Beauty: Wholesale MOQ Guide</a></li>
                <li><a href="https://www.dandh.com/docs/vendor/US-DomesticSupplierRoutingGuide.pdf" target="_blank">D&H Distributing: US Domestic Supplier Routing Guide</a></li>
            </ul>
        </div>

        <footer>
            <p>&copy; 2026 Inventory Optimization System. All rights reserved.</p>
        </footer>
    </div>
</body>
</html>
"""

    result = reorder_assessment_agent.invoke(
        {"report": mock_html_report, "messages": []}
    )

    print(f"Positive Points: {result['positive_points']}")
    print(f"Negative Points: {result['negative_points']}")
    print(f"SKU Data: {result['sku_level_data']}")
