"""Conversation handler for the invoice application flow.

Step-by-step dialog that collects all required fields from the user,
validates each input, and upon confirmation writes to Google Sheets + Drive.
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings
from middleware.security import ALLOWED_MIME_TYPES, check_file_safe
from models.invoice import Article, InvoiceApplication, PaymentStatus
from services.google_drive import upload_file_async
from services.google_sheets import append_row_async
from validators.fields import (
    build_article_keyboard,
    build_status_keyboard,
    validate_amount,
    validate_article,
    validate_comment,
    validate_counterparty,
    validate_date,
    validate_status,
)

logger = logging.getLogger(__name__)

# Conversation states
(
    STATE_PLANNED_DATE,
    STATE_COUNTERPARTY,
    STATE_AMOUNT,
    STATE_ARTICLE,
    STATE_COMMENT,
    STATE_STATUS,
    STATE_INVOICE_FILE,
    STATE_URGENCY,
    STATE_CONFIRM,
) = range(9)


async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point. /start или /new_invoice — начало подачи заявки."""
    user = update.effective_user
    if user is None:
        await update.message.reply_text("Ошибка идентификации пользователя.")
        return ConversationHandler.END

    # Store employee identity from Telegram — immutable, server-verified
    employee_name = user.full_name or f"@{user.username}" or str(user.id)
    context.user_data["employee"] = employee_name
    context.user_data["tg_user_id"] = user.id
    context.user_data["entry_date"] = date.today()

    # Reset file data
    context.user_data["invoice_file_id"] = None
    context.user_data["invoice_file_bytes"] = None
    context.user_data["invoice_file_name"] = None
    context.user_data["invoice_mime_type"] = None

    await update.message.reply_text(
        "📋 *Новая заявка на оплату счёта*

"
        "Я пошагово соберу необходимые данные.
"
        "В любой момент отправьте /cancel для отмены.

"
        "Шаг 1/7: Укажите *плановую дату оплаты* в формате ДД.ММ.ГГГГ\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_PLANNED_DATE


async def get_planned_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: Collect planned payment date."""
    try:
        planned_date = validate_date(update.message.text)
        context.user_data["planned_payment_date"] = planned_date
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}
Попробуйте ещё раз:")
        return STATE_PLANNED_DATE

    await update.message.reply_text(
        "Шаг 2/7: Введите *наименование контрагента*\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_COUNTERPARTY


async def get_counterparty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Collect counterparty."""
    try:
        counterparty = validate_counterparty(update.message.text)
        context.user_data["counterparty"] = counterparty
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}
Попробуйте ещё раз:")
        return STATE_COUNTERPARTY

    await update.message.reply_text(
        "Шаг 3/7: Введите *сумму* счёта в рублях \(например, 15000 или 15000\.50\)\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_AMOUNT


async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: Collect amount."""
    try:
        amount = validate_amount(update.message.text)
        context.user_data["amount"] = amount
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}
Попробуйте ещё раз:")
        return STATE_AMOUNT

    lines = build_article_keyboard()
    await update.message.reply_text(
        "Шаг 4/7: Выберите *статью расхода*:
" + "
".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_ARTICLE


async def get_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 4: Collect budget article."""
    try:
        article = validate_article(update.message.text)
        context.user_data["article"] = article
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}
Попробуйте ещё раз:")
        return STATE_ARTICLE

    await update.message.reply_text(
        "Шаг 5/7: Добавьте *комментарий* к заявке или отправьте `-` чтобы пропустить\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_COMMENT


async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 5: Collect comment (optional)."""
    try:
        comment = validate_comment(update.message.text)
        context.user_data["comment"] = comment
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}
Попробуйте ещё раз:")
        return STATE_COMMENT

    lines = build_status_keyboard()
    await update.message.reply_text(
        "Шаг 6/7: Выберите *статус оплаты*:
" + "
".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_STATUS


async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 6: Collect payment status."""
    try:
        status = validate_status(update.message.text)
        context.user_data["payment_status"] = status
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}
Попробуйте ещё раз:")
        return STATE_STATUS

    await update.message.reply_text(
        "Шаг 7/7: Прикрепите *файл счёта* \(PDF, изображение, документ\) "
        "или отправьте `-` если счёт отсутствует\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_INVOICE_FILE


async def get_invoice_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 7: Collect invoice file or skip."""
    # Check if user wants to skip
    if update.message.text and update.message.text.strip() == "-":
        context.user_data["invoice_file_id"] = None
        context.user_data["invoice_file_bytes"] = None
        return await ask_urgency(update, context)

    # Check if a document or photo was sent
    doc = update.message.document
    photo = update.message.photo

    if doc:
        file_size = doc.file_size or 0
        mime = doc.mime_type
        if not check_file_safe(file_size, mime):
            max_mb = settings.max_invoice_file_size_mb
            await update.message.reply_text(
                f"❌ Файл не соответствует требованиям безопасности. "
                f"Допустимые форматы: PDF, изображения, документы. "
                f"Максимальный размер: {max_mb} МБ."
            )
            return STATE_INVOICE_FILE

        file_obj = await doc.get_file()
        file_bytes = await file_obj.download_as_bytearray()
        context.user_data["invoice_file_bytes"] = bytes(file_bytes)
        context.user_data["invoice_file_id"] = doc.file_id
        context.user_data["invoice_file_name"] = doc.file_name or "invoice"
        context.user_data["invoice_mime_type"] = mime or "application/pdf"
        return await ask_urgency(update, context)

    if photo:
        # Take the largest photo size
        largest = photo[-1]
        file_obj = await largest.get_file()
        file_bytes = await file_obj.download_as_bytearray()
        context.user_data["invoice_file_bytes"] = bytes(file_bytes)
        context.user_data["invoice_file_id"] = largest.file_id
        context.user_data["invoice_file_name"] = f"invoice_{date.today().isoformat()}.jpg"
        context.user_data["invoice_mime_type"] = "image/jpeg"
        return await ask_urgency(update, context)

    await update.message.reply_text(
        "Пожалуйста, прикрепите файл или отправьте `-` чтобы пропустить."
    )
    return STATE_INVOICE_FILE


async def ask_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask if the application is urgent."""
    await update.message.reply_text(
        "Заявка *срочная*? Отправьте `да` или `нет`\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return STATE_URGENCY


async def get_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect urgency flag."""
    text = update.message.text.strip().lower()
    is_urgent = text in ("да", "yes", "1", "д", "y")
    context.user_data["is_urgent"] = is_urgent

    # Build summary
    ud = context.user_data
    summary = (
        "📋 *Проверьте данные заявки:*

"
        f"• Сотрудник: {ud['employee']}
"
        f"• Дата внесения: {ud['entry_date'].strftime('%d.%m.%Y')}
"
        f"• Плановая дата оплаты: {ud['planned_payment_date'].strftime('%d.%m.%Y')}
"
        f"• Контрагент: {ud['counterparty']}
"
        f"• Сумма: {ud['amount']} ₽
"
        f"• Статья: {ud['article'].value}
"
        f"• Статус: {ud['payment_status'].value}
"
        f"• Комментарий: {ud['comment'] or '—'}
"
        f"• Счёт: {'приложен' if ud.get('invoice_file_bytes') else 'не приложен'}
"
        f"• Срочность: {'🔥 Срочно' if is_urgent else 'Обычная'}

"
        "Подтвердить отправку? /confirm или /cancel"
    )
    # Escape for MarkdownV2
    summary = summary.replace(".", "\.").replace("-", "\-").replace("₽", "₽")
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_CONFIRM


async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Final confirmation: write to Google Sheets and Drive."""
    ud = context.user_data

    await update.message.reply_text("⏳ Сохраняю заявку...")

    # Upload file to Drive if present
    invoice_link = ""
    try:
        if ud.get("invoice_file_bytes"):
            file_id, web_link = await upload_file_async(
                file_data=ud["invoice_file_bytes"],
                file_name=ud.get("invoice_file_name", "invoice.pdf"),
                mime_type=ud.get("invoice_mime_type", "application/pdf"),
            )
            invoice_link = web_link
            logger.info("invoice_file_uploaded", file_id=file_id, link=web_link)
        else:
            invoice_link = "Счёт не приложен"
    except Exception as e:
        logger.error("drive_upload_failed", error=str(e))
        await update.message.reply_text(
            "⚠️ Не удалось загрузить файл счёта в Google Drive. "
            "Заявка будет сохранена без ссылки на счёт."
        )

    # Build application and write to Sheet
    try:
        app = InvoiceApplication(
            entry_date=ud["entry_date"],
            planned_payment_date=ud["planned_payment_date"],
            employee=ud["employee"],
            counterparty=ud["counterparty"],
            amount=ud["amount"],
            article=ud["article"],
            payment_status=ud["payment_status"],
            comment=ud.get("comment", ""),
            invoice_link=invoice_link,
            is_urgent=ud.get("is_urgent", False),
        )

        row = app.to_sheet_row(invoice_link)
        await append_row_async(row)

        await update.message.reply_text(
            "✅ *Заявка успешно сохранена\!*

"
            f"• Контрагент: {app.counterparty}
"
            f"• Сумма: {app.amount} ₽
"
            f"• Статус: {app.payment_status.value}
"
            f"• Счёт: {'загружен в Drive' if invoice_link and invoice_link != 'Счёт не приложен' else 'не приложен'}",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        # Urgent notification
        if app.is_urgent and settings.urgent_notify_user_id:
            try:
                notify_text = (
                    f"🔥 *Срочная заявка на оплату*

"
                    f"От: {app.employee}
"
                    f"Контрагент: {app.counterparty}
"
                    f"Сумма: {app.amount} ₽
"
                    f"Дата оплаты: {app.planned_payment_date.strftime('%d.%m.%Y')}
"
                    f"Счёт: {'приложен' if invoice_link and invoice_link != 'Счёт не приложен' else 'не приложен'}"
                ).replace(".", "\.").replace("-", "\-")
                await context.bot.send_message(
                    chat_id=settings.urgent_notify_user_id,
                    text=notify_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception as e:
                logger.error("urgent_notify_failed", error=str(e))

    except Exception as e:
        logger.error("sheet_write_failed", error=str(e))
        await update.message.reply_text(
            "❌ Произошла ошибка при сохранении заявки. Попробуйте позже."
        )
        return ConversationHandler.END

    return ConversationHandler.END


async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the application process."""
    await update.message.reply_text("🚫 Заявка отменена.")
    context.user_data.clear()
    return ConversationHandler.END


# --- ConversationHandler builder ---

def build_conversation_handler() -> ConversationHandler:
    """Build and return the configured ConversationHandler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_application),
            CommandHandler("new_invoice", start_application),
        ],
        states={
            STATE_PLANNED_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_planned_date),
            ],
            STATE_COUNTERPARTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_counterparty),
            ],
            STATE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount),
            ],
            STATE_ARTICLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_article),
            ],
            STATE_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment),
            ],
            STATE_STATUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_status),
            ],
            STATE_INVOICE_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, get_invoice_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_invoice_file),
            ],
            STATE_URGENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_urgency),
            ],
            STATE_CONFIRM: [
                CommandHandler("confirm", confirm_application),
                CommandHandler("cancel", cancel_application),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_application)],
        name="invoice_application",
        persistent=False,
    )
