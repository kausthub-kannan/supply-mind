from typing import Any, Optional
from pydantic import BaseModel, Field

MAX_ROWS = 500


class SelectInput(BaseModel):
    table: str = Field(..., description="Table to query.")
    columns: list[str] = Field(default=["*"], description="Columns to fetch.")
    where: Optional[str] = Field(None, description="Raw WHERE clause, e.g. 'age > 30'.")
    params: Optional[list] = Field(
        None, description="Positional params for the WHERE clause."
    )
    order_by: Optional[str] = Field(None, description="ORDER BY expression.")
    limit: int = Field(50, description=f"Max rows (hard cap {MAX_ROWS}).", ge=1)


class InsertInput(BaseModel):
    table: str = Field(..., description="Target table.")
    rows: list[dict] = Field(
        ..., description="List of {column: value} dicts to insert."
    )
    returning: list[str] = Field(
        default=[], description="Columns to return after insert."
    )
    on_conflict: Optional[str] = Field(
        None, description="ON CONFLICT clause, e.g. 'DO NOTHING'."
    )


class UpdateInput(BaseModel):
    table: str = Field(..., description="Target table.")
    values: dict[str, Any] = Field(..., description="{column: new_value} pairs.")
    where: str = Field(
        ..., description="WHERE clause (required – never update entire table)."
    )
    params: Optional[list] = Field(
        None, description="Extra positional params appended after SET values."
    )
    returning: list[str] = Field(
        default=[], description="Columns to return after update."
    )
