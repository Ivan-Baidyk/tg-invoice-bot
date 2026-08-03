"""Shared OAuth 2.0 authentication for Google APIs.

Uses the user's personal Google account (not a service account).
On first run: opens browser → user clicks "Allow" → token.json is saved.
On subsequent runs: reads token.json, auto-refreshes if expired.
"""

import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_credentials() -> Credentials:
    """Return valid user credentials, triggering OAuth flow if needed.

    Flow:
    1. token.json exists and is valid → return immediately (no browser)
    2. token.json expired → refresh silently (no browser)
    3. No token.json → open browser, user consents, save token.json
    4. No credentials.json → raise clear error with setup instructions
    """
    creds: Credentials | None = None

    if Path(TOKEN_FILE).exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            logger.warning("token_json_corrupted", path=TOKEN_FILE)
            creds = None

    if creds and creds.valid:
        logger.info("google_auth_ok", source="cached_token")
        return creds

    if creds and creds.expired and creds.refresh_token:
        logger.info("google_auth_refreshing_token")
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception:
            logger.warning("token_refresh_failed")

    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"\n❌ Файл {CREDENTIALS_FILE} не найден.\n\n"
            "Как получить:\n"
            "1. Открой https://console.cloud.google.com/apis/credentials\n"
            "2. Создай OAuth client ID → Desktop application\n"
            "3. Скачай JSON и сохрани как credentials.json в корне проекта\n"
            "4. Запусти бота ещё раз\n"
        )

    logger.info("google_auth_starting_oauth_flow")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(
        port=0,
        open_browser=True,
        success_message="✅ Авторизация успешна! Можете закрыть это окно.",
    )

    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    """Persist credentials to token.json with restricted permissions."""
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_FILE, 0o600)
    logger.info("token_saved", path=TOKEN_FILE)
