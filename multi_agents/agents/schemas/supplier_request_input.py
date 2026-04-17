from pydantic import BaseModel, Field, field_validator


class SupplierRequestInputs(BaseModel):
    sku_name: str = Field(..., description="The exact SKU name or identifier")
    order_quantity: int = Field(
        ..., gt=0, description="Order quantity must be greater than 0"
    )
    delivery_date: str = Field(..., description="Expected delivery date")
    suppliers_list: list[str] = Field(
        default_factory=list, description="List of target suppliers to analyze"
    )

    @field_validator("suppliers_list")
    def check_suppliers(cls, v):
        if not v:
            raise ValueError("At least one supplier must be provided.")
        return v
