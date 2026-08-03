"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )

    # Telegram
    bot_token: str
    allowed_chat_id: int = 0
    proxy_url: str = ""
    webhook_url: str = ""
    webhook_port: int = 8443
    webhook_listen: str = "0.0.0.0"

    # Bitrix24
    bitrix24_webhook_url: str = ""
    bitrix24_telegram_field_id: str = ""
    urgent_notify_positions: list[str] = []  # Должности для срочных уведомлений

    # Google
    google_sheet_id: str
    google_drive_folder_id: str
    google_sheet_range: str = "A:I"

    # Logging
    loki_url: str = ""

    # Security
    max_invoice_file_size_mb: int = 10

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


settings = Settings()
