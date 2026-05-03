import json
import os
import joblib
import pandas as pd
import xgboost as xgb
from langchain_core.tools import tool
from datetime import datetime, timedelta
from multi_agents.tools.schemas.anomaly import AnomalySchema
from multi_agents.tools.db import db
from sqlalchemy import text

# Load models and encoders globally
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
models_dir = os.path.join(base_dir, 'models')

try:
    anomaly_model = xgb.XGBClassifier()
    anomaly_model.load_model(os.path.join(models_dir, 'anomaly_detector.json'))
    anomaly_encoders = joblib.load(os.path.join(models_dir, 'anomaly_encoders.pkl'))
except Exception as e:
    anomaly_model = None
    anomaly_encoders = None

@tool(args_schema=AnomalySchema)
def anomaly_detection(sku_id: str, lookback_days: int = 30) -> str:
    """
    Tool used to detect statistical anomalies for a given SKU using XGBoost.
    """
    output = detect_anomalies(sku_id, lookback_days)
    return json.dumps(output, indent=2)

def detect_anomalies(sku_id: str, lookback_days: int = 30) -> dict:
    if anomaly_model is None or anomaly_encoders is None:
        return {"error": "Machine Learning models not found in models/ directory. Run the training scripts first."}

    try:
        # Fetch the last N days of data for this SKU
        query = f"SELECT * FROM history_logs WHERE sku_id = '{sku_id}' ORDER BY date DESC LIMIT {lookback_days}"
        
        with db._engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        if df.empty:
            return {"error": f"No historical data found in database for SKU: {sku_id}"}
        
        # Prepare features exactly as the model expects
        drop_cols = ['log_id', 'date', 'anomaly_class', 'anomaly_label']
        features = [col for col in df.columns if col not in drop_cols]
        X = df[features].copy()

        # Encode categorical columns safely
        categorical_cols = ['sku_id', 'region', 'season', 'category', 'specs_level', 'supplier_id']
        feature_encoders = anomaly_encoders['features']
        target_encoder = anomaly_encoders['target']
        
        for col in categorical_cols:
            if col in X.columns:
                def safe_encode(val):
                    val_str = str(val)
                    if val_str not in feature_encoders[col].classes_:
                        return -1 
                    return feature_encoders[col].transform([val_str])[0]
                
                X[col] = X[col].apply(safe_encode)
                
                if -1 in X[col].values:
                     return {"error": f"I cannot detect anomalies because an unknown '{col}' was found in the database."}

        # Predict anomaly classes for all rows using XGBoost!
        predictions_enc = anomaly_model.predict(X)
        predictions_labels = target_encoder.inverse_transform(predictions_enc)
        
        # Build the final list of anomalies
        anomalies_list = []
        
        for idx, label in enumerate(predictions_labels):
            if label != "normal":
                row_date = df['date'].iloc[idx]
                anomalies_list.append({
                    "date": str(row_date),
                    "anomaly_type": label,
                    "severity": "High" if label in ["supply_disruption", "demand_spike"] else "Medium",
                    "requires_human_review": True,
                    "description": f"XGBoost ML Model detected statistical deviation matching a '{label}' profile."
                })

        anomalies_list.sort(key=lambda x: x["date"])

        return {
            "sku_id": sku_id,
            "lookback_window": lookback_days,
            "total_anomalies_found": len(anomalies_list),
            "anomalies": anomalies_list,
            "ml_model_used": "XGBoost Classifier"
        }

    except Exception as e:
        return {"error": f"Failed to detect anomalies: {str(e)}"}
