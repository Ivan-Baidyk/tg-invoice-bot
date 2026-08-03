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
    allowed_user_ids: list[int]
    urgent_notify_user_id: int | None = None

    # --- Google ---
    google_sheet_id: str
    google_drive_folder_id: str
    google_sheet_range: str = "Заявки!A:H"

    # --- Security ---
    max_invoice_file_size_mb: int = 10


settings = Settings()  # type: ignore[call-arg]
