"""Валидаторы полей заявки."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from data.currencies import Currency, get_currency, list_currency_codes
from models.invoice import DATE_PATTERN

AMOUNT_CURRENCY_PATTERN = re.compile(
    r"^\s*([\d\s]+\.?\d*)\s+([A-Za-z]{3})\s*$"
)


def validate_date(text: str) -> date:
    text = text.strip()
    if not DATE_PATTERN.match(text):
        raise ValueError("Дата должна быть в формате ДД.ММ.ГГГГ (например, 25.12.2025)")
    day, month, year = text.split(".")
    d = date(int(year), int(month), int(day))
    if d < date.today():
        raise ValueError("Плановая дата оплаты не может быть в прошлом")
    return d


def validate_amount_with_currency(text: str) -> tuple[Decimal, Currency]:
    text = text.strip()
    match = AMOUNT_CURRENCY_PATTERN.match(text)
    if not match:
        raise ValueError(
            "Укажите сумму и код валюты через пробел.\n"
            "Пример: <b>15000 RUB</b> или <b>5000.50 USD</b>\n\n"
            f"Допустимые коды: {list_currency_codes()}"
        )
    raw_amount = match.group(1).replace(" ", "")
    raw_currency = match.group(2)
    currency = get_currency(raw_currency)
    if currency is None:
        raise ValueError(
            f"Неизвестный код валюты: <b>{raw_currency.upper()}</b>\n"
            f"Допустимые коды: {list_currency_codes()}"
        )
    try:
        amount = Decimal(raw_amount)
    except InvalidOperation:
        raise ValueError("Некорректная сумма. Введите число (например, 15000)")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Не больше двух знаков после запятой")
    return amount, currency


def validate_counterparty(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("Введите наименование контрагента")
    if len(text) > 200:
        raise ValueError("Слишком длинное наименование (макс. 200 символов)")
    return text


def validate_article(text: str, articles: list[str]) -> str:
    """Validate article by number or name from dynamic list."""
    text = text.strip()
    if not articles:
        raise ValueError("Справочник статей пуст. Обратитесь к администратору.")
    try:
        idx = int(text) - 1
        if 0 <= idx < len(articles):
            return articles[idx]
    except ValueError:
        pass
    for a in articles:
        if a.lower() == text.lower():
            return a
    for a in articles:
        if text.lower() in a.lower():
            return a
    raise ValueError("Выберите статью из списка (введите номер или название)")


def validate_comment(text: str) -> str:
    text = text.strip() if text else ""
    if len(text) > 500:
        raise ValueError("Слишком длинный комментарий (макс. 500 символов)")
    return text


def build_article_keyboard(articles: list[str]) -> list[str]:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a}")
    lines.append("Введите номер или название статьи:")
    return lines
