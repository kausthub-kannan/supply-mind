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
def create_donut_plot(labels: List[str], values: List[float], title: str) -> str:
    """
    Creates a donut plot to show proportional data (parts of a whole)
    :param labels: List[str] - The list of category labels for the plot slices
    :param values: List[float] - The numerical values corresponding to each label
    :param title: str - The title to be displayed on the chart
    :return: str - HTML string containing the Plotly chart with CDN dependencies
    """
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
) -> str:
    """
    Creates a line chart to show trends over time or ordered categories
    :param x_data: List[Any] - Data for the x-axis (e.g., dates or categories)
    :param y_data: List[float] - Numerical data for the y-axis
    :param x_label: str - The label to display for the x-axis
    :param y_label: str - The label to display for the y-axis
    :param title: str - The title to be displayed on the chart
    :return: str - HTML string containing the Plotly chart with CDN dependencies
    """
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
) -> str:
    """
    Creates a scatter plot to identify correlations or outliers between two numerical variables.
    :param x_data: List[float] - Numerical data for the x-axis
    :param y_data: List[float] - Numerical data for the y-axis
    :param x_label: str - The label to display for the x-axis
    :param y_label: str - The label to display for the y-axis
    :param title: str - The title to be displayed on the chart
    :return: str - HTML string containing the Plotly chart with CDN dependencies
    """
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
) -> str:
    """
    Creates a dual-axis chart with a primary bar chart and a secondary line chart overlay.
    :param x_data: List[str] - The common x-axis labels for both charts
    :param bar_y_data: List[float] - The numerical values for the bar chart (primary y-axis)
    :param line_y_data: List[float] - The numerical values for the line chart (secondary y-axis)
    :param bar_name: str - The legend name for the bar chart
    :param line_name: str - The legend name for the line chart
    :param title: str - The title to be displayed on the chart
    :return: str - HTML string containing the Plotly chart with CDN dependencies
    """
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
    reference_value: Optional[float] = None,
    prefix: str = "",
) -> str:
    """
    Creates a KPI Banner/Indicator to display high-level summary metrics, optionally with a reference delta.
    :param kpi_name: str - The name or label of the KPI being tracked
    :param kpi_value: float - The current metric value to display
    :param reference_value: Optional[float] - A value to compare against (e.g., target or previous period), defaults to None
    :param prefix: str - A string prefix for the metric (e.g., currency symbol), defaults to an empty string
    :return: str - HTML string containing the Plotly chart with CDN dependencies
    """
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
    """
    Creates a step chart to visualize changes occurring at distinct intervals.
    :param x_data: List[Any] - Data for the x-axis representing the intervals
    :param y_data: List[float] - Numerical data representing the levels/values at those intervals
    :param title: str - The title to be displayed on the chart
    :param output_path: str - The path where the generated chart should be stored (Note: function currently returns HTML)
    :return: str - HTML string containing the Plotly chart with CDN dependencies
    """
    try:
        fig = go.Figure(data=go.Scatter(x=x_data, y=y_data, mode="lines"))
        fig.update_layout(title=title)
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    except Exception as e:
        return f"Error creating step chart: {str(e)}"
