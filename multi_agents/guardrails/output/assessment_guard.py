from pydantic import BaseModel, Field

class ReorderDecision(BaseModel):
    """Schema for the final reorder assessment decision."""
    reorder_status: bool = Field(description="Set to True if we should reorder from this supplier, False if we should not.")
    reasoning: str = Field(description="A 1-2 sentence explanation of why this decision was made based on the positive and negative critiques.")
