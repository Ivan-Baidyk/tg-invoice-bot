#!/usr/bin/env python3
"""Интерактивный мастер установки Invoice Bot.

Последовательно запрашивает все параметры и генерирует .env.
Автоматически сохраняет credentials.json для Google.
"""

import json
import os
import sys
from pathlib import Path

BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"


def ask(label: str, default: str = "") -> str:
    """Задать вопрос с опциональным значением по умолчанию."""
    if default:
        prompt = f"{label} [{default}]: "
    else:
        prompt = f"{label}: "
    return input(prompt).strip() or default


def ask_multiline(label: str) -> str:
    """Считать многострочный ввод (до строки END)."""
    print(label)
    print("(введите END на отдельной строке чтобы закончить):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def section(title: str) -> None:
    print(f"\n{CYAN}─── {title} ───{RESET}")


def main() -> None:
    print()
    print(f"{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}  Invoice Bot — Мастер установки{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}")
    print()

    # ── 1. Telegram ──
    section("1. Telegram")
    bot_token = ask("Токен бота (от @BotFather)")
    if not bot_token:
        print(f"{RED}❌ Токен бота обязателен. Выход.{RESET}")
        sys.exit(1)

    chat_id = ask(
        "ID группового чата для дублирования заявок\n"
        "  (0 — не дублировать, бот работает только в личных сообщениях)",
        "0",
    )

    # ── 2. Bitrix24 ──
    section("2. Битрикс24")
    print("  Бот проверяет доступ через активных сотрудников Битрикс24.")
    print("  У каждого сотрудника должно быть заполнено кастомное поле с Telegram ID.")
    print()

    b24_url = ask(
        "Webhook URL для REST API\n"
        "  (пример: https://b24-xxx.bitrix24.ru/rest/1/xxxxxxxxxxxxxx)"
    )

    b24_tg_field = ask(
        "ID кастомного поля пользователя с Telegram ID\n"
        "  (пример: UF_USR_1785740541166)"
    )

    b24_pos_field = ask(
        "ID кастомного поля пользователя с должностью\n"
        "  (пример: UF_USR_XXXXXXXXXX)"
    )

    positions = ask(
        "Должности для уведомлений о срочных заявках (через запятую)\n"
        "  (сотрудники с этими должностями получат уведомления и задачи)",
        "Бухгалтер",
    )

    # ── 3. Google Таблицы и Диск ──
    section("3. Google Таблицы и Диск")
    print("  Сервисный аккаунт Google Cloud должен иметь доступ к таблице и папке.")
    print()

    sheet_id = ask(
        "ID Google Таблицы\n"
        "  (из URL: docs.google.com/spreadsheets/d/<ID>/edit)"
    )
    if not sheet_id:
        print(f"{RED}❌ ID Google Таблицы обязателен. Выход.{RESET}")
        sys.exit(1)

    drive_id = ask(
        "ID папки Google Drive для хранения счетов\n"
        "  (из URL: drive.google.com/drive/folders/<ID>)"
    )

    # ── 4. Google credentials ──
    section("4. Ключ сервисного аккаунта Google")
    print("  Скачайте JSON-ключ в Google Cloud Console:")
    print("  APIs & Services → Credentials → Service Account → Keys → JSON")
    print()

    creds_raw = ask_multiline(
        "Вставьте содержимое JSON-файла сервисного аккаунта (credentials.json)"
    )

    if creds_raw:
        try:
            creds_data = json.loads(creds_raw)
            with open("credentials.json", "w", encoding="utf-8") as f:
                json.dump(creds_data, f, indent=2, ensure_ascii=False)
            os.chmod("credentials.json", 0o600)
            print(f"{GREEN}✅ credentials.json сохранён{RESET}")
        except json.JSONDecodeError:
            print(f"{RED}❌ Ошибка: некорректный JSON. Сохраните credentials.json вручную.{RESET}")
    else:
        print(f"{YELLOW}⚠️  credentials.json не заполнен. Сохраните его вручную.{RESET}")

    # ── 5. Прокси (опционально) ──
    section("5. Прокси (опционально)")
    proxy = ask(
        "URL прокси-сервера для Telegram API\n"
        "  (оставьте пустым, если сервер за пределами РФ)",
        "",
    )

    # ── 6. Логирование (опционально) ──
    section("6. Grafana Loki (опционально)")
    loki_url = ask(
        "URL Loki для отправки логов\n"
        "  (оставьте пустым, если не используете Grafana)",
        "",
    )

    # ── Сборка .env ──
    pos_list = ",".join(f'"{p.strip()}"' for p in positions.split(",") if p.strip())

    env_content = f"""# Invoice Bot — сгенерировано setup.py
# {Path.cwd().resolve()}

# Telegram
BOT_TOKEN={bot_token}
ALLOWED_CHAT_ID={chat_id}

# Proxy (оставьте пустым на зарубежном сервере)
PROXY_URL={proxy}

# Bitrix24
BITRIX24_WEBHOOK_URL={b24_url}
BITRIX24_TELEGRAM_FIELD_ID={b24_tg_field}
BITRIX24_POSITION_FIELD_ID={b24_pos_field}
URGENT_NOTIFY_POSITIONS=[{pos_list}]

# Google
GOOGLE_SHEET_ID={sheet_id}
GOOGLE_DRIVE_FOLDER_ID={drive_id}

# Loki (опционально)
LOKI_URL={loki_url}
"""

    env_path = Path(".env")
    if env_path.exists():
        backup = env_path.with_suffix(".env.backup")
        env_path.rename(backup)
        print(f"\n{YELLOW}⚠️  Старый .env сохранён как {backup}{RESET}")

    env_path.write_text(env_content, encoding="utf-8")
    os.chmod(env_path, 0o600)

    print()
    print(f"{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}  ✅ Настройка завершена!{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}")
    print()
    print(f"  • Конфигурация:  {BOLD}.env{RESET}")
    if creds_raw:
        print(f"  • Google ключ:   {BOLD}credentials.json{RESET}")
    print()
    print(f"  Для запуска:")
    print(f"    {BOLD}uv sync{RESET}")
    print(f"    {BOLD}uv run python bot.py{RESET}")
    print()


if __name__ == "__main__":
    main()
