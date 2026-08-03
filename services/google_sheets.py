"""Google Sheets service: read/write invoice data using OAuth 2.0.

Authentication is handled by google_auth.get_credentials() which uses
the user's personal Google account via OAuth, not a service account.
"""

import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from services.google_auth import get_credentials

logger = logging.getLogger(__name__)


def append_row(row_data: list[str]) -> str:
    """Append a row to the Google Sheet. Returns the range where data was written."""
    try:
        creds = get_credentials()
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
        logger.error("google_sheets_error: %s", e)
        raise


async def append_row_async(row_data: list[str]) -> str:
    """Async wrapper for append_row."""
    import asyncio

    return await asyncio.to_thread(append_row, row_data)
