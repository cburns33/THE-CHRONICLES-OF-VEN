"""Google Docs API client.

Handles OAuth2 authentication and fetching the document as structured JSON
via the Docs API. This approach has no file size limit, unlike the Drive
export endpoint.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.utils.config import project_root
from src.utils.logging import get_logger

log = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_TOKEN_PATH = project_root() / "token.json"
_CREDENTIALS_PATH = project_root() / "credentials.json"


def _get_creds() -> Credentials:
    creds = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console "
                    "(OAuth 2.0 Desktop client) and place it in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def get_doc_modified_time(doc_id: str) -> datetime:
    """Return the last-modified UTC datetime for the Google Doc."""
    creds = _get_creds()
    drive = build("drive", "v3", credentials=creds)
    meta = drive.files().get(fileId=doc_id, fields="modifiedTime").execute()
    return datetime.fromisoformat(meta["modifiedTime"].replace("Z", "+00:00"))


def fetch_doc_as_json(doc_id: str, out_path: Path) -> dict:
    """Fetch the full document structure via the Docs API and save to out_path.

    Returns the document dict. No file size limit — works for any length manuscript.
    """
    creds = _get_creds()
    docs = build("docs", "v1", credentials=creds)
    document = docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    title = document.get("title", "untitled")
    content_len = len(str(document))
    log.info(f"Fetched doc '{title}' ({content_len // 1024} KB JSON)")
    return document
