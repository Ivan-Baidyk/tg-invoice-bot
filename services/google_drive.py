"""Google Drive service: upload invoice files with access control (OAuth 2.0)."""

import io
import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from config import settings
from services.google_auth import get_credentials

logger = logging.getLogger(__name__)


def upload_file(
    file_data: bytes,
    file_name: str,
    mime_type: str = "application/pdf",
) -> tuple[str, str]:
    """Upload a file to Google Drive. Returns (file_id, web_view_link).

    Tries the configured folder first; falls back to root if 404.
    """
    creds = get_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    file_metadata: dict = {"name": file_name}

    # Try with parent folder
    if settings.google_drive_folder_id:
        file_metadata["parents"] = [settings.google_drive_folder_id]

    media = MediaIoBaseUpload(
        io.BytesIO(file_data),
        mimetype=mime_type,
        resumable=False,
    )

    try:
        drive_file = (
            service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as e:
        if "404" in str(e) and "parents" in file_metadata:
            # Folder not accessible — retry without parent
            logger.warning("drive_folder_404 retrying without parent")
            del file_metadata["parents"]
            drive_file = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, webViewLink",
                )
                .execute()
            )
        else:
            raise

    file_id = drive_file.get("id")
    web_link = drive_file.get("webViewLink", "")

    _restrict_permissions(service, file_id)

    logger.info("drive_file_uploaded id=%s name=%s", file_id, file_name)
    return file_id, web_link


def _restrict_permissions(service, file_id: str) -> None:
    """Remove default permissions, keep only owner."""
    try:
        perms = service.permissions().list(fileId=file_id, fields="permissions(id,role)").execute()
        for perm in perms.get("permissions", []):
            perm_id = perm.get("id")
            role = perm.get("role")
            if role != "owner" and perm_id:
                service.permissions().delete(fileId=file_id, permissionId=perm_id).execute()
                logger.info("permission_removed file=%s perm=%s", file_id, perm_id)
    except HttpError as e:
        logger.warning("permission_restrict_warning: %s", e)


async def upload_file_async(
    file_data: bytes, file_name: str, mime_type: str = "application/pdf",
) -> tuple[str, str]:
    import asyncio
    return await asyncio.to_thread(upload_file, file_data, file_name, mime_type)
