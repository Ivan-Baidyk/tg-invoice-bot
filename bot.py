"""Entry point for the Telegram Invoice Bot."""

import asyncio
import logging
import signal
import sys

from telegram.ext import Application

from config import settings
from handlers.application import build_conversation_handler
from middleware.security import security_middleware


def setup_logging() -> None:
    """Configure structured logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Reduce noise from httpx and googleapiclient
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)


def build_application() -> Application:
    """Build and configure the PTB Application."""
    app = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )

    # Security middleware runs first on every update
    app.add_handler(security_middleware, group=-1)

    # Main conversation handler
    conv_handler = build_conversation_handler()
    app.add_handler(conv_handler)

    return app


async def main() -> None:
    """Start the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Telegram Invoice Bot...")
    logger.info("allowed_chat_id=%s", settings.allowed_chat_id)
    logger.info("allowed_users=%s", len(settings.allowed_user_ids))

    application = build_application()

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    await application.initialize()
    await application.start()

    # Start polling in background
    polling_task = asyncio.create_task(
        application.updater.start_polling(drop_pending_updates=True)
    )

    logger.info("Bot is running. Press Ctrl+C to stop.")

    await stop_event.wait()

    # Shutdown
    logger.info("Stopping bot...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    polling_task.cancel()

    logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
