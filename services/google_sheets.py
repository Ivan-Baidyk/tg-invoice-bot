"""Google Sheets service: read/write invoice data."""

import logging
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_credentials() -> Credentials:
    """Load service account credentials from JSON file."""
    creds_path = Path(settings.google_service_account_file)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Service account credentials file not found: {creds_path}. "
            "Place your credentials.json in the project root."
        )
    return Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)


def append_row(row_data: list[str]) -> str:
    """Append a row to the Google Sheet. Returns the range where data was written."""
    try:
        creds = _get_credentials()
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        sheet = service.spreadsheets()

        result = (
            sheet.values()
            .append(
                spreadsheetId=settings.google_sheet_id,
                range=settings.google_sheet_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row_data]},
            )
            .execute()
        )

        updated_range = result.get("updates", {}).get("updatedRange", "unknown")
        logger.info("sheet_row_appended", range=updated_range)
        return updated_range

    except HttpError as e:
        logger.error("google_sheets_error", error=str(e))
        raise


async def append_row_async(row_data: list[str]) -> str:
    """Async wrapper for append_row."""
    import asyncio

    return await asyncio.to_thread(append_row, row_data)
