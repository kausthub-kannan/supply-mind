from multi_agents.tools.search import web_search
from multi_agents.tools.gmail import send_email, read_email
from multi_agents.tools.db import list_tables_tool, get_schema_tool, safe_execute_query
from multi_agents.tools.reports.html import data_card, data_table
from multi_agents.tools.reports.graph import (
    create_donut_plot,
    create_scatter_plot,
    create_kpi_banner,
    create_line_chart,
    create_step_chart,
    create_dual_axis_chart,
)
from multi_agents.tools.forecast import forecast_orders
from multi_agents.tools.anomaly import anomaly_detection

report_generation_toolkit = [
    create_donut_plot,
    create_scatter_plot,
    create_kpi_banner,
    create_line_chart,
    create_step_chart,
    create_dual_axis_chart,
    data_card,
    data_table,
]
supplier_analysis_agent_toolkit = [web_search]
order_and_return_agent_toolkit = [
    send_email,
    read_email,
    list_tables_tool,
    get_schema_tool,
    safe_execute_query,
]

supervisor_toolkit = [list_tables_tool, get_schema_tool, safe_execute_query]

tool_maps = {
    "web_search": web_search,
    "forecast_orders": forecast_orders,
    "anomaly_detection": anomaly_detection,
    "create_donut_plot": create_donut_plot,
    "create_scatter_plot": create_scatter_plot,
    "create_kpi_banner": create_kpi_banner,
    "create_line_chart": create_line_chart,
    "create_step_chart": create_step_chart,
    "create_dual_axis_chart": create_dual_axis_chart,
    "data_card": data_card,
    "data_table": data_table,
    "send_email": send_email,
    "read_email": read_email,
    "list_tables_tool": list_tables_tool,
    "get_schema_tool": get_schema_tool,
    "safe_execute_query": safe_execute_query,
}
