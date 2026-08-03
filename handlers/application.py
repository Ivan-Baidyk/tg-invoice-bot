"""Conversation handler for the invoice application flow.

- Multi-step dialog with currency-aware amount validation
- HTML summary with inline "Изменить" buttons for each field
- Callback-based field editing with re-confirmation
"""

import logging
from datetime import date
from typing import cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from data.currencies import Currency
from middleware.security import check_file_safe
from models.invoice import Article, InvoiceApplication, PaymentStatus
from services.bitrix24 import get_accountants
from services.google_drive import upload_file_async
from services.google_sheets import append_row_async
from validators.fields import (
    build_article_keyboard,
    build_status_keyboard,
    validate_amount_with_currency,
    validate_article,
    validate_comment,
    validate_counterparty,
    validate_date,
    validate_status,
)

logger = logging.getLogger(__name__)

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
    STATE_EDITING,
) = range(10)


def _build_summary_html(ud: dict) -> str:
    file_status = "приложен" if ud.get("invoice_file_bytes") else "не приложен"
    urgency = "Срочно" if ud.get("is_urgent") else "Обычная"
    cn = ud.get("currency_name", "")
    return (
        "<b>Проверьте данные заявки:</b>\n\n"
        f"<b>Дата оплаты:</b> {ud['planned_payment_date'].strftime('%d.%m.%Y')}\n"
        f"<b>Контрагент:</b> {ud['counterparty']}\n"
        f"<b>Сумма:</b> {ud['amount']} {ud['currency_code']} ({cn})\n"
        f"<b>Статья:</b> {ud['article'].value}\n"
        f"<b>Статус:</b> {ud['payment_status'].value}\n"
        f"<b>Комментарий:</b> {ud['comment'] or '—'}\n"
        f"<b>Файл счёта:</b> {file_status}\n"
        f"<b>Срочность:</b> {urgency}\n\n"
        "<i>Нажмите кнопку для изменения поля</i>"
    )


def _build_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Дату оплаты", callback_data="edit:date")],
        [InlineKeyboardButton("🏢 Контрагента", callback_data="edit:counterparty")],
        [InlineKeyboardButton("💰 Сумму / Валюту", callback_data="edit:amount")],
        [InlineKeyboardButton("📂 Статью", callback_data="edit:article")],
        [InlineKeyboardButton("📋 Статус", callback_data="edit:status")],
        [InlineKeyboardButton("💬 Комментарий", callback_data="edit:comment")],
        [InlineKeyboardButton("📎 Файл счёта", callback_data="edit:file")],
        [InlineKeyboardButton("🔥 Срочность", callback_data="edit:urgency")],
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_app"),
        ],
    ])


