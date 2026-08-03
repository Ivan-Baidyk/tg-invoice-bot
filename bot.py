"""Entry point for the Telegram Invoice Bot.

Supports both polling (default) and webhook modes.
Set WEBHOOK_URL in .env to enable webhook mode.
"""

import asyncio
import logging
import signal
import sys

from telegram.ext import Application

from config import settings
from handlers.application import build_application_handlers
from middleware.security import security_middleware

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)


def build_application() -> Application:
    app = Application.builder().token(settings.bot_token).build()
    app.add_handler(security_middleware, group=-1)

    handlers = build_application_handlers()
    for handler in handlers:
        app.add_handler(handler)

    return app


async def run_polling(app: Application) -> None:
    """Run bot in polling mode (no public URL needed)."""
    logger.info("Mode: POLLING")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is running (polling). Ctrl+C to stop.")


async def run_webhook(app: Application) -> None:
    """Run bot in webhook mode (needs public HTTPS URL)."""
    logger.info("Mode: WEBHOOK — %s", settings.webhook_url)
    await app.initialize()
    await app.start()
    await app.updater.start_webhook(
        listen=settings.webhook_listen,
        port=settings.webhook_port,
        url_path="webhook",
        webhook_url=settings.webhook_url,
        drop_pending_updates=True,
    )
    logger.info("Bot is running (webhook on port %s). Ctrl+C to stop.", settings.webhook_port)


async def main() -> None:
    setup_logging()

    logger.info("Starting Invoice Bot...")
    logger.info("chat_id=%s", settings.allowed_chat_id)
    logger.info("b24_webhook=%s", "yes" if settings.bitrix24_webhook_url else "no")
    logger.info("webhook_mode=%s", "yes" if settings.use_webhook else "no (polling)")

    application = build_application()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    if settings.use_webhook:
        await run_webhook(application)
    else:
        await run_polling(application)

    await stop_event.wait()

    logger.info("Stopping bot...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
