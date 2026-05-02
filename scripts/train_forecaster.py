import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error

def main():
    print("Loading data...")
    # Load the inventory logs
    df = pd.read_csv('../inventory_logs.csv')

    # For a real forecasting model, you want to sort by date to prevent data leakage 
    # (predicting the past using future data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Define features and target
    # We want to forecast 'units_sold'
    target = 'units_sold'
    
    # We drop 'log_id', 'date', 'units_sold' (target), and the anomaly labels 
    # (since in the future, we won't know if it's an anomaly yet when forecasting)
    drop_cols = ['log_id', 'date', 'units_sold', 'anomaly_class', 'anomaly_label']
    features = [col for col in df.columns if col not in drop_cols]

    X = df[features].copy()
    y = df[target]

    print(f"Features used for forecasting: {features}")

    # Encode categorical columns
    categorical_cols = ['sku_id', 'region', 'season', 'category', 'specs_level', 'supplier_id']
    encoders = {}

    for col in categorical_cols:
        if col in X.columns:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            encoders[col] = le

    # Chronological train-test split (80% past data to train, 20% future data to test)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"Training on {len(X_train)} logs, Testing on {len(X_test)} logs...")

    # Initialize and train the XGBoost Regressor
    # objective='reg:squarederror' is standard for forecasting continuous values
    model = xgb.XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        objective='reg:squarederror',
        random_state=42
    )

    model.fit(X_train, y_train)

    # Evaluate the model
    predictions = model.predict(X_test)
    
    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))

    print("\n--- Model Performance ---")
    print(f"Mean Absolute Error (MAE): {mae:.2f} units")
    print(f"Root Mean Squared Error (RMSE): {rmse:.2f} units")
    print("(This means on average, our forecast is off by roughly this many units)")

    # Show a few sample predictions vs actuals
    print("\n--- Sample Predictions ---")
    results = pd.DataFrame({
        'Actual_Units_Sold': y_test.values,
        'Predicted_Units_Sold': np.round(predictions)
    })
    print(results.head())

    # Save the model
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, 'forecaster_model.json')
    model.save_model(model_path)
    print(f"\nModel successfully saved to {model_path}")

if __name__ == "__main__":
    main()
