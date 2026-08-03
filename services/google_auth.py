"""Google service account authentication — no browser, no OAuth."""

import logging
from pathlib import Path

from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

CREDENTIALS_FILE = "credentials.json"


def get_credentials() -> Credentials:
    """Load service account credentials from JSON key file."""
    path = Path(CREDENTIALS_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"\nФайл {CREDENTIALS_FILE} не найден.\n"
            "Скачайте JSON-ключ сервисного аккаунта из Google Cloud Console\n"
            "и сохраните как credentials.json в корне проекта.\n"
        )
    creds = Credentials.from_service_account_file(str(path), scopes=SCOPES)
    logger.info("service_account_loaded email=%s", creds.service_account_email)
    return creds
