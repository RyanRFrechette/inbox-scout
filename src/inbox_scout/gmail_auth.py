from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from rich.console import Console

from inbox_scout.paths import CREDENTIALS_DIR, PROJECT_ROOT, get_token_path

console = Console()

READONLY_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MODIFY_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SETTINGS_SCOPES = ["https://www.googleapis.com/auth/gmail.settings.basic"]

CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
READONLY_TOKEN_FILE = PROJECT_ROOT / "token.json"
MODIFY_TOKEN_FILE = PROJECT_ROOT / "token_modify.json"
SETTINGS_TOKEN_FILE = PROJECT_ROOT / "token_settings.json"


def get_auth_config(mode="readonly", account="primary"):
    token_file = get_token_path(account, mode)

    if mode == "readonly":
        return READONLY_SCOPES, token_file, "read-only"

    if mode == "modify":
        return MODIFY_SCOPES, token_file, "modify"

    if mode == "settings":
        return SETTINGS_SCOPES, token_file, "settings"

    raise ValueError("Invalid Gmail auth mode. Use 'readonly', 'modify', or 'settings'.")


def get_gmail_service(mode="readonly", account="primary"):
    scopes, token_file, mode_label = get_auth_config(mode, account)
    creds = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            console.print(f"[yellow]Refreshing Gmail {mode_label} token...[/yellow]")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing credentials file: {CREDENTIALS_FILE}"
                )

            console.print(f"[cyan]Opening browser for Gmail {mode_label} permission...[/cyan]")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                scopes
            )
            creds = flow.run_local_server(port=0, timeout_seconds=600)

        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def test_gmail_profile(mode="readonly"):
    service = get_gmail_service(mode=mode)

    profile = service.users().getProfile(userId="me").execute()

    console.print(f"\n[bold green]Gmail {mode} connection successful.[/bold green]")
    console.print(f"Email: {profile.get('emailAddress')}")
    console.print(f"Total messages: {profile.get('messagesTotal')}")
    console.print(f"Total threads: {profile.get('threadsTotal')}")

    if mode == "readonly":
        console.print("\n[yellow]Read-only mode. No Gmail changes were made.[/yellow]\n")
    else:
        console.print("\n[yellow]Modify permission exists, but this test made no Gmail changes.[/yellow]\n")


if __name__ == "__main__":
    test_gmail_profile(mode="readonly")
