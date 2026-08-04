import termios, tty
#!/usr/bin/env python3
"""Интерактивный мастер установки Invoice Bot — пошаговая настройка."""

import json
import os
import sys
from pathlib import Path

GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"

_step = 0


def step(title: str) -> None:
    global _step
    _step += 1
    print()
    print(f"{GREEN}Шаг {_step}: {title}{RESET}")
    print("-" * 40)


def ask(label: str, default: str = "") -> str:
    sys.stdout.flush()
    if default:
        return input(f"  {label} [{default}]: ").strip() or default
    return input(f"  {label}: ").strip()


def ask_multiline(label: str) -> str:
    print(f"  {label}")
    print("  (введите END на отдельной строке чтобы закончить):")
    lines = []
    while True:
        try:
            line = input("  > ")
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    print()
    print(f"{GREEN}{'=' * 50}{RESET}")
    print(f"{GREEN}  Invoice Bot — Мастер установки{RESET}")
    print(f"{GREEN}{'=' * 50}{RESET}")

    # ── Шаг 1: Токен бота ──
    step("Токен Telegram-бота")
    # Flush any buffered input
    import termios, tty
    try:
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass

    while True:
        bot_token = ask("Токен бота (получить у @BotFather)")
        if not bot_token:
            print(f"{RED}  ❌ Токен не может быть пустым. Попробуйте ещё раз.{RESET}")
            continue
        if len(bot_token) < 20:
            print(f"{RED}  ❌ Токен слишком короткий. Проверьте и попробуйте ещё раз.{RESET}")
            continue
        break
    print(f"{GREEN}  ✓ Токен сохранён{RESET}")

    # ── Шаг 2: ID группы ──
    step("ID группового чата")
    print(f"  {CYAN}Бот будет дублировать все заявки в указанный чат.{RESET}")
    print(f"  {CYAN}Укажите 0, если дублирование не нужно.{RESET}")
    chat_id = ask("ID группового чата", "0")
    print(f"{GREEN}  ✓ Сохранено{RESET}")

    # ── Шаг 3: Bitrix24 webhook ──
    step("Webhook URL Битрикс24")
    print(f"  {CYAN}Бот проверяет доступ через активных сотрудников Битрикс24.{RESET}")
    print(f"  {CYAN}У каждого сотрудника должно быть заполнено поле с Telegram ID.{RESET}")
    b24_url = ask(
        "Webhook URL для REST API\n"
        "  (пример: https://b24-xxx.bitrix24.ru/rest/1/token)"
    )

    # ── Шаг 4: Поле Telegram ID ──
    step("ID поля с Telegram ID")
    print(f"  {CYAN}Кастомное поле пользователя в Битрикс24, где хранится Telegram ID.{RESET}")
    print(f"  {CYAN}Поле должно быть скрыто от пользователя, заполняется администратором.{RESET}")
    b24_tg_field = ask(
        "ID кастомного поля\n"
        "  (пример: UF_USR_1785740541166)"
    )

    # ── Шаг 5: Поле с должностью ──
    step("ID поля с должностью")
    b24_pos_field = ask(
        "ID кастомного поля пользователя с должностью\n"
        "  (пример: UF_USR_XXXXXXXXXX)"
    )

    # ── Шаг 6: Должности для уведомлений ──
    step("Должности для уведомлений")
    print(f"  {CYAN}Сотрудники с этими должностями будут получать уведомления{RESET}")
    print(f"  {CYAN}о срочных заявках и задачи в Битрикс24.{RESET}")
    positions = ask(
        "Должности через запятую",
        "Бухгалтер",
    )

    # ── Шаг 7: Google Таблица ──
    step("Google Таблица")
    print(f"  {CYAN}Сервисный аккаунт Google Cloud должен иметь доступ к таблице.{RESET}")
    sheet_id = ask(
        "ID Google Таблицы\n"
        "  (из URL: docs.google.com/spreadsheets/d/<ID>/edit)"
    )
    if not sheet_id:
        print(f"\n{RED}❌ ID таблицы обязателен. Установка прервана.{RESET}")
        sys.exit(1)
    print(f"{GREEN}  ✓ Сохранено{RESET}")

    # ── Шаг 8: Google Drive ──
    step("Папка Google Drive")
    drive_id = ask(
        "ID папки Google Drive для хранения счетов\n"
        "  (из URL: drive.google.com/drive/folders/<ID>)"
    )
    print(f"{GREEN}  ✓ Сохранено{RESET}")

    # ── Шаг 9: Ключ Google ──
    step("Ключ сервисного аккаунта Google")
    print(f"  {CYAN}Скачайте JSON-ключ в Google Cloud Console:{RESET}")
    print(f"  {CYAN}APIs & Services → Credentials → Service Account → Keys → JSON{RESET}")
    creds_raw = ask_multiline(
        "Вставьте содержимое JSON-файла"
    )

    if creds_raw:
        try:
            creds_data = json.loads(creds_raw)
            with open("credentials.json", "w", encoding="utf-8") as f:
                json.dump(creds_data, f, indent=2, ensure_ascii=False)
            os.chmod("credentials.json", 0o600)
            print(f"{GREEN}  ✓ credentials.json сохранён{RESET}")
        except json.JSONDecodeError:
            print(f"{RED}  ❌ Ошибка JSON. Сохраните файл вручную.{RESET}")
    else:
        print(f"{YELLOW}  ⚠️  Пропущено. Сохраните credentials.json вручную.{RESET}")

    # ── Шаг 10: Прокси ──
    step("Прокси (опционально)")
    print(f"  {CYAN}Если сервер находится в РФ, Telegram API может быть заблокирован.{RESET}")
    print(f"  {CYAN}Укажите URL прокси. На зарубежном сервере оставьте пустым.{RESET}")
    proxy = ask("URL прокси-сервера", "")

    # ── Шаг 11: Логирование ──
    step("Grafana Loki (опционально)")
    print(f"  {CYAN}Логи бота можно отправлять в Grafana Loki для мониторинга.{RESET}")
    loki_url = ask("URL Loki", "")

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
        print(f"\n{YELLOW}  ⚠️  Старый .env сохранён как {backup}{RESET}")

    env_path.write_text(env_content, encoding="utf-8")
    os.chmod(env_path, 0o600)

    print()
    print(f"{GREEN}{'=' * 50}{RESET}")
    print(f"{GREEN}  ✅ Установка завершена!{RESET}")
    print(f"{GREEN}{'=' * 50}{RESET}")
    print()
    print(f"  Созданы файлы:")
    print(f"    • .env — конфигурация бота")
    if creds_raw:
        print(f"    • credentials.json — ключ Google")
    print()
    print(f"  Для запуска:")
    print(f"    uv sync")
    print(f"    uv run python bot.py")
    print()


if __name__ == "__main__":
    main()
