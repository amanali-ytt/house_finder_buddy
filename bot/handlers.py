"""
Telegram Bot Handlers.
Standalone bot: direct LLM + SQLite, no FastAPI backend needed.

Flow:
1. New user → must upload property doc to verify → welcome
2. Verified user → can add properties (chat/PDF/Excel), search, manage
"""

import logging
import os
import tempfile
from typing import Dict, Any

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    ConversationHandler, filters
)

from bot.states import (
    ConversationState,
    get_listing_type_keyboard,
    get_property_type_keyboard,
    get_confirmation_keyboard,
    get_confirm_all_keyboard,
    get_main_menu_keyboard,
    format_property_summary,
    format_property_card,
)
from bot import database as db
from bot import llm_helpers

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_data(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """Get or initialize user data."""
    if "property_data" not in context.user_data:
        context.user_data["property_data"] = {}
    if "pending_properties" not in context.user_data:
        context.user_data["pending_properties"] = []
    return context.user_data


def clear_user_data(context: ContextTypes.DEFAULT_TYPE):
    """Clear user's temp data."""
    context.user_data["property_data"] = {}
    context.user_data["pending_properties"] = []


# =============================================================================
# /start COMMAND — with onboarding for new users
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — detect new vs returning user."""
    user = update.effective_user
    telegram_id = user.id
    logger.info(f"▶️ /start from {user.first_name} (ID: {telegram_id})")

    # Create user in DB if needed
    db.get_or_create_user(
        telegram_id=telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if db.is_user_verified(telegram_id):
        # Returning verified user — show main menu
        prop_count = len(db.get_user_properties(telegram_id))
        total_props = db.get_property_count()

        await update.message.reply_text(
            f"👋 Welcome back, {user.first_name}!\n\n"
            f"📊 You have {prop_count} properties listed.\n"
            f"🗃️ Total properties in database: {total_props}\n\n"
            "What would you like to do?",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END
    else:
        # New user — start onboarding
        await update.message.reply_text(
            f"👋 Welcome to Property Bot, {user.first_name}!\n\n"
            "Before you get started, I need to verify you're a property owner or broker.\n\n"
            "📄 *Please upload a document (PDF or Excel) that contains property information.*\n\n"
            "This could be:\n"
            "• A property listing document\n"
            "• A rental agreement\n"
            "• A property brochure or details sheet\n"
            "• An Excel file with property data\n\n"
            "I'll verify the document and add the properties to your profile!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationState.ONBOARDING_WAITING_DOC.value


# =============================================================================
# ONBOARDING — Document upload and verification
# =============================================================================

async def onboarding_receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document upload during onboarding."""
    logger.info(f"📄 ONBOARDING: Document received from {update.effective_user.first_name}")
    document = update.message.document

    if not document:
        await update.message.reply_text(
            "📄 Please upload a *PDF* or *Excel* file with property information.",
            parse_mode="Markdown",
        )
        return ConversationState.ONBOARDING_WAITING_DOC.value

    file_name = document.file_name.lower()
    valid_ext = ('.pdf', '.xlsx', '.xls', '.csv')

    if not any(file_name.endswith(ext) for ext in valid_ext):
        await update.message.reply_text(
            "⚠️ Unsupported file type. Please upload a *PDF*, *Excel* (.xlsx/.xls), or *CSV* file.",
            parse_mode="Markdown",
        )
        return ConversationState.ONBOARDING_WAITING_DOC.value

    logger.info(f"📄 ONBOARDING: Processing file '{file_name}' for {update.effective_user.first_name}")
    await update.message.reply_text(
        "📄 Processing your document... This may take a moment.\n"
        "🤖 I'm analyzing it with AI to extract property information.",
    )

    try:
        # Download file
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()

        # Process: extract → validate → normalize
        result = await llm_helpers.process_uploaded_file(bytes(file_bytes), file_name)

        if not result["success"]:
            logger.warning(f"❌ ONBOARDING: Validation failed: {result.get('error')}")
            await update.message.reply_text(
                f"❌ {result['error']}\n\n"
                "📄 Please upload a valid property document to continue.",
            )
            return ConversationState.ONBOARDING_WAITING_DOC.value

        properties = result["properties"]
        validation = result.get("validation", {})
        logger.info(f"✅ ONBOARDING: Found {len(properties)} properties, validation={validation}")

        # Check for duplicates
        telegram_id = update.effective_user.id
        new_properties = []
        duplicate_count = 0

        for prop in properties:
            dupes = db.find_duplicates(prop)
            if dupes:
                duplicate_count += 1
            else:
                new_properties.append(prop)

        if not new_properties and duplicate_count > 0:
            await update.message.reply_text(
                f"⚠️ All {duplicate_count} properties from this document already exist in the database!\n\n"
                "📄 Please upload a *different* document with new property listings.",
                parse_mode="Markdown",
            )
            return ConversationState.ONBOARDING_WAITING_DOC.value

        # Store pending properties for confirmation
        user_data = get_user_data(context)
        user_data["pending_properties"] = new_properties

        # Show summary
        summary_parts = [
            f"✅ *Document verified!* Found {len(properties)} properties.\n",
        ]
        if duplicate_count > 0:
            summary_parts.append(f"⚠️ {duplicate_count} duplicates skipped.\n")

        summary_parts.append(f"📝 *{len(new_properties)} new properties to add:*\n")

        for i, prop in enumerate(new_properties[:5], 1):
            summary_parts.append(format_property_summary(prop))
            summary_parts.append("")

        if len(new_properties) > 5:
            summary_parts.append(f"... and {len(new_properties) - 5} more.\n")

        summary_parts.append("\nWould you like to save these properties?")

        await update.message.reply_text(
            "\n".join(summary_parts),
            reply_markup=get_confirmation_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationState.ONBOARDING_CONFIRMING.value

    except Exception as e:
        logger.error(f"Onboarding file error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred while processing your file. Please try again.",
        )
        return ConversationState.ONBOARDING_WAITING_DOC.value


async def onboarding_text_instead_of_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages during onboarding (user should upload a doc)."""
    await update.message.reply_text(
        "📄 I need a *document* to verify you. Please upload a *PDF* or *Excel* file "
        "with property information.\n\n"
        "You can type /cancel to exit.",
        parse_mode="Markdown",
    )
    return ConversationState.ONBOARDING_WAITING_DOC.value


async def onboarding_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation of onboarding properties."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    telegram_id = update.effective_user.id
    logger.info(f"✅ ONBOARDING CONFIRM: User {telegram_id} said '{text}', pending={len(user_data.get('pending_properties', []))}")

    if "yes" in text or "save" in text:
        properties = user_data.get("pending_properties", [])
        saved = 0

        logger.info(f"💾 SAVING {len(properties)} properties for user {telegram_id}")
        for prop in properties:
            try:
                prop["raw_input_text"] = ""
                db.save_property(telegram_id, prop, source="pdf_onboarding")
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save property: {e}")

        # Mark user as verified
        db.mark_user_verified(telegram_id)

        clear_user_data(context)

        await update.message.reply_text(
            f"🎉 *Welcome to Property Bot!*\n\n"
            f"✅ {saved} properties saved to your profile.\n"
            f"You're now verified and can:\n\n"
            f"• ➕ *Add Property* — via chat or file upload\n"
            f"• 🔍 *Search* — find properties with natural language\n"
            f"• 📋 *My Properties* — view your listings\n\n"
            f"Use the menu below to get started!",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationHandler.END
    else:
        clear_user_data(context)
        await update.message.reply_text(
            "❌ Properties not saved.\n\n"
            "📄 Please upload a different document, or type /start to begin again.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationState.ONBOARDING_WAITING_DOC.value


# =============================================================================
# FILE UPLOAD — For verified users
# =============================================================================

async def upload_file_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the file upload flow."""
    telegram_id = update.effective_user.id

    if not db.is_user_verified(telegram_id):
        await update.message.reply_text(
            "⚠️ Please complete onboarding first. Type /start to begin.",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📄 *Upload a Property Document*\n\n"
        "Send me a PDF or Excel file with property listings.\n"
        "I'll extract the properties and add them to the database.\n\n"
        "Type /cancel to go back.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationState.PROCESSING_FILE.value


async def receive_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file upload from verified user."""
    document = update.message.document

    if not document:
        await update.message.reply_text("📄 Please upload a PDF or Excel file.")
        return ConversationState.PROCESSING_FILE.value

    file_name = document.file_name.lower()
    valid_ext = ('.pdf', '.xlsx', '.xls', '.csv')

    if not any(file_name.endswith(ext) for ext in valid_ext):
        await update.message.reply_text(
            "⚠️ Unsupported file type. Please upload PDF, Excel, or CSV.",
        )
        return ConversationState.PROCESSING_FILE.value

    await update.message.reply_text("📄 Processing your file... 🤖")

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()

        result = await llm_helpers.process_uploaded_file(bytes(file_bytes), file_name)

        if not result["success"]:
            await update.message.reply_text(
                f"❌ {result['error']}",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        properties = result["properties"]
        telegram_id = update.effective_user.id

        # Check duplicates
        new_properties = []
        duplicate_count = 0
        for prop in properties:
            dupes = db.find_duplicates(prop)
            if dupes:
                duplicate_count += 1
            else:
                new_properties.append(prop)

        if not new_properties:
            await update.message.reply_text(
                f"⚠️ All {duplicate_count} properties already exist in the database.\n"
                "Upload a different document with new listings!",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        # Store and ask for confirmation
        user_data = get_user_data(context)
        user_data["pending_properties"] = new_properties

        summary = [f"✅ Found {len(properties)} properties."]
        if duplicate_count > 0:
            summary.append(f"⚠️ {duplicate_count} duplicates skipped.")
        summary.append(f"\n📝 *{len(new_properties)} new properties:*\n")

        for i, prop in enumerate(new_properties[:5], 1):
            summary.append(format_property_card(prop, i))
            summary.append("")

        if len(new_properties) > 5:
            summary.append(f"... and {len(new_properties) - 5} more.")

        summary.append("\nSave all properties?")

        await update.message.reply_text(
            "\n".join(summary),
            reply_markup=get_confirm_all_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationState.CONFIRMING_EXTRACTED.value

    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error processing file. Please try again.",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END


async def confirm_file_properties(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm saving extracted properties."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    telegram_id = update.effective_user.id

    if "save" in text or "yes" in text:
        properties = user_data.get("pending_properties", [])
        saved = 0
        for prop in properties:
            try:
                db.save_property(telegram_id, prop, source="pdf_upload")
                saved += 1
            except Exception as e:
                logger.error(f"Save error: {e}")

        clear_user_data(context)
        await update.message.reply_text(
            f"✅ {saved} properties saved successfully!\n\n"
            f"Use 📋 My Properties to view them.",
            reply_markup=get_main_menu_keyboard(),
        )
    elif "review" in text:
        properties = user_data.get("pending_properties", [])
        # Show all properties in detail
        for i, prop in enumerate(properties, 1):
            await update.message.reply_text(
                f"*Property {i}/{len(properties)}:*\n\n"
                f"{format_property_summary(prop)}",
                parse_mode="Markdown",
            )

        await update.message.reply_text(
            "Save all these properties?",
            reply_markup=get_confirmation_keyboard(),
        )
        return ConversationState.CONFIRMING_EXTRACTED.value
    else:
        clear_user_data(context)
        await update.message.reply_text(
            "❌ Upload cancelled.",
            reply_markup=get_main_menu_keyboard(),
        )

    return ConversationHandler.END


# =============================================================================
# ADD PROPERTY VIA CHAT
# =============================================================================

async def add_property_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add property flow."""
    telegram_id = update.effective_user.id

    if not db.is_user_verified(telegram_id):
        await update.message.reply_text(
            "⚠️ Please complete onboarding first. Type /start to begin.",
        )
        return ConversationHandler.END

    clear_user_data(context)
    await update.message.reply_text(
        "🏠 Let's list your property!\n\n"
        "First, are you putting it up for *RENT* or *SALE*?",
        reply_markup=get_listing_type_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationState.WAITING_LISTING_TYPE.value


async def receive_listing_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle listing type selection."""
    text = update.message.text.lower()
    user_data = get_user_data(context)

    if "rent" in text:
        user_data["property_data"]["listing_type"] = "rent"
        await update.message.reply_text(
            "🔑 Great, a rental property!\n\nWhat type of property is it?",
            reply_markup=get_property_type_keyboard(),
        )
    elif "sell" in text or "sale" in text:
        user_data["property_data"]["listing_type"] = "sell"
        await update.message.reply_text(
            "🏠 Perfect, listing for sale!\n\nWhat type of property is it?",
            reply_markup=get_property_type_keyboard(),
        )
    else:
        await update.message.reply_text(
            "Please select either 'Rent' or 'Sell':",
            reply_markup=get_listing_type_keyboard(),
        )
        return ConversationState.WAITING_LISTING_TYPE.value

    return ConversationState.WAITING_PROPERTY_TYPE.value


async def receive_property_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle property type selection."""
    text = update.message.text.lower()
    user_data = get_user_data(context)

    type_map = {
        "apartment": "apartment", "house": "house", "villa": "villa",
        "plot": "plot", "commercial": "commercial", "pg": "pg",
    }
    property_type = "other"
    for key, value in type_map.items():
        if key in text:
            property_type = value
            break

    user_data["property_data"]["property_type"] = property_type

    listing_type = user_data["property_data"].get("listing_type", "sell")
    price_q = "💰 What's the monthly rent?" if listing_type == "rent" else "💰 What's the selling price?"

    await update.message.reply_text(
        f"Got it, a {property_type}!\n\n{price_q}\n\n"
        "_(You can use formats like 25000, 25k, 50L, 1.5Cr)_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationState.WAITING_PRICE.value


async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle price input."""
    text = update.message.text.lower().replace(",", "").replace(" ", "")
    user_data = get_user_data(context)

    try:
        if "cr" in text:
            price = float(text.replace("cr", "")) * 10000000
        elif "l" in text or "lakh" in text:
            price = float(text.replace("l", "").replace("akh", "")) * 100000
        elif "k" in text:
            price = float(text.replace("k", "")) * 1000
        else:
            price = float(text)

        user_data["property_data"]["price"] = price

        await update.message.reply_text(
            "📍 Which city and locality is the property in?\n\n"
            "_(Example: Andheri West, Mumbai)_",
            parse_mode="Markdown",
        )
        return ConversationState.WAITING_CITY.value

    except ValueError:
        await update.message.reply_text(
            "I couldn't parse that price. Please try again.\n"
            "Examples: 25000, 25k, 50L, 1.5Cr",
        )
        return ConversationState.WAITING_PRICE.value


async def receive_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle city/locality input."""
    text = update.message.text
    user_data = get_user_data(context)

    parts = text.split(",")
    if len(parts) >= 2:
        user_data["property_data"]["locality"] = parts[0].strip()
        user_data["property_data"]["city"] = parts[1].strip()
    else:
        user_data["property_data"]["city"] = text.strip()

    await update.message.reply_text(
        "🛏️ How many bedrooms?\n\n_(Enter a number, or 0 for studio/1RK)_",
    )
    return ConversationState.WAITING_BEDROOMS.value


async def receive_bedrooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bedrooms input."""
    text = update.message.text.lower()
    user_data = get_user_data(context)

    try:
        if "bhk" in text:
            bedrooms = int(text.replace("bhk", "").strip())
        elif "rk" in text or "studio" in text:
            bedrooms = 1
        else:
            bedrooms = int(text)

        user_data["property_data"]["bedrooms"] = bedrooms

        # Generate title
        listing = user_data["property_data"].get("listing_type", "rent")
        ptype = user_data["property_data"].get("property_type", "property")
        city = user_data["property_data"].get("city", "")
        user_data["property_data"]["title"] = f"{bedrooms}BHK {ptype.title()} for {listing.title()} in {city}"

        await update.message.reply_text(
            "📞 What's the contact phone number for this property?\n\n"
            "_(Enter a mobile number, or type 'skip' to skip)_",
        )
        return ConversationState.WAITING_CONTACT.value

    except ValueError:
        await update.message.reply_text("Please enter a valid number for bedrooms.")
        return ConversationState.WAITING_BEDROOMS.value


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact phone input."""
    text = update.message.text.strip()
    user_data = get_user_data(context)

    if text.lower() != "skip":
        # Clean and store phone number
        phone = text.replace(" ", "").replace("-", "")
        if phone and not phone.startswith("+"):
            if len(phone) == 10 and phone.isdigit():
                phone = "+91" + phone
        user_data["property_data"]["contact_phone"] = phone
    else:
        user_data["property_data"]["contact_phone"] = ""

    await update.message.reply_text(
        "🗺️ Do you have a Google Maps link for this property?\n\n"
        "_(Paste the Google Maps URL, or type 'skip' to skip)_",
    )
    return ConversationState.WAITING_MAPS_URL.value


async def receive_maps_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Google Maps URL input."""
    text = update.message.text.strip()
    user_data = get_user_data(context)

    if text.lower() != "skip" and text.startswith("http"):
        user_data["property_data"]["google_maps_url"] = text
    else:
        user_data["property_data"]["google_maps_url"] = ""

    summary = format_property_summary(user_data["property_data"])

    await update.message.reply_text(
        f"📋 Here's your listing summary:\n\n{summary}\n\n"
        "Would you like to save this listing?",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationState.CONFIRMING_PROPERTY.value


async def confirm_property(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle property confirmation and save."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    telegram_id = update.effective_user.id

    if "yes" in text or "save" in text:
        try:
            prop_data = user_data["property_data"]

            # Check for duplicates
            dupes = db.find_duplicates(prop_data)
            if dupes:
                await update.message.reply_text(
                    "⚠️ A similar property already exists in the database!\n\n"
                    f"Existing: {format_property_card(dupes[0])}\n\n"
                    "Save anyway? (Reply Yes or No)",
                    reply_markup=get_confirmation_keyboard(),
                )
                # Continue to save on next yes
                return ConversationState.CONFIRMING_PROPERTY.value

            prop_id = db.save_property(telegram_id, prop_data, source="chat")

            await update.message.reply_text(
                f"✅ Property saved! (ID: {prop_id})\n\n"
                "Your listing is now live and searchable.\n"
                "Use ➕ Add Property to list another or 📋 My Properties to view.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception as e:
            logger.error(f"Save property error: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Error saving property. Please try again.",
                reply_markup=get_main_menu_keyboard(),
            )
    else:
        await update.message.reply_text(
            "❌ Listing cancelled.",
            reply_markup=get_main_menu_keyboard(),
        )

    clear_user_data(context)
    return ConversationHandler.END


# =============================================================================
# SEARCH FLOW
# =============================================================================

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command."""
    await update.message.reply_text(
        "🔍 What kind of property are you looking for?\n\n"
        "Describe what you need, for example:\n"
        '• "2BHK flat for rent in Mumbai under 30k"\n'
        '• "PG in Chennai near metro"\n'
        '• "Cheapest house in Bangalore"',
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationState.SEARCHING.value


async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process natural language search query via LLM."""
    query = update.message.text

    await update.message.reply_text("🔍 Searching... 🤖")

    try:
        # Plan query via LLM
        query_plan = await llm_helpers.plan_search_query(query)

        # Execute against SQLite
        results = db.search_properties(query_plan)

        if not results:
            # Show what was searched for
            filters_desc = ", ".join(
                f"{f['field']} {f['operator']} {f['value']}"
                for f in query_plan.get("filters", [])
            )
            await update.message.reply_text(
                f"😕 No properties found.\n\n"
                f"🔎 Searched: {filters_desc or 'all properties'}\n\n"
                "Try a broader search or use ➕ Add Property to list one!",
                reply_markup=get_main_menu_keyboard(),
            )
        else:
            parts = [f"🏠 Found {len(results)} properties:\n"]

            for i, prop in enumerate(results[:10], 1):
                parts.append(format_property_card(prop, i))
                parts.append("")

            if len(results) > 10:
                parts.append(f"... and {len(results) - 10} more.")

            await update.message.reply_text(
                "\n".join(parts),
                reply_markup=get_main_menu_keyboard(),
            )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Search failed. Please try again.",
            reply_markup=get_main_menu_keyboard(),
        )

    return ConversationHandler.END


# =============================================================================
# MY PROPERTIES
# =============================================================================

async def my_properties_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /my_properties command."""
    telegram_id = update.effective_user.id

    properties = db.get_user_properties(telegram_id)

    if not properties:
        await update.message.reply_text(
            "📋 You haven't listed any properties yet.\n\n"
            "Use ➕ Add Property or 📄 Upload File to get started!",
            reply_markup=get_main_menu_keyboard(),
        )
    else:
        parts = [f"📋 *Your Properties ({len(properties)}):*\n"]

        for i, prop in enumerate(properties, 1):
            parts.append(format_property_card(prop, i))
            parts.append("")

        await update.message.reply_text(
            "\n".join(parts),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
        )


# =============================================================================
# HELP COMMAND
# =============================================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "🤖 *Property Bot Help*\n\n"
        "*Commands:*\n"
        "• /start — Start or re-enter the bot\n"
        "• /add — List a new property via chat\n"
        "• /upload — Upload PDF/Excel with properties\n"
        "• /search — Search properties (natural language)\n"
        "• /my\\_properties — View your listings\n"
        "• /cancel — Cancel current operation\n\n"
        "*Adding Properties:*\n"
        "1. 💬 *Chat* — I'll guide you step by step\n"
        "2. 📄 *PDF/Excel* — Upload and I'll extract automatically\n\n"
        "*Searching:*\n"
        'Just type what you need!\n'
        '• "2BHK flat for rent in Mumbai under 30k"\n'
        '• "PG in Chennai near metro"\n'
        '• "Cheapest property in Bangalore"\n\n'
        "*Tips:*\n"
        "• Use Indian formats (lakhs, crores, sq ft)\n"
        "• Mention rent/buy and city for better results\n"
        "• 🤖 Powered by DeepSeek AI",
        parse_mode="Markdown",
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    clear_user_data(context)
    await update.message.reply_text(
        "❌ Operation cancelled.",
        reply_markup=get_main_menu_keyboard(),
    )
    return ConversationHandler.END


# =============================================================================
# MENU TEXT HANDLER — for button presses
# =============================================================================

async def handle_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu text buttons and direct search queries."""
    text = update.message.text.lower()
    telegram_id = update.effective_user.id
    logger.info(f"📝 MENU HANDLER: '{text}' from {update.effective_user.first_name} (ID: {telegram_id})")

    # Check if user is verified
    if not db.is_user_verified(telegram_id):
        await update.message.reply_text(
            "👋 Hi! You need to complete onboarding first.\n\n"
            "Send /start to begin!",
        )
        return

    if "add" in text and "property" in text:
        return await add_property_start(update, context)
    elif "upload" in text:
        return await upload_file_start(update, context)
    elif text.strip().startswith("search") or "🔍" in text:
        return await search_command(update, context)
    elif "my properties" in text or "my listing" in text:
        await my_properties_command(update, context)
    elif "help" in text:
        await help_command(update, context)
    else:
        # Treat any other text as a direct search query
        logger.info(f"🔍 DIRECT SEARCH: '{text}'")
        try:
            await update.message.reply_text("🔍 Searching...")
            query_plan = await llm_helpers.plan_search_query(text)
            results = db.search_properties(query_plan.get("filters", []))

            if results:
                parts = [f"🔍 *Found {len(results)} result(s):*\n"]
                for i, prop in enumerate(results[:5], 1):
                    parts.append(f"{i}. {format_property_card(prop)}\n")
                await update.message.reply_text(
                    "\n".join(parts),
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard(),
                )
            else:
                await update.message.reply_text(
                    "😕 No properties found matching your query.\n"
                    "Try different keywords or use ➕ Add Property to list one!",
                    reply_markup=get_main_menu_keyboard(),
                )
        except Exception as e:
            logger.error(f"Direct search error: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Search failed. Please try again.",
                reply_markup=get_main_menu_keyboard(),
            )


# =============================================================================
# CONVERSATION HANDLER BUILDERS
# =============================================================================

def get_onboarding_handler() -> ConversationHandler:
    """Build the onboarding conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
        ],
        states={
            ConversationState.ONBOARDING_WAITING_DOC.value: [
                MessageHandler(filters.Document.ALL, onboarding_receive_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_text_instead_of_doc),
            ],
            ConversationState.ONBOARDING_CONFIRMING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_confirm),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        name="onboarding",
        persistent=True,
    )


def get_upload_handler() -> ConversationHandler:
    """Build the file upload conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("upload", upload_file_start),
            MessageHandler(filters.Regex(r"(?i)upload\s*file"), upload_file_start),
        ],
        states={
            ConversationState.PROCESSING_FILE.value: [
                MessageHandler(filters.Document.ALL, receive_file_upload),
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               lambda u, c: u.message.reply_text("📄 Please upload a file.")),
            ],
            ConversationState.CONFIRMING_EXTRACTED.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_file_properties),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        name="upload",
        persistent=True,
    )


def get_add_property_handler() -> ConversationHandler:
    """Build the add property conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_property_start),
            MessageHandler(filters.Regex(r"(?i)add\s*property"), add_property_start),
        ],
        states={
            ConversationState.WAITING_LISTING_TYPE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_listing_type),
            ],
            ConversationState.WAITING_PROPERTY_TYPE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_property_type),
            ],
            ConversationState.WAITING_PRICE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price),
            ],
            ConversationState.WAITING_CITY.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_city),
            ],
            ConversationState.WAITING_BEDROOMS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bedrooms),
            ],
            ConversationState.WAITING_CONTACT.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_contact),
            ],
            ConversationState.WAITING_MAPS_URL.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_maps_url),
            ],
            ConversationState.CONFIRMING_PROPERTY.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_property),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        name="add_property",
        persistent=True,
    )


def get_search_handler() -> ConversationHandler:
    """Build the search conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_command),
            MessageHandler(filters.Regex(r"(?i)^🔍?\s*search"), search_command),
        ],
        states={
            ConversationState.SEARCHING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_search),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        name="search",
        persistent=True,
    )
