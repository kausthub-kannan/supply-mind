from pydantic import BaseModel, Field


class AnomalySchema(BaseModel):
    sku_id: str = Field(description="SKU identifier to check for historical anomalies.")
    lookback_days: int = Field(
        default=30, description="Number of past days to analyze."
    )
