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
        logger.info("sheet_row_appended range=%s", updated_range)
        return updated_range

    except HttpError as e:
        logger.error("google_sheets_error: %s", e)
        raise


async def append_row_async(row_data: list[str]) -> str:
    """Async wrapper for append_row."""
    import asyncio

    return await asyncio.to_thread(append_row, row_data)


# Article cache
_articles_cache: list[str] = []
_articles_ts: float = 0


def get_articles() -> list[str]:
    """Read article list from 'Справочник' sheet column A."""
    global _articles_cache, _articles_ts
    import time
    now = time.time()
    if _articles_cache and now - _articles_ts < 300:
        return _articles_cache

    try:
        creds = get_credentials()
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)

        # Get spreadsheet metadata to find sheet names
        meta = service.spreadsheets().get(
            spreadsheetId=settings.google_sheet_id,
            fields="sheets.properties",
        ).execute()

        # Find sheet by gid=1004180925 (Справчник)
        ARTICLE_SHEET_GID = 1004180925
        sheet_name = None
        for s in meta.get("sheets", []):
            props = s.get("properties", {})
            if props.get("sheetId") == ARTICLE_SHEET_GID:
                sheet_name = props.get("title", "")
                break

        if not sheet_name:
            logger.error("articles_sheet_not_found gid=%d", ARTICLE_SHEET_GID)
            return _articles_cache or []

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheet_id,
                range=f"'{sheet_name}'!A:A",
            )
            .execute()
        )
        rows = result.get("values", [])
        _articles_cache = [r[0].strip() for r in rows if r and r[0].strip()]
        _articles_ts = now
        logger.info("articles_loaded sheet=%s count=%d", sheet_name, len(_articles_cache))
    except Exception as e:
        logger.error("articles_load_failed: %s", e)

    return _articles_cache


async def get_articles_async() -> list[str]:
    import asyncio
    return await asyncio.to_thread(get_articles)


def get_next_invoice_id() -> int:
    """Read last ID from column A and return next number."""
    try:
        creds = get_credentials()
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheet_id,
                range="A:A",
            )
            .execute()
        )
        rows = result.get("values", [])
        if len(rows) <= 1:
            return 1  # Only header row
        max_id = 0
        for r in rows[1:]:  # Skip header
            try:
                max_id = max(max_id, int(r[0]))
            except (ValueError, IndexError):
                pass
        return max_id + 1
    except Exception as e:
        logger.error("get_next_id_failed: %s", e)
        return 0


async def get_next_invoice_id_async() -> int:
    import asyncio
    return await asyncio.to_thread(get_next_invoice_id)
