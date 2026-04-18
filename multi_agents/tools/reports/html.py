from langchain_core.tools import tool
from typing import List, Dict


@tool
def data_card(title: str, content: str) -> str:
    """
    Creates an HTML string for a data card to highlight a specific metric or insight.
    """
    try:
        html = f"""
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-family: sans-serif;">
            <h3 style="margin-top: 0; margin-bottom: 10px; color: #333333; font-size: 1.2em;">{title}</h3>
            <p style="margin: 0; color: #555555; line-height: 1.5;">{content}</p>
        </div>
        """
        return html
    except Exception as e:
        return f"<p>Error generating data card: {str(e)}</p>"


@tool
def data_table(columns: List[str], data: List[Dict[str, str]]) -> str:
    """
    Creates an HTML string for a data table given a list of column names and a list of row dictionaries.
    """
    try:
        # Construct the table headers
        headers_html = "".join(
            [
                f'<th style="border-bottom: 2px solid #ddd; padding: 12px 8px; background-color: #f8f9fa; text-align: left; color: #333; font-weight: bold;">{col}</th>'
                for col in columns
            ]
        )

        # Construct the table rows
        rows_html = ""
        for row in data:
            # .get(col, "") ensures that if a key is missing in the dict, it renders an empty cell rather than crashing
            row_cells = "".join(
                [
                    f'<td style="border-bottom: 1px solid #ddd; padding: 12px 8px; color: #555;">{row.get(col, "")}</td>'
                    for col in columns
                ]
            )
            rows_html += f"<tr>{row_cells}</tr>"

        # Assemble the final table
        html = f"""
        <div style="overflow-x: auto; font-family: sans-serif; margin-bottom: 20px;">
            <table style="border-collapse: collapse; width: 100%; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <thead>
                    <tr>{headers_html}</tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """
        return html
    except Exception as e:
        return f"<p>Error generating data table: {str(e)}</p>"
