"""Step-by-step input validators used in the ConversationHandler."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from models.invoice import Article, DATE_PATTERN, PaymentStatus

MAX_STRING_LENGTH = 500


def validate_date(text: str) -> date:
    """Validate DD.MM.YYYY date format. Returns date or raises ValueError."""
    text = text.strip()
    if not DATE_PATTERN.match(text):
        raise ValueError("Дата должна быть в формате ДД.ММ.ГГГГ (например, 25.12.2025)")
    day, month, year = text.split(".")
    d = date(int(year), int(month), int(day))
    if d < date.today():
        raise ValueError("Плановая дата оплаты не может быть в прошлом")
    return d


def validate_amount(text: str) -> Decimal:
    """Validate monetary amount. Returns Decimal or raises ValueError."""
    text = text.strip().replace(",", ".").replace(" ", "")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError("Введите корректную сумму (например, 15000 или 15000.50)")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Сумма не может иметь больше двух знаков после запятой")
    return amount


def validate_counterparty(text: str) -> str:
    """Validate counterparty name."""
    text = text.strip()
    if not text or len(text) < 1:
        raise ValueError("Введите наименование контрагента")
    if len(text) > 200:
        raise ValueError("Наименование контрагента слишком длинное (макс. 200 символов)")
    return text


def validate_article(text: str) -> Article:
    """Validate article selection by number or name."""
    text = text.strip()
    articles = list(Article)
    # Try numeric selection
    try:
        idx = int(text) - 1
        if 0 <= idx < len(articles):
            return articles[idx]
    except ValueError:
        pass
    # Try name match (case-insensitive, partial)
    for article in articles:
        if article.value.lower() == text.lower():
            return article
    for article in articles:
        if text.lower() in article.value.lower():
            return article
    raise ValueError("Выберите статью из списка (введите номер или название)")


def validate_comment(text: str) -> str:
    """Validate comment field."""
    text = text.strip() if text else ""
    if len(text) > 500:
        raise ValueError("Комментарий слишком длинный (макс. 500 символов)")
    return text


def validate_status(text: str) -> PaymentStatus:
    """Validate payment status."""
    text = text.strip()
    statuses = list(PaymentStatus)
    try:
        idx = int(text) - 1
        if 0 <= idx < len(statuses):
            return statuses[idx]
    except ValueError:
        pass
    for status in statuses:
        if status.value.lower() == text.lower():
            return status
    raise ValueError("Выберите статус из списка")


def build_article_keyboard() -> list[str]:
    """Build numbered list of articles for display."""
    lines = []
    for i, article in enumerate(Article, 1):
        lines.append(f"{i}. {article.value}")
    lines.append("Введите номер или название статьи:")
    return lines


def build_status_keyboard() -> list[str]:
    """Build numbered list of statuses for display."""
    lines = []
    for i, status in enumerate(PaymentStatus, 1):
        lines.append(f"{i}. {status.value}")
    lines.append("Введите номер или название статуса:")
    return lines
