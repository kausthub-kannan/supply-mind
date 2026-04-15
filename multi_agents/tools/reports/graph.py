import plotly.graph_objects as go
from plotly.subplots import make_subplots
from langchain_core.tools import tool
from typing import List, Any, Optional
from multi_agents.tools.schemas.graph import (
    DonutPlotSchema,
    LineChartSchema,
    ScatterPlotSchema,
    DualAxisBarSchema,
    KPIBannerSchema,
    StepChartSchema,
)


@tool(args_schema=DonutPlotSchema)
def create_donut_plot(
    labels: List[str], values: List[float], title: str, output_path: str
) -> str:
    """Creates a donut plot to show proportional data (parts of a whole) and saves it to a file."""
    try:
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
        fig.update_layout(title_text=title)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating donut plot: {str(e)}"


@tool(args_schema=LineChartSchema)
def create_line_chart(
    x_data: List[Any],
    y_data: List[float],
    x_label: str,
    y_label: str,
    title: str,
    output_path: str,
) -> str:
    """Creates a line chart to show trends over time or ordered categories and saves it to a file."""
    try:
        fig = go.Figure(data=go.Scatter(x=x_data, y=y_data, mode="lines+markers"))
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating line chart: {str(e)}"


@tool(args_schema=ScatterPlotSchema)
def create_scatter_plot(
    x_data: List[float],
    y_data: List[float],
    x_label: str,
    y_label: str,
    title: str,
    output_path: str,
) -> str:
    """Creates a scatter plot to identify correlations or outliers between two numerical variables."""
    try:
        fig = go.Figure(data=go.Scatter(x=x_data, y=y_data, mode="markers"))
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating scatter plot: {str(e)}"


@tool(args_schema=DualAxisBarSchema)
def create_dual_axis_chart(
    x_data: List[str],
    bar_y_data: List[float],
    line_y_data: List[float],
    bar_name: str,
    line_name: str,
    title: str,
    output_path: str,
) -> str:
    """Creates a dual-axis chart with a primary bar chart and a secondary line chart overlay."""
    try:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(x=x_data, y=bar_y_data, name=bar_name),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=x_data, y=line_y_data, name=line_name, mode="lines+markers"),
            secondary_y=True,
        )

        fig.update_layout(title_text=title)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating dual-axis chart: {str(e)}"


@tool(args_schema=KPIBannerSchema)
def create_kpi_banner(
    kpi_name: str,
    kpi_value: float,
    output_path: str,
    reference_value: Optional[float] = None,
    prefix: str = "",
) -> str:
    """Creates a KPI Banner/Indicator to display high-level summary metrics, optionally with a reference delta."""
    try:
        mode = "number+delta" if reference_value is not None else "number"

        indicator = go.Indicator(
            mode=mode,
            value=kpi_value,
            title={"text": kpi_name},
            number={"prefix": prefix},
            delta=(
                {"reference": reference_value, "relative": True}
                if reference_value
                else None
            ),
        )

        fig = go.Figure(indicator)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating KPI banner: {str(e)}"


@tool(args_schema=StepChartSchema)
def create_step_chart(
    x_data: List[Any], y_data: List[float], title: str, output_path: str
) -> str:
    """Creates a step chart to visualize changes occurring at distinct intervals (e.g., inventory levels, expected lead times)."""
    try:
        fig = go.Figure(data=go.Scatter(x=x_data, y=y_data, mode="lines"))
        fig.update_layout(title=title)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating step chart: {str(e)}"
