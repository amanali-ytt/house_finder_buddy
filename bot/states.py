"""
Telegram Bot States for conversation flow management.
"""

from enum import Enum, auto


class ConversationState(Enum):
    """States for the property listing conversation flow."""
    
    # Initial states
    IDLE = auto()
    
    # Onboarding flow (new users)
    ONBOARDING_WAITING_DOC = auto()
    ONBOARDING_CONFIRMING = auto()
    
    # Adding property flow (chat)
    ADDING_PROPERTY = auto()
    WAITING_LISTING_TYPE = auto()
    WAITING_PROPERTY_TYPE = auto()
    WAITING_PRICE = auto()
    WAITING_CITY = auto()
    WAITING_BEDROOMS = auto()
    WAITING_CONTACT = auto()
    WAITING_MAPS_URL = auto()
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


def get_confirm_all_keyboard():
    """Keyboard for confirming multiple properties."""
    return ReplyKeyboardMarkup(
        [["✅ Save All", "📝 Review Each", "❌ Cancel"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def get_main_menu_keyboard():
    """Main menu keyboard."""
    return ReplyKeyboardMarkup(
        [
            ["➕ Add Property", "📄 Upload File"],
            ["🔍 Search", "📋 My Properties"],
            ["ℹ️ Help"]
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
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0
    
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
    
    # Contact phone
    phone = property_data.get("contact_phone", "")
    if phone:
        lines.append(f"📞 Contact: {phone}")
    
    # Google Maps
    maps_url = property_data.get("google_maps_url", "")
    if maps_url:
        lines.append(f"🗺️ [View on Maps]({maps_url})")
    
    # Features
    features = property_data.get("features", {})
    if isinstance(features, dict):
        feat_list = [k.replace("has_", "").replace("_", " ").title() 
                     for k, v in features.items() if v]
        if feat_list:
            lines.append(f"✨ Features: {', '.join(feat_list)}")
    
    return "\n".join(lines)


def format_property_card(prop: dict, index: int = 1) -> str:
    """Format a property from the database for display."""
    listing = "🔑 Rent" if prop.get("listing_type") == "rent" else "🏠 Sale"
    price = float(prop.get("price", 0))
    
    if prop.get("listing_type") == "rent":
        price_str = f"₹{price:,.0f}/mo"
    elif price >= 10000000:
        price_str = f"₹{price/10000000:.1f}Cr"
    elif price >= 100000:
        price_str = f"₹{price/100000:.0f}L"
    else:
        price_str = f"₹{price:,.0f}"
    
    bedrooms = prop.get("bedrooms", "?")
    ptype = prop.get("property_type", "property").title()
    loc = prop.get("locality", "")
    city = prop.get("city", "")
    title = prop.get("title", "Property")
    
    card = (
        f"{index}. {listing} | {bedrooms}BHK {ptype}\n"
        f"   📍 {loc}, {city}\n"
        f"   💰 {price_str}"
    )
    
    if prop.get("furnishing"):
        card += f"\n   🪑 {prop['furnishing'].replace('-', ' ').title()}"
    
    # Contact phone
    phone = prop.get("contact_phone", "")
    if phone:
        card += f"\n   📞 {phone}"
    
    # Google Maps
    maps_url = prop.get("google_maps_url", "")
    if maps_url:
        card += f"\n   🗺️ [View on Maps]({maps_url})"
    
    return card
