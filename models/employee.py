"""Employee model: identity from Bitrix24."""

from dataclasses import dataclass, field


@dataclass
class Employee:
    """Employee identity verified through Bitrix24 corporate directory."""

    bitrix_id: int
    last_name: str
    first_name: str
    second_name: str = ""
    position: str = ""
    telegram_id: int = 0

    @property
    def full_name(self) -> str:
        """ФИО: Фамилия Имя Отчество."""
        parts = [self.last_name, self.first_name]
        if self.second_name:
            parts.append(self.second_name)
        return " ".join(parts)

    @property
    def is_accountant(self) -> bool:
        """True if this employee holds an accountant role."""
        return "бухгалтер" in self.position.lower()


@dataclass
class EmployeeCache:
    """In-memory cache of employee lookups."""

    by_telegram: dict[int, Employee] = field(default_factory=dict)
    accountants: list[Employee] | None = None


_cache = EmployeeCache()
