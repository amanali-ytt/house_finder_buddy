"""
Telegram Bot Main Entry Point.
Standalone bot with SQLite + DeepSeek V3.2 LLM.
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, PicklePersistence
)

from bot.handlers import (
    start_command, help_command, cancel_command,
    my_properties_command, handle_menu_text,
    get_onboarding_handler, get_upload_handler,
    get_add_property_handler, get_search_handler,
)
from bot import database as db

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Start the bot."""
    # Get bot token
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        print("=" * 60)
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        print()
        print("1. Create a bot via @BotFather on Telegram")
        print("2. Copy the token")
        print("3. Set it in your .env file:")
        print("   TELEGRAM_BOT_TOKEN=your_actual_token_here")
        print("=" * 60)
        sys.exit(1)

    # Initialize database
    db.init_db()
    logger.info("✅ Database initialized")

    # Check NVIDIA API key
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if not nvidia_key:
        logger.warning("⚠️  NVIDIA_API_KEY not set! LLM features will fail.")
    else:
        logger.info(f"✅ NVIDIA API configured (model: {os.getenv('NVIDIA_MODEL', 'deepseek-ai/deepseek-v3.2')})")

    # Create persistence
    persistence = PicklePersistence(filepath="bot_data.pickle")

    # Build application
    application = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .build()
    )

    # ─── Register handlers in priority order ──────────────────────────────

    # 1. Onboarding handler (highest priority — catches /start for new users)
    application.add_handler(get_onboarding_handler())

    # 2. File upload handler
    application.add_handler(get_upload_handler())

    # 3. Add property handler (chat flow)
    application.add_handler(get_add_property_handler())

    # 4. Search handler
    application.add_handler(get_search_handler())

    # 5. Individual command handlers (for verified users who skip conversations)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("my_properties", my_properties_command))

    # 6. Standalone document uploads (outside conversation)
    # (Handled by upload handler above)

    # 7. Fallback text handler (menu buttons and general text)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_menu_text,
    ))

    # Start the bot
    print()
    print("=" * 60)
    print("🤖 PROPERTY BOT STARTING")
    print("=" * 60)
    print(f"   Database: {db.DB_PATH}")
    print(f"   LLM Model: {os.getenv('NVIDIA_MODEL', 'deepseek-ai/deepseek-v3.2')}")
    print(f"   Properties in DB: {db.get_property_count()}")
    print("=" * 60)
    print("   Send /start to your bot on Telegram to begin!")
    print("=" * 60)
    print()

    # Use webhook in production, polling for development
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

    if webhook_url:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 8443)),
            url_path=token,
            webhook_url=f"{webhook_url}/{token}",
        )
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
