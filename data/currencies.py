"""Currency database: ISO 4217 codes with Russian names.

Format: "15000 USD" → amount=15000, currency_code="USD", currency_name="Доллар США"
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    code: str          # ISO 4217 (USD, EUR, RUB, ...)
    name_ru: str       # Название на русском
    country: str       # Страна
    numeric: int       # Цифровой код


# Основные мировые валюты + рубль
CURRENCIES: dict[str, Currency] = {
    "USD": Currency("USD", "Доллар США", "США", 1),
    "EUR": Currency("EUR", "Евро", "Страны еврозоны", 2),
    "JPY": Currency("JPY", "Японская иена", "Япония", 3),
    "GBP": Currency("GBP", "Британский фунт стерлингов", "Великобритания", 4),
    "CNY": Currency("CNY", "Китайский юань", "Китай", 5),
    "CHF": Currency("CHF", "Швейцарский франк", "Швейцария", 6),
    "AUD": Currency("AUD", "Австралийский доллар", "Австралия", 7),
    "CAD": Currency("CAD", "Канадский доллар", "Канада", 8),
    "HKD": Currency("HKD", "Гонконгский доллар", "Гонконг", 9),
    "SGD": Currency("SGD", "Сингапурский доллар", "Сингапур", 10),
    "INR": Currency("INR", "Индийская рупия", "Индия", 11),
    "MXN": Currency("MXN", "Мексиканское песо", "Мексика", 12),
    "NZD": Currency("NZD", "Новозеландский доллар", "Новая Зеландия", 13),
    "NOK": Currency("NOK", "Норвежская крона", "Норвегия", 14),
    "KRW": Currency("KRW", "Южнокорейская вона", "Южная Корея", 15),
    "SEK": Currency("SEK", "Шведская крона", "Швеция", 16),
    "TRY": Currency("TRY", "Турецкая лира", "Турция", 17),
    "BRL": Currency("BRL", "Бразильский реал", "Бразилия", 18),
    "ZAR": Currency("ZAR", "Южноафриканский ранд", "Южная Африка", 19),
    "RUB": Currency("RUB", "Российский рубль", "Россия", 20),
}


def get_currency(code: str) -> Currency | None:
    """Get currency by ISO code (case-insensitive)."""
    return CURRENCIES.get(code.upper().strip())


def list_currency_codes() -> str:
    """Return comma-separated list of valid currency codes for error messages."""
    return ", ".join(sorted(CURRENCIES.keys()))
