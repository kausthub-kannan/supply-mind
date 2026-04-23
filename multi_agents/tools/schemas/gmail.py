from pydantic import BaseModel, Field
from typing import Optional


class ReadEmailInput(BaseModel):
    count: int = Field(default=5, description="Number of recent emails to fetch.")
    unread_only: bool = Field(default=False, description="Only fetch unread emails.")
    folder: str = Field(default="INBOX", description="Folder to read from.")


class SendEmailInput(BaseModel):
    recipient: str = Field(description="Recipient email address.")
    subject: str = Field(description="Email subject line.")
    content: str = Field(description="Email body (plain text).")
    reply_to_message_id: Optional[str] = Field(
        default=None, description="Message-ID of the email you're replying to."
    )
    references: Optional[str] = Field(
        default=None,
        description="Full References header from the email chain (copy from read_email output).",
    )
