#!/usr/bin/env python3
"""Interactive setup wizard for Invoice Bot."""

import os
from pathlib import Path

BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def prompt(label: str, default: str = "") -> str:
    if default:
        hint = f" [{default}]"
    else:
        hint = ""
    value = input(f"{BOLD}{label}{hint}: {RESET}")
    return value.strip() or default


def main() -> None:
    print()
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  Invoice Bot - Nastroyka{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print()

    # --- Telegram ---
    print(f"{CYAN}--- Telegram ---{RESET}")
    bot_token = prompt("Token bota (ot @BotFather)")
    chat_id = prompt("ID gruppovogo chata (0 = razreshit vse)", "0")

    # --- Bitrix24 ---
    print()
    print(f"{CYAN}--- Bitrix24 ---{RESET}")
    b24_url = prompt(
        "Webhook URL Bitrix24",
        default="https://b24-xxxxxxxx.bitrix24.ru/rest/1/xxxxxxxxxxxxxx",
    )
    b24_field = prompt(
        "ID kastomnogo polya polzovatelya Bitrix24 s Telegram ID",
        default="UF_USR_1785740541166",
    )
    positions = prompt(
        "Dolzhnosti dlya srochnykh uvedomleniy (cherez zapyatuyu)",
        default="Bukhgalter",
    )

    # --- Google ---
    print()
    print(f"{CYAN}--- Google ---{RESET}")
    print("  credentials.json dolzhen lezhat v korne proekta")
    sheet_id = prompt("ID Google Tablitsy")
    drive_folder_id = prompt("ID papki Google Drive dlya schetov")

    # --- Proxy ---
    print()
    print(f"{CYAN}--- Proxy (ostavte pustym esli ne nuzhen) ---{RESET}")
    proxy = prompt("Proxy URL (napr. http://proxy:3128)", "")

    # --- Build .env ---
    env_content = f"""# Invoice Bot — sgenerirovano setup.py
# {Path.cwd().resolve()}

# Telegram
BOT_TOKEN={bot_token}
ALLOWED_CHAT_ID={chat_id}

# Proxy (optional)
PROXY_URL={proxy}

# Bitrix24
BITRIX24_WEBHOOK_URL={b24_url}
BITRIX24_TELEGRAM_FIELD_ID={b24_field}
URGENT_NOTIFY_POSITIONS=[{",".join(f'"{p.strip()}"' for p in positions.split(",") if p.strip())}]

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
        print(f"\n{YELLOW}Staryy .env sokhranen kak {backup}{RESET}")

    env_path.write_text(env_content)
    os.chmod(env_path, 0o600)

    print()
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  Nastroyka zavershena!{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print()
    print(f"  Konfiguratsiya: {BOLD}.env{RESET}")
    print(f"  Zapusk:         {BOLD}uv run python bot.py{RESET}")
    print(f"  Docker:         {BOLD}docker compose up -d{RESET}")
    print()


if __name__ == "__main__":
    main()
