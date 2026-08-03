"""Pydantic models for invoice application data with validation."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class PaymentStatus(StrEnum):
    """Invoice payment status."""

    PENDING = "Ожидает оплаты"
    PAID = "Оплачено"
    REJECTED = "Отклонено"
    ON_HOLD = "На уточнении"


class Article(StrEnum):
    """Budget articles for invoices."""

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


DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


class InvoiceApplication(BaseModel):
    """Full invoice payment application."""

    entry_date: date = Field(default_factory=date.today)
    planned_payment_date: date
    employee: str = Field(min_length=2, max_length=100)
    counterparty: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    article: Article
    payment_status: PaymentStatus = PaymentStatus.PENDING
    comment: str = Field(default="", max_length=500)
    invoice_file_id: str | None = None  # Telegram file_id
    invoice_link: str = Field(default="", max_length=500)
    is_urgent: bool = False

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v: object) -> Decimal:
        """Accept amounts with comma or space separators."""
        if isinstance(v, str):
            v = v.replace(",", ".").replace(" ", "")
        return Decimal(str(v))

    @field_validator("planned_payment_date", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> date:
        """Parse date from DD.MM.YYYY string."""
        if isinstance(v, str):
            v = v.strip()
            if not DATE_PATTERN.match(v):
                raise ValueError("Дата должна быть в формате ДД.ММ.ГГГГ")
            day, month, year = v.split(".")
            return date(int(year), int(month), int(day))
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        raise ValueError("Некорректный формат даты")

    @field_validator("comment", mode="before")
    @classmethod
    def default_empty_string(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @model_validator(mode="after")
    def check_planned_date_not_past(self) -> "InvoiceApplication":
        if self.planned_payment_date < date.today():
            raise ValueError("Плановая дата оплаты не может быть в прошлом")
        return self

    def to_sheet_row(self, invoice_link: str = "") -> list[str]:
        """Convert to a row for Google Sheets."""
        return [
            self.entry_date.strftime("%d.%m.%Y"),
            self.planned_payment_date.strftime("%d.%m.%Y"),
            self.employee,
            self.counterparty,
            str(self.amount),
            self.article.value,
            self.payment_status.value,
            self.comment,
            invoice_link or "Счёт не приложен",
        ]
