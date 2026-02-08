"""
Telegram Bot Handlers.
Handles all user interactions including commands, messages, and file uploads.
"""

import logging
from typing import Dict, Any
import httpx
import json

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
    get_main_menu_keyboard,
    format_property_summary
)

logger = logging.getLogger(__name__)

# API base URL (configure via environment)
API_BASE_URL = "http://localhost:8000/api/v1"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_data(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """Get or initialize user data."""
    if "property_data" not in context.user_data:
        context.user_data["property_data"] = {}
    if "conversation_history" not in context.user_data:
        context.user_data["conversation_history"] = []
    return context.user_data


def clear_user_data(context: ContextTypes.DEFAULT_TYPE):
    """Clear user's property data."""
    context.user_data["property_data"] = {}
    context.user_data["conversation_history"] = []


async def call_api(method: str, endpoint: str, data: dict = None, params: dict = None):
    """Make API call to backend."""
    async with httpx.AsyncClient() as client:
        url = f"{API_BASE_URL}{endpoint}"
        if method == "GET":
            response = await client.get(url, params=params)
        elif method == "POST":
            response = await client.post(url, json=data, params=params)
        elif method == "DELETE":
            response = await client.delete(url, params=params)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json() if response.content else None


# =============================================================================
# COMMAND HANDLERS
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Welcome message and main menu."""
    user = update.effective_user
    
    welcome_message = f"""
👋 Welcome to Property Bot, {user.first_name}!

I can help you:
• **Add properties** for rent or sale
• **Search properties** using natural language
• **Manage your listings**

Use the menu below or type:
• /add - List a new property
• /search - Find properties
• /my_properties - View your listings
• /help - Get help
"""
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
🤖 **Property Bot Help**

**Commands:**
• /add - Start listing a new property
• /search - Search for properties
• /my_properties - View your listings
• /cancel - Cancel current operation

**Adding Properties:**
You can add properties by:
1. Chatting with me (I'll ask questions)
2. Uploading a PDF with property details
3. Uploading an Excel file with listings

**Searching:**
Just describe what you're looking for!
Examples:
• "2BHK flat for rent in Mumbai under 30k"
• "Looking to buy a villa in Pune"
• "3 bedroom near metro station"

**Tips:**
• Use Indian formats (lakhs, crores, sq ft)
• Mention if it's for rent or purchase
• Include city name for better results
"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    clear_user_data(context)
    await update.message.reply_text(
        "❌ Operation cancelled. Use /add to start again or /help for assistance.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


# =============================================================================
# ADD PROPERTY FLOW
# =============================================================================

async def add_property_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add property flow."""
    clear_user_data(context)
    
    await update.message.reply_text(
        "🏠 Let's list your property!\n\n"
        "First, are you putting it up for **RENT** or **SALE**?",
        reply_markup=get_listing_type_keyboard(),
        parse_mode="Markdown"
    )
    
    return ConversationState.WAITING_LISTING_TYPE.value


async def receive_listing_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle listing type selection."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    
    if "rent" in text:
        user_data["property_data"]["listing_type"] = "rent"
        await update.message.reply_text(
            "🔑 Great, a rental property!\n\n"
            "What type of property is it?",
            reply_markup=get_property_type_keyboard()
        )
    elif "sell" in text or "sale" in text:
        user_data["property_data"]["listing_type"] = "sell"
        await update.message.reply_text(
            "🏠 Perfect, listing for sale!\n\n"
            "What type of property is it?",
            reply_markup=get_property_type_keyboard()
        )
    else:
        await update.message.reply_text(
            "Please select either 'Rent' or 'Sell':",
            reply_markup=get_listing_type_keyboard()
        )
        return ConversationState.WAITING_LISTING_TYPE.value
    
    return ConversationState.WAITING_PROPERTY_TYPE.value


async def receive_property_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle property type selection."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    
    type_map = {
        "apartment": "apartment",
        "house": "house",
        "villa": "villa",
        "plot": "plot",
        "commercial": "commercial",
        "pg": "pg"
    }
    
    property_type = None
    for key, value in type_map.items():
        if key in text:
            property_type = value
            break
    
    if not property_type:
        property_type = "other"
    
    user_data["property_data"]["property_type"] = property_type
    
    listing_type = user_data["property_data"].get("listing_type", "sell")
    price_question = (
        "💰 What's the monthly rent?" if listing_type == "rent"
        else "💰 What's the selling price?"
    )
    
    await update.message.reply_text(
        f"Got it, a {property_type}!\n\n{price_question}\n\n"
        "_(You can use formats like 25000, 25k, 50L, 1.5Cr)_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    
    return ConversationState.WAITING_PRICE.value


async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle price input."""
    text = update.message.text.lower().replace(",", "").replace(" ", "")
    user_data = get_user_data(context)
    
    try:
        # Parse Indian price formats
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
            parse_mode="Markdown"
        )
        
        return ConversationState.WAITING_CITY.value
        
    except ValueError:
        await update.message.reply_text(
            "I couldn't understand that price. Please enter a valid amount.\n\n"
            "Examples: 25000, 25k, 50L, 1.5Cr"
        )
        return ConversationState.WAITING_PRICE.value


async def receive_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle city/locality input."""
    text = update.message.text
    user_data = get_user_data(context)
    
    # Try to parse locality and city
    parts = text.split(",")
    if len(parts) >= 2:
        user_data["property_data"]["locality"] = parts[0].strip()
        user_data["property_data"]["city"] = parts[1].strip()
    else:
        user_data["property_data"]["city"] = text.strip()
    
    await update.message.reply_text(
        "🛏️ How many bedrooms does the property have?\n\n"
        "_(Enter a number, or 0 for studio/1RK)_"
    )
    
    return ConversationState.WAITING_BEDROOMS.value


async def receive_bedrooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bedrooms input."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    
    try:
        # Parse BHK formats
        if "bhk" in text:
            bedrooms = int(text.replace("bhk", "").strip())
        elif "rk" in text or "studio" in text:
            bedrooms = 1
        else:
            bedrooms = int(text)
        
        user_data["property_data"]["bedrooms"] = bedrooms
        
        # Show summary and confirm
        summary = format_property_summary(user_data["property_data"])
        
        await update.message.reply_text(
            f"📋 Here's your listing summary:\n\n{summary}\n\n"
            "Would you like to save this listing?",
            reply_markup=get_confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
        return ConversationState.CONFIRMING_PROPERTY.value
        
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number for bedrooms."
        )
        return ConversationState.WAITING_BEDROOMS.value


async def confirm_property(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle property confirmation."""
    text = update.message.text.lower()
    user_data = get_user_data(context)
    
    if "yes" in text or "save" in text:
        try:
            # Save to database via API
            telegram_id = update.effective_user.id
            property_data = user_data["property_data"]
            
            result = await call_api(
                "POST",
                "/properties/",
                data=property_data,
                params={"telegram_id": telegram_id}
            )
            
            await update.message.reply_text(
                "✅ Property saved successfully!\n\n"
                "Your listing is now live and searchable.\n\n"
                "Use /add to list another property or /my_properties to view your listings.",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error saving property: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error saving your property. Please try again.",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        await update.message.reply_text(
            "❌ Listing cancelled. Use /add to start again.",
            reply_markup=get_main_menu_keyboard()
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
        "• \"2BHK flat for rent in Mumbai under 30k\"\n"
        "• \"3 bedroom villa to buy in Pune\"\n"
        "• \"PG near Koramangala with WiFi\"",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationState.SEARCHING.value


async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process natural language search query."""
    query = update.message.text
    
    await update.message.reply_text("🔍 Searching...")
    
    try:
        # Call search API
        result = await call_api(
            "POST",
            "/query/search",
            data={"query": query}
        )
        
        properties = result.get("results", [])
        total = result.get("total_count", 0)
        
        if not properties:
            await update.message.reply_text(
                "😕 No properties found matching your criteria.\n\n"
                "Try adjusting your search or use /add to list a property!",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            # Format results
            response_parts = [f"🏠 Found {total} properties:\n"]
            
            for i, prop in enumerate(properties[:5], 1):  # Show top 5
                listing = "🔑 Rent" if prop.get("listing_type") == "rent" else "🏠 Sale"
                price = prop.get("price", 0)
                
                if prop.get("listing_type") == "rent":
                    price_str = f"₹{price:,.0f}/mo"
                elif price >= 10000000:
                    price_str = f"₹{price/10000000:.1f}Cr"
                elif price >= 100000:
                    price_str = f"₹{price/100000:.0f}L"
                else:
                    price_str = f"₹{price:,.0f}"
                
                prop_line = (
                    f"\n{i}. {listing} | {prop.get('bedrooms', '?')}BHK "
                    f"{prop.get('property_type', 'property').title()}\n"
                    f"   📍 {prop.get('locality', '')} {prop.get('city', '')}\n"
                    f"   💰 {price_str}"
                )
                response_parts.append(prop_line)
            
            if total > 5:
                response_parts.append(f"\n\n...and {total - 5} more results.")
            
            await update.message.reply_text(
                "\n".join(response_parts),
                reply_markup=get_main_menu_keyboard()
            )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text(
            "❌ Sorry, search failed. Please try again.",
            reply_markup=get_main_menu_keyboard()
        )
    
    return ConversationHandler.END


# =============================================================================
# MY PROPERTIES
# =============================================================================

async def my_properties_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /my_properties command."""
    telegram_id = update.effective_user.id
    
    try:
        properties = await call_api(
            "GET",
            "/properties/my",
            params={"telegram_id": telegram_id}
        )
        
        if not properties:
            await update.message.reply_text(
                "📋 You haven't listed any properties yet.\n\n"
                "Use /add to list your first property!",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            response_parts = [f"📋 Your Properties ({len(properties)}):\n"]
            
            for i, prop in enumerate(properties, 1):
                listing = "🔑 Rent" if prop.get("listing_type") == "rent" else "🏠 Sale"
                status = "✅ Active" if prop.get("status") == "available" else "⏸️ Inactive"
                
                prop_line = (
                    f"\n{i}. {listing} | {prop.get('bedrooms', '?')}BHK "
                    f"in {prop.get('city', 'Unknown')}\n"
                    f"   Status: {status}"
                )
                response_parts.append(prop_line)
            
            await update.message.reply_text(
                "\n".join(response_parts),
                reply_markup=get_main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error fetching properties: {e}")
        await update.message.reply_text(
            "❌ Sorry, couldn't fetch your properties. Please try again.",
            reply_markup=get_main_menu_keyboard()
        )


# =============================================================================
# FILE UPLOAD HANDLER
# =============================================================================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (PDF/Excel)."""
    document = update.message.document
    file_name = document.file_name.lower()
    
    # Check file type
    if not (file_name.endswith('.pdf') or file_name.endswith('.xlsx') 
            or file_name.endswith('.xls') or file_name.endswith('.csv')):
        await update.message.reply_text(
            "⚠️ Please upload a PDF, Excel (.xlsx/.xls), or CSV file.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    await update.message.reply_text("📄 Processing your file... Please wait.")
    
    try:
        # Download file
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # TODO: Send to backend for processing
        # This would call the file processor and normalizer agent
        
        await update.message.reply_text(
            "✅ File received! Property details will be extracted.\n\n"
            "This feature is coming soon. For now, please use /add to list properties manually.",
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"File processing error: {e}")
        await update.message.reply_text(
            "❌ Error processing file. Please try again or use /add to list manually.",
            reply_markup=get_main_menu_keyboard()
        )


# =============================================================================
# TEXT MENU HANDLER
# =============================================================================

async def handle_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu text buttons."""
    text = update.message.text.lower()
    
    if "add" in text:
        return await add_property_start(update, context)
    elif "search" in text:
        return await search_command(update, context)
    elif "my properties" in text:
        await my_properties_command(update, context)
    elif "help" in text:
        await help_command(update, context)
    else:
        # Treat as search query
        return await search_command(update, context)


# =============================================================================
# CONVERSATION HANDLER BUILDER
# =============================================================================

def get_add_property_handler() -> ConversationHandler:
    """Build the add property conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_property_start),
            MessageHandler(filters.Regex(r"(?i)add property"), add_property_start),
        ],
        states={
            ConversationState.WAITING_LISTING_TYPE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_listing_type)
            ],
            ConversationState.WAITING_PROPERTY_TYPE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_property_type)
            ],
            ConversationState.WAITING_PRICE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)
            ],
            ConversationState.WAITING_CITY.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_city)
            ],
            ConversationState.WAITING_BEDROOMS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bedrooms)
            ],
            ConversationState.CONFIRMING_PROPERTY.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_property)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        name="add_property",
        persistent=False,
    )


def get_search_handler() -> ConversationHandler:
    """Build the search conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_command),
            MessageHandler(filters.Regex(r"(?i)search"), search_command),
        ],
        states={
            ConversationState.SEARCHING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_search)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        name="search",
        persistent=False,
    )
