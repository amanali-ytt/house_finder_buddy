"""
Telegram Bot Main Entry Point.
Initializes and runs the bot with all handlers.
"""

import logging
import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, PicklePersistence
)

from bot.handlers import (
    start_command, help_command, cancel_command,
    my_properties_command, handle_document, handle_menu_text,
    get_add_property_handler, get_search_handler
)

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
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")
    
    # Create persistence for user data
    persistence = PicklePersistence(filepath="bot_data.pickle")
    
    # Build application
    application = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .build()
    )
    
    # Add handlers in order of priority
    
    # 1. Conversation handlers (for multi-turn flows)
    application.add_handler(get_add_property_handler())
    application.add_handler(get_search_handler())
    
    # 2. Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("my_properties", my_properties_command))
    
    # 3. Document handler (for file uploads)
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # 4. Fallback text handler (for menu buttons)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_menu_text
    ))
    
    # Start the bot
    logger.info("Starting Property Bot...")
    
    # Use webhook in production, polling for development
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    
    if webhook_url:
        # Production: Use webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 8443)),
            url_path=token,
            webhook_url=f"{webhook_url}/{token}",
        )
    else:
        # Development: Use polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
