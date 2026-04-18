from pydantic import BaseModel, Field
from typing import List, Any, Optional


class DonutPlotSchema(BaseModel):
    labels: List[str] = Field(
        description="List of category labels for the donut chart."
    )
    values: List[float] = Field(
        description="List of numerical values corresponding to the labels."
    )
    title: str = Field(description="Title of the donut plot.")


class LineChartSchema(BaseModel):
    x_data: List[Any] = Field(
        description="List of X-axis data points (e.g., dates or categories)."
    )
    y_data: List[float] = Field(description="List of Y-axis data points.")
    x_label: str = Field(description="Label for the X-axis.")
    y_label: str = Field(description="Label for the Y-axis.")
    title: str = Field(description="Title of the line chart.")


class ScatterPlotSchema(BaseModel):
    x_data: List[float] = Field(description="List of numerical X-axis data points.")
    y_data: List[float] = Field(description="List of numerical Y-axis data points.")
    x_label: str = Field(description="Label for the X-axis.")
    y_label: str = Field(description="Label for the Y-axis.")
    title: str = Field(description="Title of the scatter plot.")


class DualAxisBarSchema(BaseModel):
    x_data: List[str] = Field(description="List of X-axis categories.")
    bar_y_data: List[float] = Field(
        description="Data for the primary Y-axis (represented as bars)."
    )
    line_y_data: List[float] = Field(
        description="Data for the secondary Y-axis (represented as a line)."
    )
    bar_name: str = Field(description="Legend name for the bar data.")
    line_name: str = Field(description="Legend name for the line data.")
    title: str = Field(description="Title of the dual-axis chart.")


class KPIBannerSchema(BaseModel):
    kpi_name: str = Field(
        description="The name or title of the KPI (e.g., 'Total Revenue')."
    )
    kpi_value: float = Field(description="The primary numerical value to display.")
    reference_value: Optional[float] = Field(
        default=None, description="Optional previous value to calculate a delta/trend."
    )
    prefix: str = Field(default="", description="Prefix for the value (e.g., '$').")


class StepChartSchema(BaseModel):
    x_data: List[Any] = Field(
        description="List of X-axis data points (e.g., time series)."
    )
    y_data: List[float] = Field(description="List of Y-axis data points.")
    title: str = Field(description="Title of the step chart.")
