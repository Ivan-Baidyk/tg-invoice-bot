#!/usr/bin/env python3
"""Interactive setup wizard for Invoice Bot.

Prompts the user for all required configuration and generates .env file.
Run: python setup.py
"""

import os
import sys
from pathlib import Path

BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    """Prompt user for input with optional default."""
    if default:
        hint = f" [{default}]"
    else:
        hint = ""
    value = input(f"{BOLD}{label}{hint}: {RESET}")
    return value.strip() or default


def main() -> None:
    print()
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  🤖 Invoice Bot — Мастер установки{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print()
    print("Этот мастер поможет настроить все переменные окружения.")
    print("Значения будут сохранены в файл .env")
    print()
    print(f"{YELLOW}Подсказка:{RESET} нажмите Enter чтобы оставить значение по умолчанию.")
    print()

    # --- Telegram ---
    print(f"{CYAN}─── Telegram ───{RESET}")
    bot_token = prompt("Токен бота (от @BotFather)", secret=True)
    chat_id = prompt("ID группового чата (напр. -1001234567890)")
    allowed_ids = prompt("Резервные ID пользователей через запятую (если Bitrix24 недоступен)", "")
    allowed_user_ids = [int(x.strip()) for x in allowed_ids.split(",") if x.strip()] if allowed_ids else []

    # --- Bitrix24 ---
    print()
    print(f"{CYAN}─── Bitrix24 ───{RESET}")
    b24_url = prompt(
        "Webhook URL Bitrix24",
        default="https://b24-xxxxxxxx.bitrix24.ru/rest/1/xxxxxxxxxxxxxx",
    )
    b24_field = prompt(
        "ID кастомного поля с Telegram ID",
        default="UF_USR_1785740541166",
    )

    # --- Google ---
    print()
    print(f"{CYAN}─── Google ───{RESET}")
    print("  ⚠️  Убедитесь что credentials.json лежит в корне проекта")
    print("  ⚠️  Как получить: Google Cloud Console → OAuth client ID → Desktop app")
    sheet_id = prompt("ID Google Таблицы")
    drive_folder_id = prompt("ID папки Google Drive для счетов")

    # --- Build .env ---
    env_content = f"""# Invoice Bot — сгенерировано setup.py
# {Path.cwd().resolve()}

# Telegram
BOT_TOKEN={bot_token}
ALLOWED_CHAT_ID={chat_id}
ALLOWED_USER_IDS={allowed_user_ids}

# Bitrix24
BITRIX24_WEBHOOK_URL={b24_url}
BITRIX24_TELEGRAM_FIELD_ID={b24_field}

# Google
GOOGLE_SHEET_ID={sheet_id}
GOOGLE_DRIVE_FOLDER_ID={drive_folder_id}

# Security
MAX_INVOICE_FILE_SIZE_MB=10
"""

    env_path = Path(".env")
    if env_path.exists():
        backup = env_path.with_suffix(".env.backup")
        env_path.rename(backup)
        print(f"\n{YELLOW}⚠ Старый .env сохранён как {backup}{RESET}")

    env_path.write_text(env_content)
    os.chmod(env_path, 0o600)

    print()
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  ✅ Настройка завершена!{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print()
    print(f"  • Конфигурация сохранена в {BOLD}.env{RESET}")
    print(f"  • Для запуска: {BOLD}uv run python bot.py{RESET}")
    print(f"  • Или Docker:   {BOLD}docker compose up -d{RESET}")
    print()
    print(f"  {YELLOW}Убедитесь что{RESET}:")
    print(f"    1. credentials.json лежит в корне проекта (Google OAuth)")
    print(f"    2. Бот добавлен в групповой чат как администратор")
    print(f"    3. В Bitrix24 у сотрудников заполнено поле {b24_field}")
    print()


if __name__ == "__main__":
    main()
