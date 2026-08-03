"""Bitrix24 integration: employee lookup via REST API.

Uses incoming webhook URL for authentication.
Employee identity is verified by matching Telegram user_id
against a custom UF_* field in Bitrix24 user profile.
"""

import logging
from typing import Any

import httpx

from config import settings
from models.employee import Employee, _cache

logger = logging.getLogger(__name__)


async def get_employee_by_telegram(tg_user_id: int) -> Employee | None:
    """Look up an employee in Bitrix24 by their Telegram user_id.

    Results are cached in memory to avoid hitting the API on every message.
    """
    if tg_user_id in _cache.by_telegram:
        return _cache.by_telegram[tg_user_id]

    field = settings.bitrix24_telegram_field_id
    url = f"{settings.bitrix24_webhook_url}/user.get"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={"FILTER": {field: str(tg_user_id)}},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        users = data.get("result", [])
        if not users:
            logger.info("b24_user_not_found", tg_user_id=tg_user_id, field=field)
            return None

        user = users[0]
        employee = Employee(
            bitrix_id=int(user["ID"]),
            last_name=user.get("LAST_NAME", ""),
            first_name=user.get("NAME", ""),
            second_name=user.get("SECOND_NAME", ""),
            position=user.get("WORK_POSITION", ""),
            telegram_id=int(user.get(field, 0)),
        )

        _cache.by_telegram[tg_user_id] = employee
        logger.info(
            "b24_employee_found",
            tg_user_id=tg_user_id,
            full_name=employee.full_name,
            position=employee.position,
        )
        return employee

    except httpx.HTTPError as e:
        logger.error("b24_api_error", error=str(e))
        return None


async def get_accountants() -> list[Employee]:
    """Return all employees with 'Бухгалтер' in their position title.

    Result is cached — Bitrix24 org structure doesn't change mid-session.
    """
    if _cache.accountants is not None:
        return _cache.accountants

    url = f"{settings.bitrix24_webhook_url}/user.get"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={"FILTER": {"ACTIVE": True}},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        field = settings.bitrix24_telegram_field_id
        accountants: list[Employee] = []

        for user in data.get("result", []):
            position = user.get("WORK_POSITION", "")
            if "бухгалтер" not in position.lower():
                continue

            tg_raw = user.get(field, "0")
            tg_id = int(tg_raw) if tg_raw else 0
            if not tg_id:
                continue

            emp = Employee(
                bitrix_id=int(user["ID"]),
                last_name=user.get("LAST_NAME", ""),
                first_name=user.get("NAME", ""),
                second_name=user.get("SECOND_NAME", ""),
                position=position,
                telegram_id=tg_id,
            )
            accountants.append(emp)

        _cache.accountants = accountants
        logger.info("b24_accountants_loaded", count=len(accountants))
        return accountants

    except httpx.HTTPError as e:
        logger.error("b24_api_accountants_error", error=str(e))
        return []


def clear_cache() -> None:
    """Clear cached employee data."""
    _cache.by_telegram.clear()
    _cache.accountants = None
    logger.info("b24_cache_cleared")
