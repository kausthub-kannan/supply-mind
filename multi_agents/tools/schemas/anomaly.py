from pydantic import BaseModel, Field
from typing import List


class AnomalySchema(BaseModel):
    sku_ids: List[str] = Field(
        description="List of unique SKU identifier to check for historical anomalies."
    )
    lookback_days: int = Field(
        default=30, description="Number of past days to analyze."
    )
