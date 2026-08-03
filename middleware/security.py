"""Security middleware: Bitrix24 authentication on every message."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from services.bitrix24 import get_employee_by_telegram

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf", "image/jpeg", "image/png", "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
}


def check_file_safe(file_size: int, mime_type: str | None) -> bool:
    max_bytes = settings.max_invoice_file_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False
    return True


async def authenticate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user is None:
        return False

    tg_id = user.id

    if settings.bitrix24_webhook_url and settings.bitrix24_telegram_field_id:
        employee = await get_employee_by_telegram(tg_id)
        if employee is not None:
            context.user_data["employee_obj"] = employee
            logger.info("auth_ok b24 user=%s tg=%s pos=%s", employee.full_name, tg_id, employee.position)
            return True

    context.user_data.clear()
    logger.warning("auth_denied tg=%s", tg_id)
    return False


async def security_middleware(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> object | None:
    if not isinstance(update, Update):
        return None
    if update.callback_query:
        return None
    if not await authenticate_user(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(
                "Доступ закрыт. Обратись к руководителю отдела"
            )
        return True  # Block ConversationHandler on deny
    return None
