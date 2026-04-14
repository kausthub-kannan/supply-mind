from multi_agents.tools.search import web_search
from multi_agents.tools.gmail import send_email, read_email
from multi_agents.tools.db import sql_insert, sql_select, sql_update
from multi_agents.tools.file import upload_file

forecast_agent_toolkit = [sql_select]
anomaly_agent_toolkit = [sql_select]
report_generation_toolkit = [upload_file]
supplier_analysis_agent_toolkit = [web_search]
order_and_return_agent_toolkit = [send_email, read_email, sql_insert, sql_select, sql_update]

supervisor_workers = []
