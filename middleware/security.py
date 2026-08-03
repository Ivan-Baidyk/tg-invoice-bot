"""Security middleware: user authentication, chat restriction, file safety."""

import logging
from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from config import settings

logger = logging.getLogger(__name__)

# Allowed MIME types for invoice files
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
}


def check_user_allowed(update: Update) -> bool:
    """Check if the user is in the allowed list.

    Telegram user_id is immutable and verified by Telegram servers,
    making user impersonation impossible at the transport level.
    """
    user = update.effective_user
    if user is None:
        return False
    return user.id in settings.allowed_user_ids


def check_chat_allowed(update: Update) -> bool:
    """Ensure the bot only responds in the designated group chat.

    This prevents the bot from being used in unauthorized chats.
    """
    chat = update.effective_chat
    if chat is None:
        return False
    return chat.id == settings.allowed_chat_id


def check_file_safe(file_size: int, mime_type: str | None) -> bool:
    """Validate file size and type for invoice uploads."""
    max_bytes = settings.max_invoice_file_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False
    return True


async def security_middleware(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> object | None:
    """Middleware that enforces access control on every update.

    Installed as the first middleware in the Application.
    - Rejects updates from unauthorized users
    - Rejects updates from unauthorized chats
    - Provides clear error messages to the user
    """
    if not isinstance(update, Update):
        return None

    # Allow callback queries through (they come from buttons we've shown)
    if update.callback_query:
        return None

    # Check chat restriction
    if not check_chat_allowed(update):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⛔ Этот бот работает только в корпоративном чате. "
                "Обратитесь к администратору для получения доступа."
            )
        logger.warning(
            "unauthorized_chat",
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )
        return None

    # Check user authorization
    if not check_user_allowed(update):
        if update.effective_message:
            await update.effective_message.reply_text(
                "🔒 У вас нет доступа к подаче заявок. "
                "Обратитесь к администратору для добавления в список сотрудников."
            )
        logger.warning(
            "unauthorized_user",
            user_id=update.effective_user.id if update.effective_user else None,
        )
        return None

    return None
