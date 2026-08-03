"""Entry point for the Telegram Invoice Bot — with Loki structured logging."""

import asyncio
import json
import logging
import signal
import sys
from datetime import timedelta

from telegram import Update
from telegram.ext import Application, TypeHandler

from config import settings
from handlers.application import build_application_handlers
from middleware.security import security_middleware

logger = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for Loki."""
    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ")
        return json.dumps({
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
        }, ensure_ascii=False)


def setup_logging() -> None:
    # Force unbuffered output for background process visibility
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler (human-readable)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
    ))
    root.addHandler(console)

    # Loki handler (structured JSON) — if configured
    if settings.loki_url:
        from services.loki_handler import LokiHandler
        loki = LokiHandler(settings.loki_url, labels={"app": "invoice-bot"})
        loki.setLevel(logging.DEBUG)
        loki.setFormatter(JsonFormatter())
        loki.start()
        root.addHandler(loki)
        logger.info("loki_connected url=%s", settings.loki_url)

    # Silence noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def build_application() -> Application:
    builder = Application.builder().token(settings.bot_token)
    if settings.proxy_url:
        builder.proxy(settings.proxy_url)
        # Longer timeouts for proxy connections
        builder.connect_timeout(15).read_timeout(15).write_timeout(15).pool_timeout(15)
        logger.info("proxy=%s", settings.proxy_url)

    app = builder.build()
    app.add_handler(TypeHandler(Update, security_middleware), group=-1)
    for handler in build_application_handlers():
        app.add_handler(handler)
    return app


async def main() -> None:
    setup_logging()
    logger.info("bot_starting chat_id=%s b24=%s loki=%s",
        settings.allowed_chat_id,
        bool(settings.bitrix24_webhook_url),
        bool(settings.loki_url),
    )

    application = build_application()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def handler():
        logger.info("bot_shutdown_signal")
        stop.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, handler)
        except NotImplementedError: pass

    logger.info("bot_polling_start")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=False, poll_interval=0.5, timeout=timedelta(seconds=2))
    logger.info("bot_running")

    # Set menu button
    await app.bot.set_my_commands([
        ("start", "Оставить новую заявку"),
        ("cancel", "Отменить заявку"),
    ])

    await stop.wait()

    logger.info("bot_stopping")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("bot_stopped")


if __name__ == "__main__":
    asyncio.run(main())
