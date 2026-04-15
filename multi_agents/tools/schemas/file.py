from typing import Optional
from pydantic import BaseModel, Field


class UploadInput(BaseModel):
    key: str = Field(description="Unique identifier or destination key for the upload.")
    content: str = Field(description="Content to be processed.")
    content_type: Optional[str] = Field(
        description="The MIME type of the content (e.g., 'text/csv')."
    )
