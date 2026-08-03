"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str
    allowed_chat_id: int
    allowed_user_ids: list[int] = []

    # --- Webhook (optional, falls back to polling) ---
    webhook_url: str = ""  # e.g. https://bot.example.com/webhook
    webhook_port: int = 8443
    webhook_listen: str = "0.0.0.0"

    # --- Bitrix24 ---
    bitrix24_webhook_url: str = ""
    bitrix24_telegram_field_id: str = ""

    # --- Google ---
    google_sheet_id: str
    google_drive_folder_id: str
    google_sheet_range: str = "\u0417\u0430\u044f\u0432\u043a\u0438!A:J"

    # --- Security ---
    max_invoice_file_size_mb: int = 10

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


settings = Settings()  # type: ignore[call-arg]
