import base64
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.agent import run_triage
from src.gmail_service import GmailClient
from src.schemas import TriageOutput

load_dotenv()

# Google OAuth Scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

app = FastAPI(title="Mumzworld Email Triage Service", version="1.0.0")

# In-memory idempotency cache (stores processed message IDs)
PROCESSED_MESSAGE_IDS = set()


# ==========================================
# 1. Google OAuth Credential Management
# ==========================================
def get_gmail_client() -> GmailClient:
    """Loads existing token.json or initiates OAuth flow with credentials.json."""
    creds: Optional[Credentials] = None
    token_path = Path("token.json")
    credentials_path = Path("credentials.json")

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    "credentials.json not found in root directory! "
                    "Download it from Google Cloud Console (OAuth 2.0 Client IDs)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the token for future runs
        token_path.write_text(creds.to_json())

    return GmailClient(credentials=creds)


# ==========================================
# 2. Gmail Payload Extraction Helper
# ==========================================
def extract_email_content(raw_message: dict) -> dict:
    """Parses Gmail API message structure to extract subject, sender, and body."""
    payload = raw_message.get("payload", {})
    headers = payload.get("headers", [])

    header_dict = {h["name"].lower(): h["value"] for h in headers}
    subject = header_dict.get("subject", "(No Subject)")
    sender = header_dict.get("from", "Unknown")
    thread_id = raw_message.get("threadId", "")

    body_text = ""

    def decode_data(data_str: str) -> str:
        return base64.urlsafe_b64decode(data_str).decode(
            "utf-8", errors="ignore"
        )

    # Simple plain-text payload
    if "data" in payload.get("body", {}):
        body_text = decode_data(payload["body"]["data"])
    # Multipart payload
    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and "data" in part.get(
                "body", {}
            ):
                body_text = decode_data(part["body"]["data"])
                break

    # Fallback to snippet if body extraction failed
    if not body_text.strip():
        body_text = raw_message.get("snippet", "")

    return {
        "msg_id": raw_message["id"],
        "thread_id": thread_id,
        "sender": sender,
        "subject": subject,
        "body": body_text.strip(),
    }


# ==========================================
# 3. Core Processing Pipeline
# ==========================================
def process_single_email(msg_id: str, gmail_client: GmailClient):
    """Fetches, triages, labels, and creates drafts/replies for one email."""
    # 1. Idempotency Check
    if msg_id in PROCESSED_MESSAGE_IDS:
        print(f"Message {msg_id} already processed. Skipping.")
        return

    print(f"\n--- Processing Message: {msg_id} ---")
    raw_message = gmail_client.get_email(msg_id)
    email_data = extract_email_content(raw_message)

    # Format input for LangGraph agent
    email_text = f"Subject: {email_data['subject']}\n\n{email_data['body']}"
    print(f"From: {email_data['sender']}")
    print(f"Subject: {email_data['subject']}")

    # 2. Run LangGraph Agent
    triage_result: TriageOutput = run_triage(email_text)
    print(
        f"Triage Result: Intent='{triage_result.intent}' | Urgency='{triage_result.urgency}' | Action='{triage_result.action}' (Confidence: {triage_result.confidence})"
    )

    # 3. Apply Gmail Labels
    gmail_client.apply_label(msg_id, "Mumzworld/AI-Triaged")
    gmail_client.apply_label(msg_id, f"Mumzworld/Intent/{triage_result.intent}")
    gmail_client.apply_label(
        msg_id, f"Mumzworld/Urgency/{triage_result.urgency.upper()}"
    )
    gmail_client.apply_label(msg_id, f"Mumzworld/Action/{triage_result.action}")

    # 4. Action: Reply vs Draft
    auto_send_enabled = (
        os.getenv("ENABLE_AUTO_SEND", "false").lower() == "true"
    )
    suggested_reply = (
        triage_result.suggested_reply_ar
        if triage_result.language_detected == "ar"
        else triage_result.suggested_reply_en
    )

    if (
        triage_result.action == "auto_respond"
        and triage_result.confidence >= 0.90
        and auto_send_enabled
    ):
        print("Action: Sending live automated reply...")
        gmail_client.send_reply(
            to_email=email_data["sender"],
            thread_id=email_data["thread_id"],
            subject=f"Re: {email_data['subject']}",
            body_text=suggested_reply,
        )
    else:
        print("Action: Creating Gmail draft for human review...")
        gmail_client.create_draft(
            to_email=email_data["sender"],
            thread_id=email_data["thread_id"],
            subject=f"Re: {email_data['subject']}",
            body_text=suggested_reply,
        )

    # Mark as processed
    PROCESSED_MESSAGE_IDS.add(msg_id)
    print(f"Message {msg_id} triaged and labeled successfully!\n")


# ==========================================
# 4. API Endpoints
# ==========================================
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "processed_count": len(PROCESSED_MESSAGE_IDS),
    }


@app.post("/triage/unread")
def triage_unread_emails():
    """Manual trigger: Fetches all unread emails in Inbox and runs triage."""
    gmail_client = get_gmail_client()
    # Query unread messages in inbox
    results = (
        gmail_client.service.users()
        .messages()
        .list(userId="me", q="is:unread in:inbox", maxResults=5)
        .execute()
    )

    messages = results.get("messages", [])
    if not messages:
        return {"status": "success", "message": "No unread messages found."}

    processed = []
    for msg in messages:
        process_single_email(msg["id"], gmail_client)
        processed.append(msg["id"])

    return {"status": "success", "processed_message_ids": processed}


@app.post("/webhook/gmail-pubsub")
async def gmail_pubsub_webhook(
    request: Request, background_tasks: BackgroundTasks
):
    """Production endpoint: Receives real-time push events from Google Pub/Sub."""
    body = await request.json()
    message = body.get("message", {})

    if "data" in message:
        data_str = base64.b64decode(message["data"]).decode("utf-8")
        event = json.loads(data_str)
        history_id = event.get("historyId")

        # Process in background task to return fast 200 OK
        def run_sync():
            try:
                gmail_client = get_gmail_client()
                # Fetch recent unread
                results = (
                    gmail_client.service.users()
                    .messages()
                    .list(userId="me", q="is:unread in:inbox", maxResults=5)
                    .execute()
                )
                for msg in results.get("messages", []):
                    process_single_email(msg["id"], gmail_client)
            except Exception as e:
                print(f"Error in background sync: {e}")

        background_tasks.add_task(run_sync)

    return {"status": "acknowledged"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_server:app", host="0.0.0.0", port=8000, reload=True)