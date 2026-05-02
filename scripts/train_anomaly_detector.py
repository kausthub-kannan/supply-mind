import os
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score

def main():
    print("Loading data for Anomaly Detection...")
    df = pd.read_csv('../inventory_logs.csv')

    # Target is anomaly_label (e.g. 'normal', 'demand_spike')
    target = 'anomaly_label'
    
    # We drop columns we shouldn't train on
    # 'anomaly_class' is dropped because it's just the integer version of our target
    drop_cols = ['log_id', 'date', 'anomaly_class', 'anomaly_label']
    features = [col for col in df.columns if col not in drop_cols]

    X = df[features].copy()
    y = df[target]

    # Encode categorical text into numbers for XGBoost
    categorical_cols = ['sku_id', 'region', 'season', 'category', 'specs_level', 'supplier_id']
    
    for col in categorical_cols:
        if col in X.columns:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))

    # For classification, a random split is standard to ensure all classes are represented
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"Training on {len(X_train)} logs, Testing on {len(X_test)} logs...")

    # XGBoost requires the target labels to be integers from 0 to num_classes-1
    le_y = LabelEncoder()
    y_train_enc = le_y.fit_transform(y_train)
    y_test_enc = le_y.transform(y_test)

    # Train XGBoost Classifier
    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42,
        eval_metric='mlogloss'
    )
    
    model.fit(X_train, y_train_enc)

    # Make predictions and convert them back to text labels
    predictions_enc = model.predict(X_test)
    predictions = le_y.inverse_transform(predictions_enc)
    
    # Evaluate Accuracy and Precision
    accuracy = accuracy_score(y_test, predictions)

    print("\n--- Anomaly Detector Performance ---")
    print(f"Overall Accuracy: {accuracy * 100:.2f}%\n")
    
    # Classification report shows Precision, Recall, and F1-Score for EACH anomaly type
    print("Detailed Precision & Recall Report:")
    print(classification_report(y_test, predictions, zero_division=0))

    # Save the model
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, 'anomaly_detector.json')
    model.save_model(model_path)
    print(f"\nModel successfully saved to {model_path}")

if __name__ == "__main__":
    main()
