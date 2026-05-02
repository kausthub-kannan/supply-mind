# Supply Mind - Forecasting and Anomaly Detection Models

## Overview
This document summarizes the development of the predictive models for the `supply-mind` inventory management system. We developed two separate global supervised machine learning models using XGBoost to handle both forecasting and anomaly detection.

## 1. Forecasting Model (`train_forecaster.py`)
**Objective**: Predict the future `units_sold` for any given SKU.
**Model Selected**: `XGBRegressor` (XGBoost Regressor)
**Why Selected**: Handled the small, tabular dataset better than univariate models (like Prophet) by learning global cross-SKU patterns from contextual features.

**Features Used**:
- `sku_id`, `region`, `season`, `category`, `specs_level`, `supplier_id` (Categorical, Label Encoded)
- `opening_stock`, `units_received`, `units_returned`, `closing_stock`, `price`, `period_days` (Numerical)

**Training Strategy**:
- Data sorted chronologically.
- 80% Train / 20% Test split.
- Objective: `reg:squarederror`.

**Performance**:
- **Mean Absolute Error (MAE)**: ~24.90 units
- **Root Mean Squared Error (RMSE)**: ~32.40 units
- *Note*: Attempts to add time-series lag features (like rolling averages) resulted in overfitting due to the small dataset size (323 rows). The simpler base model performed better.

---

## 2. Anomaly Detection Model (`train_anomaly_detector.py`)
**Objective**: Categorize the state of the supply chain (`normal`, `demand_spike`, `high_returns`, `supply_disruption`, `price_anomaly`).
**Model Selected**: `XGBClassifier` (XGBoost Classifier)
**Why Selected**: Leverages the explicit labels provided in the dataset to build a highly accurate supervised classifier.

**Features Used**: Same as the Forecaster.

**Training Strategy**:
- Random 80% Train / 20% Test split (to ensure rare anomaly classes are distributed).
- Target labels encoded using `LabelEncoder`.

**Performance**:
- **Overall Accuracy**: 92.31%
- **Precision (Anomalies)**: 100% (Zero false alarms; when the model flags a crisis, it is always right).
- **Recall (Anomalies)**: ~65% (The model is conservative and occasionally misses an anomaly, classifying it as 'normal').

---

## Future Enhancements
1. **Data Augmentation (SMOTE)**: The dataset is heavily imbalanced towards 'normal' logs. Generating synthetic anomaly data will improve the recall score.
2. **More Data**: The primary bottleneck is the low volume of data (~323 rows). Gathering daily logs for at least a full year will unlock the ability to use powerful time-series lag features.
3. **Hyperparameter Tuning**: Implementing GridSearch to find the optimal `max_depth` and `learning_rate` for the XGBoost models.
4. **Model Serialization**: Models are serialized and saved in this `models/` directory for fast inference by the agent workflows.
