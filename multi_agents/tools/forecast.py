import json
import os
import joblib
import pandas as pd
import xgboost as xgb
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from datetime import datetime, timedelta
from multi_agents.tools.db import db
from sqlalchemy import text

# Load models and encoders globally so they don't load on every function call
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
models_dir = os.path.join(base_dir, 'models')

# Try loading, but wrap in try-except in case they aren't generated yet
try:
    forecaster_model = xgb.XGBRegressor()
    forecaster_model.load_model(os.path.join(models_dir, 'forecaster_model.json'))
    forecaster_encoders = joblib.load(os.path.join(models_dir, 'forecaster_encoders.pkl'))
except Exception as e:
    forecaster_model = None
    forecaster_encoders = None

class ForecastSchema(BaseModel):
    sku_id: str = Field(description="The unique SKU identifier to generate the forecast for.")
    days: int = Field(default=30, description="Number of days to forecast into the future.")

@tool(args_schema=ForecastSchema)
def forecast_orders(sku_id: str, days: int = 30) -> str:
    """
    Forecast orders for given SKU based on historical data using XGBoost ML Model.
    """
    output = generate_forecast(sku_id, days)
    return json.dumps(output, indent=2)

def generate_forecast(sku_id: str, days: int = 30) -> dict:
    if forecaster_model is None or forecaster_encoders is None:
        return {"error": "Machine Learning models not found in models/ directory. Run the training scripts first."}

    try:
        # Fetch the most recent context for this SKU from the DB
        query = f"SELECT * FROM history_logs WHERE sku_id = '{sku_id}' ORDER BY date DESC LIMIT 1"
        
        with db._engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        if df.empty:
            return {"error": f"No historical data found in database for SKU: {sku_id}"}
        
        current_stock = int(df['closing_stock'].iloc[0])
        
        # Prepare features exactly as the model expects
        drop_cols = ['log_id', 'date', 'units_sold', 'anomaly_class', 'anomaly_label']
        features = [col for col in df.columns if col not in drop_cols]
        X = df[features].copy()

        # Encode categorical columns safely
        categorical_cols = ['sku_id', 'region', 'season', 'category', 'specs_level', 'supplier_id']
        for col in categorical_cols:
            if col in X.columns:
                val = str(X[col].iloc[0])
                # Safe transform: Catch unseen label error
                if val not in forecaster_encoders[col].classes_:
                    return {"error": f"I cannot forecast for {col} '{val}' because I have no historical training data for it."}
                X[col] = forecaster_encoders[col].transform([val])

        # Predict baseline daily demand for this SKU using XGBoost!
        predicted_daily_demand = float(forecaster_model.predict(X)[0])
        
        import random
        forecast_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_date = datetime.now() + timedelta(days=1)
        forecast_list = []

        projected_inventory = current_stock
        reorder_point = 100
        buffer_days = 5

        low_inventory_date = None
        expected_delivery_date = None

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            # Baseline ML prediction + tiny day-to-day noise for realism
            demand = max(0, int(predicted_daily_demand + random.randint(-5, 5)))
            projected_inventory -= demand

            if projected_inventory <= reorder_point and low_inventory_date is None:
                low_inventory_date = current_date
                delivery_dt_obj = low_inventory_date - timedelta(days=buffer_days)
                expected_delivery_date = delivery_dt_obj.strftime("%Y-%m-%d")

            forecast_list.append(
                {"date": current_date.strftime("%Y-%m-%d"), "forecasted_demand": demand}
            )

        return {
            "sku_id": sku_id,
            "forecast_generated_at": forecast_date,
            "forecast_horizon_days": days,
            "delivery_date": expected_delivery_date,
            "data": forecast_list,
            "order_quantity": sum([fd["forecasted_demand"] for fd in forecast_list]),
            "ml_model_used": "XGBoost Regressor"
        }

    except Exception as e:
        return {"error": f"Failed to generate forecast: {str(e)}"}
