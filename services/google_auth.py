"""Shared OAuth 2.0 authentication for Google APIs.

Tries browser-based flow first (run_local_server).
If running on a headless server, falls back to console flow
(prints URL, user pastes authorization code).
"""

import logging
import os
import urllib.parse
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

    Tries browser flow first; if DISPLAY is not set (headless),
    falls back to console URL flow.
    """
    creds: Credentials | None = None

    if Path(TOKEN_FILE).exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            logger.warning("token_json_corrupted")
            creds = None

    if creds and creds.valid:
        logger.info("google_auth_ok", source="cached_token")
        return creds

    if creds and creds.expired and creds.refresh_token:
        logger.info("google_auth_refreshing")
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception:
            logger.warning("token_refresh_failed")

    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"\nФайл {CREDENTIALS_FILE} не найден.\n\n"
            "Как получить:\n"
            "1. Открой https://console.cloud.google.com/apis/credentials\n"
            "2. Создай OAuth client ID -> Desktop application\n"
            "3. Скачай JSON -> сохрани как credentials.json в корне проекта\n"
        )

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

    # Try browser flow first; if no display, use console
    # Manual OAuth for headless servers.
    logger.info("oauth_manual_flow")
    flow.redirect_uri = "http://localhost"
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
    )
    # Force redirect_uri — sometimes not auto-included
    if "redirect_uri" not in auth_url:
        auth_url += "&redirect_uri=" + urllib.parse.quote(flow.redirect_uri, safe="")
    print("\n" + "=" * 60)
    print("ОТКРОЙТЕ ССЫЛКУ В БРАУЗЕРЕ:")
    print(auth_url)
    print("=" * 60)
    print()
    print("1. Войдите в Google-аккаунт, нажмите \"Разрешить\"")
    print("2. После редиректа скопируйте ВСЮ адресную строку")
    print("3. Вставьте её сюда:")
    redirect_url = input("> ").strip()
    # Parse code from redirect URL
    import urllib.parse
    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)
    code = params.get("code", [None])[0]
    if not code:
        # Maybe user pasted just the code
        code = redirect_url
    flow.fetch_token(code=code)
    creds = flow.credentials

    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_FILE, 0o600)
    logger.info("token_saved")
