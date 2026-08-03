"""Security middleware: Bitrix24-based authentication, chat restriction.

Authentication flow:
  1. Extract Telegram user_id (immutable, server-verified by Telegram)
  2. Fetch all employees from Bitrix24 (once, cached)
  3. Look up user by UF_* field matching their Telegram user_id
  4. Found → allow, store Employee in context.user_data
  5. Not found → deny: "Доступ к функционалу запрещен. Обратитесь к ответственному лицу"
  6. Bitrix24 unavailable → fall back to allowed_user_ids
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from services.bitrix24 import get_employee_by_telegram

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
}


def check_chat_allowed(update: Update) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    return chat.id == settings.allowed_chat_id


def check_file_safe(file_size: int, mime_type: str | None) -> bool:
    max_bytes = settings.max_invoice_file_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False
    return True


async def authenticate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Authenticate against Bitrix24 corporate directory."""
    user = update.effective_user
    if user is None:
        return False

    # Already authenticated
    if "employee_obj" in context.user_data:
        return True

    tg_id = user.id

    # Primary: Bitrix24 lookup
    if settings.bitrix24_webhook_url and settings.bitrix24_telegram_field_id:
        employee = await get_employee_by_telegram(tg_id)
        if employee is not None:
            context.user_data["employee_obj"] = employee
            return True

    # Fallback: hardcoded whitelist
    if tg_id in settings.allowed_user_ids:
        logger.warning("b24_unavailable_fallback", tg_user_id=tg_id)
        return True

    return False


async def security_middleware(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> object | None:
    if not isinstance(update, Update):
        return None

    if update.callback_query:
        return None

    if not check_chat_allowed(update):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⛔ Этот бот работает только в корпоративном чате."
            )
        return None

    if not await authenticate_user(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(
                "Доступ к функционалу запрещен. Обратитесь к ответственному лицу"
            )
        return None

    return None
