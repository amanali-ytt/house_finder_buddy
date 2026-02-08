"""
Telegram Bot States for conversation flow management.
"""

from enum import Enum, auto


class ConversationState(Enum):
    """States for the property listing conversation flow."""
    
    # Initial states
    IDLE = auto()
    
    # Adding property flow
    ADDING_PROPERTY = auto()
    WAITING_LISTING_TYPE = auto()
    WAITING_PROPERTY_TYPE = auto()
    WAITING_PRICE = auto()
    WAITING_CITY = auto()
    WAITING_BEDROOMS = auto()
    WAITING_DETAILS = auto()
    CONFIRMING_PROPERTY = auto()
    
    # File upload flow
    PROCESSING_FILE = auto()
    CONFIRMING_EXTRACTED = auto()
    
    # Search flow
    SEARCHING = auto()
    
    # Edit flow
    EDITING_PROPERTY = auto()
    SELECTING_PROPERTY = auto()


# Keyboard layouts
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def get_listing_type_keyboard():
    """Keyboard for selecting rent/sell."""
    return ReplyKeyboardMarkup(
        [["🔑 Rent", "🏠 Sell"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def get_property_type_keyboard():
    """Keyboard for selecting property type."""
    return ReplyKeyboardMarkup(
        [
            ["🏢 Apartment", "🏠 House"],
            ["🏰 Villa", "📐 Plot"],
            ["🏪 Commercial", "🛏️ PG"],
        ],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def get_furnishing_keyboard():
    """Keyboard for selecting furnishing status."""
    return ReplyKeyboardMarkup(
        [
            ["Unfurnished", "Semi-Furnished"],
            ["Fully Furnished"]
        ],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def get_confirmation_keyboard():
    """Keyboard for yes/no confirmation."""
    return ReplyKeyboardMarkup(
        [["✅ Yes, Save", "❌ No, Cancel"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def get_main_menu_keyboard():
    """Main menu keyboard."""
    return ReplyKeyboardMarkup(
        [
            ["➕ Add Property", "🔍 Search"],
            ["📋 My Properties", "ℹ️ Help"]
        ],
        resize_keyboard=True
    )


def format_property_summary(property_data: dict) -> str:
    """Format property data for display."""
    listing = "🔑 For Rent" if property_data.get("listing_type") == "rent" else "🏠 For Sale"
    
    lines = [
        f"**{listing}**",
        "",
        f"🏷️ Type: {property_data.get('property_type', 'N/A').title()}",
        f"📍 Location: {property_data.get('locality', '')} {property_data.get('city', 'N/A')}",
    ]
    
    if property_data.get("bedrooms"):
        lines.append(f"🛏️ Bedrooms: {property_data['bedrooms']}")
    
    if property_data.get("bathrooms"):
        lines.append(f"🚿 Bathrooms: {property_data['bathrooms']}")
    
    if property_data.get("carpet_area"):
        lines.append(f"📐 Area: {property_data['carpet_area']} sq ft")
    
    price = property_data.get("price", 0)
    if property_data.get("listing_type") == "rent":
        lines.append(f"💰 Rent: ₹{price:,.0f}/month")
    else:
        if price >= 10000000:
            lines.append(f"💰 Price: ₹{price/10000000:.2f} Cr")
        elif price >= 100000:
            lines.append(f"💰 Price: ₹{price/100000:.2f} L")
        else:
            lines.append(f"💰 Price: ₹{price:,.0f}")
    
    if property_data.get("furnishing"):
        lines.append(f"🪑 Furnishing: {property_data['furnishing'].replace('-', ' ').title()}")
    
    return "\n".join(lines)
