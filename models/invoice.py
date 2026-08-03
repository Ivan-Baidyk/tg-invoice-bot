"""Pydantic models for invoice application data with validation."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from data.currencies import Currency

DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


class PaymentStatus(StrEnum):
    """Real sheet values: Новый, Оплачено, Отклонено."""
    NEW = "Новый"
    PAID = "Оплачено"
    REJECTED = "Отклонено"


class Article(StrEnum):
    OFFICE_SUPPLIES = "Канцелярия"
    EQUIPMENT = "Оборудование"
    SOFTWARE = "ПО и лицензии"
    RENT = "Аренда"
    UTILITIES = "Коммунальные услуги"
    MARKETING = "Маркетинг и реклама"
    TRAVEL = "Командировки"
    TRAINING = "Обучение"
    SERVICES = "Услуги подрядчиков"
    OTHER = "Прочее"


class InvoiceApplication(BaseModel):
    """Full invoice payment application."""

    entry_date: date = Field(default_factory=date.today)
    planned_payment_date: date
    employee: str = Field(min_length=1, max_length=100)
    counterparty: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency_code: str = Field(default="RUB", min_length=3, max_length=3)
    currency_name: str = Field(default="Российский рубль")
    article: Article
    payment_status: PaymentStatus = PaymentStatus.NEW
    comment: str = Field(default="", max_length=500)
    invoice_file_id: str | None = None
    invoice_link: str = Field(default="", max_length=500)
    is_urgent: bool = False

    @classmethod
    def from_validated(
        cls,
        planned_payment_date: date,
        employee: str,
        counterparty: str,
        amount: Decimal,
        currency: Currency,
        article: Article,
        payment_status: PaymentStatus,
        comment: str = "",
        invoice_link: str = "",
        entry_date: date | None = None,
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
            payment_status=payment_status,
            comment=comment,
            invoice_link=invoice_link,
        )

    @property
    def amount_display(self) -> str:
        return f"{self.amount} {self.currency_code} ({self.currency_name})"

    def to_sheet_row(self, invoice_link: str = "") -> list[str]:
        """9 columns: Дата внесения | Плановая дата | Сотрудник | Контрагент | Сумма | Статья | Статус | Комментарий | Ссылка"""
        return [
            self.entry_date.strftime("%d.%m.%Y"),
            self.planned_payment_date.strftime("%d.%m.%Y"),
            self.employee,
            self.counterparty,
            f"{self.amount} {self.currency_code}",
            self.article.value,
            self.payment_status.value,
            self.comment,
            invoice_link or "Счёт не приложен",
        ]
