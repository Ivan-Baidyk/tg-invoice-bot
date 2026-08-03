#!/usr/bin/env python3
"""Интерактивный мастер установки Invoice Bot.

Запрашивает все необходимые параметры и генерирует .env.
Автоматически сохраняет credentials.json для Google OAuth.
"""

import json
import os
import sys
from pathlib import Path


def ask(label: str, default: str = "", secret: bool = False) -> str:
    """Задать вопрос с опциональным значением по умолчанию."""
    if default:
        prompt = f"{label} [{default}]: "
    else:
        prompt = f"{label}: "
    value = input(prompt).strip()
    return value or default


def ask_multiline(label: str) -> str:
    """Считать многострочный ввод (до строки END)."""
    print(label)
    print("(введите END на отдельной строке чтобы закончить):")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    print()
    print("=" * 60)
    print("  Invoice Bot — Мастер установки")
    print("=" * 60)
    print()

    # --- Telegram ---
    print("[36m─── Telegram ───[0m")
    bot_token = ask("Токен бота (от @BotFather)")
    if not bot_token:
        print("❌ Токен бота обязателен. Выход.")
        sys.exit(1)
    chat_id = ask("ID группового чата (0 — разрешить все чаты)", "0")

    # --- Proxy ---
    print()
    print("[36m─── Прокси ───[0m")
    proxy = ask("URL прокси-сервера (оставьте пустым на зарубежном сервере)", "")

    # --- Bitrix24 ---
    print()
    print("[36m─── Bitrix24 ───[0m")
    b24_url = ask(
        "Webhook URL Bitrix24",
        "https://b24-xxxxxxxx.bitrix24.ru/rest/1/xxxxxxxxxxxxxx",
    )
    b24_tg_field = ask("ID кастомного поля Bitrix24 с Telegram ID пользователя")
    b24_pos_field = ask("ID кастомного поля Bitrix24 с должностью пользователя")

    positions = ask(
        "Должности для срочных уведомлений (через запятую)",
        "Бухгалтер",
    )

    # --- Google OAuth ---
    print()
    print("[36m─── Google OAuth ───[0m")
    creds_raw = ask_multiline(
        "Вставьте содержимое JSON-файла Google OAuth (credentials.json)"
    )
    if creds_raw:
        try:
            creds_data = json.loads(creds_raw)
            with open("credentials.json", "w", encoding="utf-8") as f:
                json.dump(creds_data, f, indent=2, ensure_ascii=False)
            os.chmod("credentials.json", 0o600)
            print("✅ credentials.json сохранён")
        except json.JSONDecodeError:
            print("❌ Ошибка: некорректный JSON. Сохраните credentials.json вручную.")
    else:
        print("⚠️  credentials.json не заполнен. Сохраните его вручную в корне проекта.")

    # --- Google Sheets / Drive ---
    print()
    print("[36m─── Google Таблицы и Диск ───[0m")
    sheet_id = ask("ID Google Таблицы")
    if not sheet_id:
        print("❌ ID Google Таблицы обязателен. Выход.")
        sys.exit(1)
    drive_id = ask("ID папки Google Drive")

    # --- Loki ---
    print()
    print("[36m─── Grafana Loki (опционально) ───[0m")
    loki_url = ask("URL Loki для логов (оставьте пустым если не нужен)", "")

    # --- Build .env ---
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

# Security
MAX_INVOICE_FILE_SIZE_MB=10
"""

    env_path = Path(".env")
    if env_path.exists():
        backup = env_path.with_suffix(".env.backup")
        env_path.rename(backup)
        print(f"\n⚠️  Старый .env сохранён как {backup}")

    env_path.write_text(env_content, encoding="utf-8")
    os.chmod(env_path, 0o600)

    print()
    print("=" * 60)
    print("  ✅ Настройка завершена!")
    print("=" * 60)
    print()
    print(f"  • Конфигурация сохранена в .env")
    if creds_raw:
        print(f"  • Google OAuth сохранён в credentials.json")
    print()
    print(f"  Для запуска:")
    print(f"    uv sync")
    print(f"    uv run python bot.py")
    print()


if __name__ == "__main__":
    main()
