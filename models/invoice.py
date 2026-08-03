"""Pydantic models for invoice application data."""

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from data.currencies import Currency

DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
STATUS_DEFAULT = "Новый"


class InvoiceApplication(BaseModel):
    entry_date: date = Field(default_factory=date.today)
    planned_payment_date: date
    employee: str = Field(min_length=1, max_length=100)
    counterparty: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency_code: str = Field(default="RUB", min_length=3, max_length=3)
    currency_name: str = Field(default="Российский рубль")
    article: str = Field(min_length=1, max_length=200)
    comment: str = Field(default="", max_length=500)
    invoice_link: str = Field(default="", max_length=500)
    employee_bitrix_id: int = 0

    @classmethod
    def from_validated(
        cls,
        planned_payment_date: date,
        employee: str,
        counterparty: str,
        amount: Decimal,
        currency: Currency,
        article: str,
        comment: str = "",
        invoice_link: str = "",
        entry_date: date | None = None,
        employee_bitrix_id: int = 0,
    ) -> "InvoiceApplication":
        return cls(
            entry_date=entry_date or date.today(),
            planned_payment_date=planned_payment_date,
            employee=employee,
            counterparty=counterparty,
            amount=amount,
            currency_code=currency.code,
            currency_name=currency.name_ru,
            article=article,
            comment=comment,
            invoice_link=invoice_link,
        )

    @property
    def amount_display(self) -> str:
        return f"{self.amount} {self.currency_code} ({self.currency_name})"

    def to_sheet_row(self, invoice_link: str = "") -> list[str]:
        return [
            self.entry_date.strftime("%d.%m.%Y"),
            self.planned_payment_date.strftime("%d.%m.%Y"),
            self.employee,
            self.counterparty,
            f"{self.amount} {self.currency_code}",
            self.article,
            STATUS_DEFAULT,
            self.comment,
            invoice_link or "Счёт не приложен",
            str(self.employee_bitrix_id),
        ]