async def _show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = context.user_data
    html = _build_summary_html(ud)
    kb = _build_confirm_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text(html, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(html, parse_mode=ParseMode.HTML, reply_markup=kb)
    return STATE_CONFIRM


async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if user is None:
        await update.message.reply_text("Ошибка идентификации.")
        return ConversationHandler.END
    employee = context.user_data.get("employee_obj")
    if employee is None:
        await update.message.reply_text("Доступ к функционалу запрещен. Обратитесь к ответственному лицу")
        return ConversationHandler.END
    context.user_data["employee"] = employee.full_name
    context.user_data["tg_user_id"] = user.id
    context.user_data["entry_date"] = date.today()
    context.user_data["invoice_file_id"] = None
    context.user_data["invoice_file_bytes"] = None
    context.user_data["invoice_file_name"] = None
    context.user_data["invoice_mime_type"] = None
    await update.message.reply_text(
        f"<b>Новая заявка на оплату счёта</b>\n\n"
        f"Сотрудник: <b>{employee.full_name}</b>\n"
        f"Должность: <i>{employee.position}</i>\n\n"
        "В любой момент /cancel для отмены.\n\n"
        "<b>Шаг 1/7:</b> Укажите <b>плановую дату оплаты</b> (ДД.ММ.ГГГГ)",
        parse_mode=ParseMode.HTML,
    )
    return STATE_PLANNED_DATE


async def get_planned_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["planned_payment_date"] = validate_date(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\nПопробуйте ещё раз:")
        return STATE_PLANNED_DATE
    await update.message.reply_text("<b>Шаг 2/7:</b> Введите <b>наименование контрагента</b>", parse_mode=ParseMode.HTML)
    return STATE_COUNTERPARTY


async def get_counterparty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["counterparty"] = validate_counterparty(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\nПопробуйте ещё раз:")
        return STATE_COUNTERPARTY
    await update.message.reply_text(
        "<b>Шаг 3/7:</b> Введите <b>сумму и код валюты</b>\nПример: <code>15000 RUB</code> или <code>5000 USD</code>",
        parse_mode=ParseMode.HTML,
    )
    return STATE_AMOUNT


async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount, currency = validate_amount_with_currency(update.message.text)
        context.user_data["amount"] = amount
        context.user_data["currency_code"] = currency.code
        context.user_data["currency_name"] = currency.name_ru
    except ValueError as e:
        await update.message.reply_text(str(e), parse_mode=ParseMode.HTML)
        return STATE_AMOUNT
    await update.message.reply_text(
        f"✅ {amount} {currency.code} — {currency.name_ru}\n\n"
        + "<b>Шаг 4/7:</b> " + "\n".join(build_article_keyboard()),
        parse_mode=ParseMode.HTML,
    )
    return STATE_ARTICLE


async def get_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["article"] = validate_article(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\nПопробуйте ещё раз:")
        return STATE_ARTICLE
    await update.message.reply_text(
        "<b>Шаг 5/7:</b> Добавьте <b>комментарий</b> или отправьте <code>-</code>",
        parse_mode=ParseMode.HTML,
    )
    return STATE_COMMENT


async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["comment"] = validate_comment(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\nПопробуйте ещё раз:")
        return STATE_COMMENT
    await update.message.reply_text(
        "<b>Шаг 6/7:</b> " + "\n".join(build_status_keyboard()),
        parse_mode=ParseMode.HTML,
    )
    return STATE_STATUS


async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["payment_status"] = validate_status(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\nПопробуйте ещё раз:")
        return STATE_STATUS
    await update.message.reply_text(
        "<b>Шаг 7/7:</b> Прикрепите <b>файл счёта</b> или отправьте <code>-</code>",
        parse_mode=ParseMode.HTML,
    )
    return STATE_INVOICE_FILE


async def get_invoice_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text and update.message.text.strip() == "-":
        context.user_data["invoice_file_bytes"] = None
        return await ask_urgency(update, context)
    doc = update.message.document
    photo = update.message.photo
    if doc:
        if not check_file_safe(doc.file_size or 0, doc.mime_type):
            await update.message.reply_text(f"❌ Недопустимый формат или размер (макс. {settings.max_invoice_file_size_mb} МБ)")
            return STATE_INVOICE_FILE
        file_obj = await doc.get_file()
        fb = await file_obj.download_as_bytearray()
        context.user_data["invoice_file_bytes"] = bytes(fb)
        context.user_data["invoice_file_name"] = doc.file_name or "invoice"
        context.user_data["invoice_mime_type"] = doc.mime_type or "application/pdf"
        return await ask_urgency(update, context)
    if photo:
        largest = photo[-1]
        file_obj = await largest.get_file()
        fb = await file_obj.download_as_bytearray()
        context.user_data["invoice_file_bytes"] = bytes(fb)
        context.user_data["invoice_file_name"] = f"invoice_{date.today().isoformat()}.jpg"
        context.user_data["invoice_mime_type"] = "image/jpeg"
        return await ask_urgency(update, context)
    await update.message.reply_text("Прикрепите файл или отправьте <code>-</code>", parse_mode=ParseMode.HTML)
    return STATE_INVOICE_FILE


async def ask_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Заявка <b>срочная</b>? Отправьте <code>да</code> или <code>нет</code>",
        parse_mode=ParseMode.HTML,
    )
    return STATE_URGENCY


async def get_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    context.user_data["is_urgent"] = text in ("да", "yes", "1", "д", "y")
    return await _show_summary(update, context)


# --- inline editing ---

async def _start_edit_date(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите новую <b>дату оплаты</b> (ДД.ММ.ГГГГ):", parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "date"
    return STATE_EDITING

async def _start_edit_counterparty(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите нового <b>контрагента</b>:", parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "counterparty"
    return STATE_EDITING

async def _start_edit_amount(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите новую <b>сумму и валюту</b> (напр. 15000 RUB):", parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "amount"
    return STATE_EDITING

async def _start_edit_article(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Выберите <b>статью</b>:\n" + "\n".join(build_article_keyboard()), parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "article"
    return STATE_EDITING

async def _start_edit_status(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Выберите <b>статус</b>:\n" + "\n".join(build_status_keyboard()), parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "status"
    return STATE_EDITING

async def _start_edit_comment(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите новый <b>комментарий</b> или <code>-</code>:", parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "comment"
    return STATE_EDITING

async def _start_edit_file(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Прикрепите новый <b>файл</b> или отправьте <code>-</code>:", parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "file"
    return STATE_EDITING

async def _start_edit_urgency(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Срочно? <code>да</code> или <code>нет</code>:", parse_mode=ParseMode.HTML)
    context.user_data["editing_field"] = "urgency"
    return STATE_EDITING


EDIT_ROUTER = {
    "date": _start_edit_date,
    "counterparty": _start_edit_counterparty,
    "amount": _start_edit_amount,
    "article": _start_edit_article,
    "status": _start_edit_status,
    "comment": _start_edit_comment,
    "file": _start_edit_file,
    "urgency": _start_edit_urgency,
}


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = cast(str, query.data)
    field = data.split(":", 1)[1]
    editor = EDIT_ROUTER.get(field)
    if editor:
        return await editor(update, context)
    return STATE_CONFIRM


async def handle_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("editing_field", "")
    text = update.message.text or ""
    try:
        if field == "date":
            context.user_data["planned_payment_date"] = validate_date(text)
        elif field == "counterparty":
            context.user_data["counterparty"] = validate_counterparty(text)
        elif field == "amount":
            amount, currency = validate_amount_with_currency(text)
            context.user_data["amount"] = amount
            context.user_data["currency_code"] = currency.code
            context.user_data["currency_name"] = currency.name_ru
        elif field == "article":
            context.user_data["article"] = validate_article(text)
        elif field == "status":
            context.user_data["payment_status"] = validate_status(text)
        elif field == "comment":
            context.user_data["comment"] = validate_comment(text)
        elif field == "file":
            if text.strip() == "-":
                context.user_data["invoice_file_bytes"] = None
            else:
                doc = update.message.document
                photo = update.message.photo
                if doc:
                    fo = await doc.get_file()
                    fb = await fo.download_as_bytearray()
                    context.user_data["invoice_file_bytes"] = bytes(fb)
                    context.user_data["invoice_file_name"] = doc.file_name or "invoice"
                    context.user_data["invoice_mime_type"] = doc.mime_type or "application/pdf"
                elif photo:
                    largest = photo[-1]
                    fo = await largest.get_file()
                    fb = await fo.download_as_bytearray()
                    context.user_data["invoice_file_bytes"] = bytes(fb)
                    context.user_data["invoice_file_name"] = f"invoice_{date.today().isoformat()}.jpg"
                    context.user_data["invoice_mime_type"] = "image/jpeg"
                else:
                    raise ValueError("Прикрепите файл или <code>-</code>")
        elif field == "urgency":
            t = text.strip().lower()
            context.user_data["is_urgent"] = t in ("да", "yes", "1", "д", "y")
        else:
            return STATE_EDITING
        await update.message.reply_text("✅ Обновлено.", parse_mode=ParseMode.HTML)
        return await _show_summary(update, context)
    except ValueError as e:
        await update.message.reply_text(str(e), parse_mode=ParseMode.HTML)
        return STATE_EDITING


async def handle_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ud = context.user_data
    await query.edit_message_text("⏳ Сохраняю заявку...")
    invoice_link = ""
    try:
        if ud.get("invoice_file_bytes"):
            file_id, web_link = await upload_file_async(
                file_data=ud["invoice_file_bytes"],
                file_name=ud.get("invoice_file_name", "invoice.pdf"),
                mime_type=ud.get("invoice_mime_type", "application/pdf"),
            )
            invoice_link = web_link
        else:
            invoice_link = "Счёт не приложен"
    except Exception as e:
        logger.error("drive_upload_failed", error=str(e))
    try:
        app = InvoiceApplication.from_validated(
            entry_date=ud["entry_date"],
            planned_payment_date=ud["planned_payment_date"],
            employee=ud["employee"],
            counterparty=ud["counterparty"],
            amount=ud["amount"],
            currency=Currency(code=ud["currency_code"], name_ru=ud["currency_name"], country="", numeric=0),
            article=ud["article"],
            payment_status=ud["payment_status"],
            comment=ud.get("comment", ""),
            invoice_link=invoice_link,
            is_urgent=ud.get("is_urgent", False),
        )
        await append_row_async(app.to_sheet_row(invoice_link))
        await query.message.reply_text(
            f"<b>✅ Заявка сохранена!</b>\n\n"
            f"Контрагент: {app.counterparty}\n"
            f"Сумма: {app.amount} {app.currency_code} ({app.currency_name})\n"
            f"Статус: {app.payment_status.value}\n"
            f"Счёт: {'загружен' if invoice_link != 'Счёт не приложен' else 'не приложен'}",
            parse_mode=ParseMode.HTML,
        )
        if ud.get("is_urgent"):
            await _notify_accountants(context, app)
    except Exception as e:
        logger.error("sheet_write_failed", error=str(e))
        await query.message.reply_text("❌ Ошибка сохранения заявки.")
        return ConversationHandler.END
    return ConversationHandler.END


async def _notify_accountants(context, app):
    accountants = await get_accountants()
    if not accountants:
        return
    text = (
        f"<b>Срочная заявка на оплату</b>\n\n"
        f"От: {app.employee}\n"
        f"Контрагент: {app.counterparty}\n"
        f"Сумма: {app.amount} {app.currency_code}\n"
        f"Дата оплаты: {app.planned_payment_date.strftime('%d.%m.%Y')}\n"
        f"Счёт: {'приложен' if app.invoice_link != 'Счёт не приложен' else 'не приложен'}"
    )
    for acc in accountants:
        try:
            await context.bot.send_message(chat_id=acc.telegram_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error("urgent_notify_failed", accountant=acc.full_name, error=str(e))


async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🚫 Заявка отменена.")
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🚫 Заявка отменена.")
    context.user_data.clear()
    return ConversationHandler.END


def build_application_handlers() -> list:
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_application),
            CommandHandler("new_invoice", start_application),
        ],
        states={
            STATE_PLANNED_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_planned_date)],
            STATE_COUNTERPARTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_counterparty)],
            STATE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            STATE_ARTICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_article)],
            STATE_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment)],
            STATE_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_status)],
            STATE_INVOICE_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, get_invoice_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_invoice_file),
            ],
            STATE_URGENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_urgency)],
            STATE_CONFIRM: [
                CallbackQueryHandler(handle_edit_callback, pattern="^edit:"),
                CallbackQueryHandler(handle_confirm_callback, pattern="^confirm$"),
                CallbackQueryHandler(handle_cancel_callback, pattern="^cancel_app$"),
            ],
            STATE_EDITING: [
                MessageHandler(filters.TEXT | filters.Document.ALL | filters.PHOTO, handle_field_input),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_application)],
        name="invoice_application",
        persistent=False,
    )
    return [conv_handler]
