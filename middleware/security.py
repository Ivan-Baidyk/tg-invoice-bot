"""Security middleware: Bitrix24-based authentication, chat restriction, file safety.

Authentication flow:
  1. Extract Telegram user_id from update (immutable, server-verified)
  2. Look up user in Bitrix24 corporate directory via custom UF field
  3. If found → allow, store Employee object in context.user_data
  4. If not found → deny with clear error message
  5. If Bitrix24 unavailable → fall back to allowed_user_ids whitelist
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
    """Authenticate user against Bitrix24 corporate directory."""
    user = update.effective_user
    if user is None:
        return False

    tg_id = user.id

    if "employee_obj" in context.user_data:
        return True

    if settings.bitrix24_webhook_url and settings.bitrix24_telegram_field_id:
        employee = await get_employee_by_telegram(tg_id)
        if employee:
            context.user_data["employee_obj"] = employee
            return True

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
                "🔒 Ваш Telegram-аккаунт не найден в корпоративной системе Bitrix24. "
                "Обратитесь к администратору для привязки Telegram к вашему профилю сотрудника."
            )
        return None

    return None
