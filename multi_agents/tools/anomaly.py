import json
import random
from datetime import datetime, timedelta
from langchain_core.tools import tool
from multi_agents.tools.schemas.anomaly import AnomalySchema


@tool(args_schema=AnomalySchema)
def anomaly_detection(sku_id: str, lookback_days: int = 30) -> str:
    """
    Tool used to detect
    :param sku_id:
    :param lookback_days:
    :return:
    """
    output = detect_anomalies(sku_id, lookback_days)
    return json.dumps(output, indent=2)


def detect_anomalies(sku_id: str, lookback_days: int = 30) -> dict:
    try:
        start_date = datetime.now() - timedelta(days=lookback_days)
        anomaly_types = [
            "Demand Spikes",
            "Supply Anomalies",
            "Return Rates",
            "Price-Demand",
            "Stock Balance",
        ]

        # Randomly generate 1 to 4 anomalies for realism
        num_anomalies = random.randint(1, 4)
        anomalies_list = []

        for _ in range(num_anomalies):
            # Pick a random day in the lookback window
            event_day = random.randint(1, lookback_days)
            event_date = start_date + timedelta(days=event_day)
            a_type = random.choice(anomaly_types)

            anomalies_list.append(
                {
                    "date": event_date.strftime("%Y-%m-%d"),
                    "anomaly_type": a_type,
                    "severity": random.choice(["Low", "Medium", "High", "Critical"]),
                    "requires_human_review": random.choice(
                        [True, True, False]
                    ),  # Weighted toward True
                    "description": f"Statistical deviation detected matching a '{a_type}' profile.",
                }
            )

        # Sort the anomalies chronologically
        anomalies_list.sort(key=lambda x: x["date"])

        output_dict = {
            "sku_id": sku_id,
            "lookback_window": lookback_days,
            "total_anomalies_found": num_anomalies,
            "anomalies": anomalies_list,
        }

        return output_dict

    except Exception as e:
        return {"error": f"Failed to detect anomalies: {str(e)}"}
