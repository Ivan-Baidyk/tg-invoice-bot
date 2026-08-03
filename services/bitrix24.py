"""Bitrix24 integration: employee lookup via REST API.

Fetches ALL active employees once and caches the list.
Filters by custom UF_* field client-side (Bitrix24 FILTER doesn't
support UF fields in user.get).
"""

import logging
from typing import Any

import httpx

from config import settings
from models.employee import Employee, _cache

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15


async def _fetch_all_employees() -> list[Employee]:
    """Fetch all active employees from Bitrix24.

    Result is cached — org structure doesn't change mid-session.
    """
    if _cache._loaded:
        return _cache.all_employees

    url = f"{settings.bitrix24_webhook_url}/user.get"
    field = settings.bitrix24_telegram_field_id

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                url,
                json={"FILTER": {"ACTIVE": True, "USER_TYPE": "employee"}},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        employees: list[Employee] = []
        for user in data.get("result", []):
            # Only consider employees (skip admins, extranet, etc.)
            if user.get("USER_TYPE") != "employee":
                continue

            # Extract telegram_id from custom UF field (string value!)
            tg_raw = user.get(field, "").strip()
            tg_id = int(tg_raw) if tg_raw and tg_raw.isdigit() else 0

            emp = Employee(
                bitrix_id=int(user["ID"]),
                last_name=user.get("LAST_NAME", ""),
                first_name=user.get("NAME", ""),
                second_name=user.get("SECOND_NAME", ""),
                position=user.get("WORK_POSITION", ""),
                telegram_id=tg_id,
            )
            employees.append(emp)

            # Index by telegram_id for fast lookup
            if tg_id:
                _cache.by_telegram[tg_id] = emp

        _cache.all_employees = employees
        _cache._loaded = True
        logger.info(
            "b24_employees_loaded",
            total=len(employees),
            with_telegram=len([e for e in employees if e.telegram_id]),
        )
        return employees

    except httpx.HTTPError as e:
        logger.error("b24_api_error", error=str(e))
        return []


async def get_employee_by_telegram(tg_user_id: int) -> Employee | None:
    """Look up an employee by Telegram user_id.

    The UF field value from Bitrix24 is a string like "7106724608".
    """
    if tg_user_id in _cache.by_telegram:
        return _cache.by_telegram[tg_user_id]

    # First load: fetch all employees
    await _fetch_all_employees()

    return _cache.by_telegram.get(tg_user_id)


async def get_accountants() -> list[Employee]:
    """Return employees matching URGENT_NOTIFY_POSITIONS with Telegram ID."""
    employees = await _fetch_all_employees()
    if not settings.urgent_notify_positions:
        return []
    positions_lower = [p.lower() for p in settings.urgent_notify_positions]
    return [
        e for e in employees
        if e.telegram_id and any(p in e.position.lower() for p in positions_lower)
    ]


def clear_cache() -> None:
    """Clear cached employee data (e.g. after org structure update)."""
    _cache.all_employees.clear()
    _cache.by_telegram.clear()
    _cache._loaded = False
    logger.info("b24_cache_cleared")
