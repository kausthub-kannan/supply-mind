import os
import imaplib
import email
import smtplib
import time
import re
from email.header import decode_header
from email.utils import make_msgid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any

from langchain.tools import tool
from multi_agents.tools.schemas.gmail import SendEmailInput, ReadEmailInput

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")


def _get_gmail_thread_id(imap_uid: bytes, mail: imaplib.IMAP4_SSL) -> Optional[str]:
    """Extract Gmail's internal X-GM-THRID for a given IMAP UID."""
    _, data = mail.fetch(imap_uid, "(X-GM-THRID)")
    if data and data[0]:
        match = re.search(rb"X-GM-THRID (\d+)", data[0])
        if match:
            return match.group(1).decode()
    return None


def _recover_sent_message(subject: str, retries: int = 5) -> Dict[str, str]:
    """
    After sending, connect to Sent Mail and recover both the real
    Message-ID and the Gmail thread ID (X-GM-THRID).
    Returns dict with keys: message_id, gmail_thread_id
    """
    safe_subject = subject.replace('"', "")

    for attempt in range(retries):
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            # Folder name has a space — must be quoted
            mail.select('"[Gmail]/Sent Mail"')

            _, data = mail.search(None, f'HEADER "Subject" "{safe_subject}"')
            ids = data[0].split()

            if ids:
                uid = ids[-1]  # most recent match

                # Fetch real Message-ID
                _, msg_data = mail.fetch(uid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                real_message_id = msg.get("Message-ID", "").strip()

                # Fetch Gmail thread ID
                gmail_thread_id = _get_gmail_thread_id(uid, mail)

                mail.logout()

                if real_message_id:
                    return {
                        "message_id": real_message_id,
                        "gmail_thread_id": gmail_thread_id or "",
                    }

            mail.logout()
        except Exception as e:
            print(f"[_recover_sent_message] attempt {attempt + 1} failed: {e}")

        time.sleep(2)

    return {"message_id": "", "gmail_thread_id": ""}


@tool(
    args_schema=SendEmailInput,
    description=(
        "Send or reply to an email via Gmail. "
        "Returns message_id and gmail_thread_id for thread tracking."
    ),
)
def send_email(
    recipient: str,
    subject: str,
    content: str,
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
) -> Dict[str, Any]:
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        return {"status": "error", "message": "Env vars not set."}

    if reply_to_message_id and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    msg = MIMEMultipart()
    msg["From"] = GMAIL_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject
    # Gmail will overwrite this, but set it anyway for the SMTP handshake
    msg["Message-ID"] = make_msgid(domain="gmail.com")

    if reply_to_message_id:
        clean_reply_id = reply_to_message_id.strip()
        msg["In-Reply-To"] = clean_reply_id
        msg["References"] = (
            f"{references} {clean_reply_id}".strip() if references else clean_reply_id
        )

    msg.attach(MIMEText(content, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            server.sendmail(GMAIL_EMAIL, recipient, msg.as_string())
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # Recover the real IDs Gmail assigned after relay
    recovered = _recover_sent_message(subject)

    return {
        "status": "success",
        "message": f"Email sent to {recipient}",
        "gmail_thread_id": recovered["gmail_thread_id"],  # use this in read_email
    }


@tool(
    args_schema=ReadEmailInput,
    description=(
        "Read emails from Gmail. "
        "Pass gmail_thread_id (numeric) to fetch an entire thread reliably. "
        "Leave blank to see recent inbox messages."
    ),
)
def read_email(
    count: int = 5,
    unread_only: bool = True,
    gmail_thread_id: Optional[str] = None,  # numeric X-GM-THRID
) -> str:
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        return "Error: GMAIL_EMAIL and GMAIL_PASSWORD env vars not set."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)

        if gmail_thread_id:
            # X-GM-THRID fetches ALL messages in the thread across folders
            mail.select('"[Gmail]/All Mail"')
            criteria = f"X-GM-THRID {gmail_thread_id}"
        else:
            mail.select("INBOX")
            criteria = "UNSEEN" if unread_only else "ALL"

        _, data = mail.search(None, criteria)
        ids = data[0].split()

        if not ids:
            return f"No emails found for criteria: {criteria}"

        target_ids = ids if gmail_thread_id else list(reversed(ids[-count:]))

        results = []
        for uid in target_ids:
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
                    if (
                        part.get_content_type() == "text/plain"
                        and not part.get("Content-Disposition")
                    ):
                        body = part.get_payload(decode=True).decode(errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="replace")

            limit = 1000 if gmail_thread_id else 400
            snippet = body[:limit] + ("..." if len(body) > limit else "")

            results.append(
                f"---\n"
                f"From:       {msg.get('From')}\n"
                f"Date:       {msg.get('Date')}\n"
                f"Subject:    {subject}\n"
                f"References: {msg.get('References', 'N/A')}\n"
                f"Body:\n{snippet}"
            )

        mail.logout()
        return "\n\n".join(results)

    except Exception as e:
        return f"Failed to read email: {str(e)}"


if __name__ == "__main__":
    # Step 1: send and capture the gmail_thread_id
    result = send_email.invoke(
        input={
            "subject": "test",
            "content": "hello",
            "recipient": "kausthubkannan961@gmail.com",
        }
    )
    print("Send result:", result)

    # Step 2: read thread using gmail_thread_id
    if result.get("gmail_thread_id"):
        print(
            read_email.invoke(
                input={"gmail_thread_id": result["gmail_thread_id"]}
            )
        )