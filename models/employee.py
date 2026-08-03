"""Employee model: identity from Bitrix24."""

from dataclasses import dataclass, field


@dataclass
class Employee:
    """Employee identity verified through Bitrix24 corporate directory."""

    bitrix_id: int
    last_name: str = ""
    first_name: str = ""
    second_name: str = ""
    position: str = ""
    telegram_id: int = 0

    @property
    def full_name(self) -> str:
        """ФИО: Фамилия Имя Отчество. Falls back to 'Сотрудник #ID'."""
        parts = [p for p in [self.last_name, self.first_name, self.second_name] if p]
        if parts:
            return " ".join(parts)
        return f"Сотрудник #{self.bitrix_id}"

    @property
    def is_accountant(self) -> bool:
        """True if this employee holds an accountant role."""
        return "бухгалтер" in self.position.lower()


@dataclass
class EmployeeCache:
    """In-memory cache of all employees fetched from Bitrix24."""

    all_employees: list[Employee] = field(default_factory=list)
    by_telegram: dict[int, Employee] = field(default_factory=dict)
    _loaded: bool = False


_cache = EmployeeCache()
