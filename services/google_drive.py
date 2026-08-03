"""Google Drive service: upload invoice files with access control."""

import io
import logging
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_credentials() -> Credentials:
    creds_path = Path(settings.google_service_account_file)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Service account credentials file not found: {creds_path}"
        )
    return Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)


def upload_file(
    file_data: bytes,
    file_name: str,
    mime_type: str = "application/pdf",
) -> tuple[str, str]:
    """Upload a file to Google Drive. Returns (file_id, web_view_link).

    The file is uploaded to the designated folder with restricted access.
    Only people with explicit permissions can view it.
    """
    try:
        creds = _get_credentials()
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        file_metadata = {
            "name": file_name,
            "parents": [settings.google_drive_folder_id],
        }

        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mime_type,
            resumable=False,
        )

        drive_file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )

        file_id = drive_file.get("id")
        web_link = drive_file.get("webViewLink", "")

        # Restrict access: remove any default permissions,
        # file is only accessible to the service account owner
        # and people who have been explicitly granted access
        _restrict_permissions(service, file_id)

        logger.info("drive_file_uploaded", file_id=file_id, name=file_name)
        return file_id, web_link

    except HttpError as e:
        logger.error("google_drive_error", error=str(e))
        raise


def _restrict_permissions(service, file_id: str) -> None:
    """Remove all default permissions and keep only service account as owner.

    This ensures the file is NOT accessible via link sharing.
    Access is only granted to specific users via the Google Drive UI
    or additional API calls.
    """
    try:
        # List all permissions
        perms = service.permissions().list(fileId=file_id, fields="permissions(id,role)").execute()
        for perm in perms.get("permissions", []):
            perm_id = perm.get("id")
            role = perm.get("role")
            # Keep owner, remove anything else (anyone, domain, etc.)
            if role != "owner" and perm_id:
                service.permissions().delete(fileId=file_id, permissionId=perm_id).execute()
                logger.info("permission_removed", file_id=file_id, perm_id=perm_id)
    except HttpError as e:
        logger.warning("permission_restrict_warning", error=str(e))


async def upload_file_async(
    file_data: bytes,
    file_name: str,
    mime_type: str = "application/pdf",
) -> tuple[str, str]:
    """Async wrapper for upload_file."""
    import asyncio

    return await asyncio.to_thread(upload_file, file_data, file_name, mime_type)
