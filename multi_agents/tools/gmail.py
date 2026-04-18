import os
from typing import Optional

import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

from langchain.tools import tool
from multi_agents.tools.schemas.gmail import SendEmailInput, ReadEmailInput

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")


@tool(
    args_schema=SendEmailInput,
    description="Send or reply to an email via Gmail. Pass references for correct threading.",
)
def send_email(
    recipient: str,
    subject: str,
    content: str,
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
) -> str:
    """

    :param recipient:
    :param subject:
    :param content:
    :param reply_to_message_id:
    :param references:
    :return:
    """
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        return "Error: GMAIL_EMAIL and GMAIL_PASSWORD env vars not set."

    if reply_to_message_id and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    msg = MIMEMultipart()
    msg["From"] = GMAIL_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject

    if reply_to_message_id:
        msg["In-Reply-To"] = reply_to_message_id
        if references:
            chain = (
                references
                if reply_to_message_id in references
                else f"{references} {reply_to_message_id}"
            )
        else:
            chain = reply_to_message_id

        msg["References"] = chain

    msg.attach(MIMEText(content, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            server.sendmail(GMAIL_EMAIL, recipient, msg.as_string())
        return f"✅ Email sent to {recipient}."
    except Exception as e:
        return f"❌ Failed to send: {e}"


@tool(
    args_schema=ReadEmailInput,
    description="Read recent emails from Gmail. Returns Message-ID and References — pass both to send_email for correct threading.",
)
def read_email(count: int = 5, unread_only: bool = False, folder: str = "INBOX") -> str:
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        return "Error: GMAIL_EMAIL and GMAIL_PASSWORD env vars not set."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select(folder)

        criteria = "UNSEEN" if unread_only else "ALL"
        _, data = mail.search(None, criteria)
        ids = data[0].split()

        if not ids:
            return "No emails found."

        results = []
        for uid in reversed(ids[-count:]):
            _, msg_data = mail.fetch(uid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            raw_subject, enc = decode_header(msg["Subject"] or "No Subject")[0]
            subject = (
                raw_subject.decode(enc or "utf-8", errors="replace")
                if isinstance(raw_subject, bytes)
                else raw_subject
            )

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and not part.get(
                        "Content-Disposition"
                    ):
                        body = part.get_payload(decode=True).decode(errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="replace")

            snippet = body[:400] + ("..." if len(body) > 400 else "")

            # ↓ References is the key addition — needed for thread chaining
            results.append(
                f"---\n"
                f"From:       {msg.get('From')}\n"
                f"Date:       {msg.get('Date')}\n"
                f"Subject:    {subject}\n"
                f"Message-ID: {msg.get('Message-ID', 'N/A')}\n"
                f"References: {msg.get('References', 'N/A')}\n"
                f"Body:\n{snippet}"
            )

        mail.logout()
        return "\n\n".join(results)

    except Exception as e:
        return f"Failed to read email: {e}"
