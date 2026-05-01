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
from markdownify import markdownify
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
import json

load_dotenv()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
    mock_html_report = """DOCTYPE html>
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
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f9f9f9;
            margin: 0;
            padding: 20px;
        }

        .report-container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: #fff;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            overflow: hidden;
        }

        header {
            background-color: var(--brand-dark);
            color: #fff;
            padding: 20px;
            text-align: center;
        }

        header h1 {
            margin: 0;
            font-size: 28px;
        }

        .report-meta {
            font-size: 14px;
            opacity: 0.9;
            margin-top: 5px;
        }

        .executive-summary {
            padding: 20px;
            border-bottom: 1px solid #eee;
        }

        .executive-summary h2 {
            color: var(--brand-secondary);
            margin-top: 0;
            font-size: 22px;
        }

        .executive-summary p {
            margin-bottom: 15px;
        }

        section {
            padding: 20px;
            border-bottom: 1px solid #eee;
        }

        section:last-child {
            border-bottom: none;
        }

        .sku-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .sku-header h2 {
            color: var(--brand-primary);
            margin: 0;
            font-size: 24px;
        }

        .sku-id {
            background-color: var(--brand-light);
            color: var(--brand-dark);
            padding: 5px 10px;
            border-radius: 4px;
            font-weight: bold;
        }

        .chart-container {
            width: 100%;
            height: 450px;
            margin: 20px 0;
        }

        .anomaly-list {
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid var(--brand-secondary);
        }

        .anomaly-list h3 {
            margin-top: 0;
            color: var(--brand-secondary);
        }

        .anomaly-item {
            margin-bottom: 10px;
        }

        .anomaly-item strong {
            color: var(--brand-secondary);
        }

        .supplier-analysis {
            background-color: #fff;
            border: 1px solid #eee;
            border-radius: 4px;
            padding: 15px;
        }

        .supplier-analysis h3 {
            margin-top: 0;
            color: var(--brand-primary);
        }

        .supplier-analysis h4 {
            color: var(--brand-secondary);
        }

        .references {
            padding: 20px;
            background-color: #f9f9f9;
        }

        .references h3 {
            color: var(--brand-dark);
        }

        .references ul {
            list-style-type: none;
            padding: 0;
        }

        .references li {
            margin-bottom: 5px;
        }

        .references a {
            color: var(--brand-primary);
            text-decoration: none;
        }

        .references a:hover {
            text-decoration: underline;
        }

        .kpi-banner {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }

        .kpi-card {
            background-color: var(--brand-light);
            border-left: 5px solid var(--brand-primary);
            padding: 15px;
            border-radius: 4px;
            text-align: center;
            flex: 1;
            margin: 0 10px;
        }

        .kpi-card h4 {
            margin: 0 0 10px 0;
            color: var(--brand-dark);
        }

        .kpi-card p {
            margin: 0;
            font-size: 24px;
            font-weight: bold;
            color: var(--brand-secondary);
        }
    </style>
</head>
<body>
    <div class="report-container">
        <header>
            <h1>Demand Forecast & Supply Chain Report</h1>
            <p class="report-meta">Generated on: <strong>2026-04-27</strong></p>
        </header>

        <div class="executive-summary">
            <h2>Executive Summary</h2>
            <p>
                This report provides a comprehensive analysis of the demand forecast, anomaly detection, and supplier risk assessment for the <strong>MSI MEG X870E GODLIKE (MB-X870-AM5)</strong> motherboard over a 30-day horizon.
            </p>
            <p>
                The forecast indicates a <strong>total order quantity of 3,078 units</strong>, with daily demand fluctuating between <strong>85 and 120 units</strong>. Three critical anomalies were detected in the historical data, requiring immediate review to mitigate potential supply chain disruptions.
            </p>
            <p>
                The supplier analysis for <strong>D&H Distributing Company</strong> reveals significant operational and reputational risks, including chronic order fulfillment delays, misleading pricing practices, and poor customer service responsiveness. These factors necessitate a direct audit or consideration of alternative suppliers for time-sensitive procurements.
            </p>
        </div>

        <!-- SKU: MB-X870-AM5 -->
        <section>
            <div class="sku-header">
                <h2>MSI MEG X870E GODLIKE</h2>
                <span class="sku-id">MB-X870-AM5</span>
            </div>

            <div class="kpi-banner">
                <div class="kpi-card">
                    <h4>Total Forecasted Demand (30 Days)</h4>
                    <p>3,078</p>
                </div>
                <div class="kpi-card">
                    <h4>Anomalies Detected</h4>
                    <p>3</p>
                </div>
            </div>

            <h3>30-Day Demand Forecast</h3>
            <div class="chart-container" id="forecast-chart-MB-X870-AM5"></div>

            <h3>Anomaly Detection Summary</h3>
            <div class="anomaly-list">
                <h3>Detected Anomalies</h3>
                <ul>
                    <li class="anomaly-item">
                        <strong>Date:</strong> 2026-03-30 |
                        <strong>Type:</strong> Price-Demand |
                        <strong>Severity:</strong> Critical |
                        <strong>Review Required:</strong> Yes |
                        <p><em>Statistical deviation detected matching a 'Price-Demand' profile.</em></p>
                    </li>
                    <li class="anomaly-item">
                        <strong>Date:</strong> 2026-04-12 |
                        <strong>Type:</strong> Demand Spikes |
                        <strong>Severity:</strong> Medium |
                        <strong>Review Required:</strong> Yes |
                        <p><em>Statistical deviation detected matching a 'Demand Spikes' profile.</em></p>
                    </li>
                    <li class="anomaly-item">
                        <strong>Date:</strong> 2026-04-20 |
                        <strong>Type:</strong> Stock Balance |
                        <strong>Severity:</strong> Critical |
                        <strong>Review Required:</strong> No |
                        <p><em>Statistical deviation detected matching a 'Stock Balance' profile.</em></p>
                    </li>
                </ul>
            </div>

            <h3>Supplier Risk Assessment</h3>
            <div class="supplier-analysis">
                <h3>D&H Distributing Company</h3>
                <h4>Operational & Reliability Risks</h4>
                <p>
                    D&H Distributing exhibits <strong>critical supply chain reliability issues</strong>, with multiple customer reports indicating <strong>chronic order fulfillment delays</strong> (often requiring manual follow-ups), inconsistent inventory management, and <strong>misleading pricing practices</strong>. Wholesale pricing frequently aligns with or exceeds retail market rates, undermining cost competitiveness, while the company artificially inflates "estimated retail prices" (ERPs) to create a false perception of discounts.
                </p>
                <p>
                    These patterns suggest <strong>structural inefficiencies in order processing and logistics</strong>, compounded by poor customer service responsiveness—a red flag for buyers dependent on just-in-time delivery. No verifiable data exists on production capacity, lead time metrics, or facility capabilities, limiting transparency into operational resilience.
                </p>

                <h4>Financial & Reputational Concerns</h4>
                <p>
                    While D&H holds <strong>high-value contracts</strong> (e.g., a <strong>$3M+ blanket purchase order</strong> with Florida International University for Apple resale in 2023), its <strong>reputational risk is elevated</strong> due to persistent customer complaints about pricing integrity and fulfillment failures. The absence of recent <strong>litigation records, regulatory violations, or data breaches</strong> offers no mitigating signal; instead, the <strong>lack of third-party audits or public financial disclosures</strong> obscures financial stability.
                </p>
                <p>
                    Given the <strong>active customer migration</strong> described in reviews, D&H’s market position appears vulnerable to competitors with stronger operational discipline.
                </p>
                <p><strong>Recommendation:</strong> Conduct a <strong>direct audit of order-to-delivery cycles</strong> and <strong>price benchmarking</strong> before engagement; explore alternative distributors for time-sensitive or cost-critical procurements.</p>
            </div>
        </section>

        <div class="references">
            <h3>References</h3>
            <ul>
                <li><a href="https://pangoly.com/en/price-history/msi-meg-x870e-godlike" target="_blank">MSI MEG X870E GODLIKE Price History - Pangoly</a></li>
                <li><a href="https://us-store.msi.com/MEG-X870E-GODLIKE" target="_blank">MSI Official Store - MEG X870E GODLIKE</a></li>
                <li><a href="https://www.cdw.com/product/msi-meg-x870e-godlike-gaming-desktop-motherboard-amd-x870e-chipset-sock/8236153" target="_blank">CDW Product Listing - MSI MEG X870E GODLIKE</a></li>
                <li><a href="https://videocardz.com/newz/msi-launches-1300-meg-x870e-godlike-x-edition-motherboard-limited-to-1000-units-for-godlikes-10th-anniversary" target="_blank">VideoCardz - MSI MEG X870E GODLIKE X Edition Launch</a></li>
                <li><a href="https://www.techpowerup.com/344087/msi-meg-x870e-godlike-x-edition-starts-selling-at-usd-1-300" target="_blank">TechPowerUp - MSI MEG X870E GODLIKE X Edition Pricing</a></li>
                <li><a href="https://www.msi.com/Motherboard/MEG-X870E-GODLIKE-X-EDITION" target="_blank">MSI Official Product Page - MEG X870E GODLIKE X Edition</a></li>
                <li><a href="https://pcpartpicker.com/product/pRLdnQ/msi-meg-x870e-godlike-eatx-am5-motherboard-meg-x870e-godlike" target="_blank">PCPartPicker - MSI MEG X870E GODLIKE</a></li>
                <li><a href="https://www.mediasourceinc.com/" target="_blank">Media Source Inc.</a></li>
                <li><a href="https://www.energy.gov/sites/default/files/2024-03/doe-fy-2025-budget-vol-4-v3.pdf" target="_blank">U.S. Department of Energy FY 2025 Budget</a></li>
                <li><a href="https://www.solidificationcourse.com/" target="_blank">Solidification Course</a></li>
                <li><a href="https://www.multybyte.com/blogs/from-moq-to-lead-time-faqs-for-first-time-buyers-of-bulk-electronics-in-india-from-multybyte" target="_blank">Multybyte - MOQ & Lead Time FAQs for Bulk Electronics Buyers</a></li>
                <li><a href="https://www.dandh.com/v4/view?pageReq=Press&cmsId=2024&int_cid=PRSS&utm_campaign=PR-2024" target="_blank">D&H Distributing Press Releases</a></li>
                <li><a href="https://insights.made-in-china.com/Understanding-MOQ-Minimum-Order-Quantity-in-Bulk-Orders_zGYtFvryaQDl.html" target="_blank">Made-in-China - Understanding MOQ in Bulk Orders</a></li>
                <li><a href="https://members.asicentral.com/research/end-buyer-research-series/" target="_blank">ASI Central - End Buyer Research Series</a></li>
                <li><a href="https://www.grantpud.org/templates/galaxy/images/2026-02-17_FYI_Packet.pdf" target="_blank">Grant PUD FYI Packet</a></li>
                <li><a href="https://www.yotpo.com/case-studies/bulk-case-study" target="_blank">Yotpo - Bulk Case Study</a></li>
                <li><a href="https://www.bbb.org/us/pa/lower-paxton/profile/video-equipment-manufacturers/d-h-distributing-company-0241-70005449/customer-reviews" target="_blank">BBB - D&H Distributing Customer Reviews</a></li>
                <li><a href="https://trustees.fiu.edu/_assets/docs/complete-e_agenda_ff_9.14.23-3-compressed.pdf" target="_blank">FIU Trustees - Contracts & Agreements</a></li>
                <li><a href="https://dojmt.gov/office-of-consumer-protection/reported-data-breaches/" target="_blank">Montana DOJ - Reported Data Breaches</a></li>
            </ul>
        </div>
    </div>

    <script>
        // Forecast Chart for MB-X870-AM5
        const forecastData = {
            dates: [
                "2026-04-28", "2026-04-29", "2026-04-30", "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07",
                "2026-05-08", "2026-05-09", "2026-05-10", "2026-05-11", "2026-05-12", "2026-05-13", "2026-05-14", "2026-05-15", "2026-05-16", "2026-05-17",
                "2026-05-18", "2026-05-19", "2026-05-20", "2026-05-21", "2026-05-22", "2026-05-23", "2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27"
            ],
            demand: [
                85, 103, 90, 92, 93, 91, 117, 116, 111, 93, 100, 120, 114, 110, 96, 88, 114, 98, 86, 101, 115, 112, 96, 111, 101, 101, 119, 106, 99, 100
            ]
        };

        const anomalyDates = ["2026-03-30", "2026-04-12", "2026-04-20"];
        const anomalyDemand = [null, null, null]; // No demand data for anomalies, just markers

        const forecastTrace = {
            x: forecastData.dates,
            y: forecastData.demand,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Forecasted Demand',
            line: { color: '#72BAA9', width: 3 }
        };

        const anomalyTrace = {
            x: anomalyDates,
            y: anomalyDemand,
            type: 'scatter',
            mode: 'markers',
            name: 'Anomalies',
            marker: { color: '#AE2448', size: 12, symbol: 'x' }
        };

        const layout = {
            title: '30-Day Demand Forecast for MSI MEG X870E GODLIKE',
            xaxis: { title: 'Date', gridcolor: '#f0f0f0' },
            yaxis: { title: 'Forecasted Demand (Units)', gridcolor: '#f0f0f0' },
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#ffffff',
            margin: { t: 40, b: 40, l: 40, r: 20 }
        };

        Plotly.newPlot('forecast-chart-MB-X870-AM5', [forecastTrace, anomalyTrace], layout);
    </script>
</body>
</html>
"""

    result = reorder_assessment_agent.invoke(
        {"report": mock_html_report, "messages": []}
    )

    print(f"Positive Points: {result['positive_points']}")
    print(f"Negative Points: {result['negative_points']}")
    print(f"SKU Data: {result['sku_level_data']}")
