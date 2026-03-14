"""
Bot Database Interface.
Uses the main FastAPI async SQLAlchemy PostgreSQL database instead of SQLite.
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, update, desc

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import (
    User,
    Property,
    PropertyFeature,
    PropertyTransport,
    PropertyStatus,
    ListingType,
    PropertyType,
    FurnishingStatus,
)
from app.database import async_engine, Base

logger = logging.getLogger(__name__)


def _normalize_property_type(value: Any) -> PropertyType:
    """Convert incoming property types to the DB enum."""
    if isinstance(value, PropertyType):
        return value

    normalized = str(value or "").strip().lower()
    alias_map = {
        "flat": PropertyType.APARTMENT,
        "flats": PropertyType.APARTMENT,
        "apartment": PropertyType.APARTMENT,
        "house": PropertyType.HOUSE,
        "villa": PropertyType.VILLA,
        "plot": PropertyType.PLOT,
        "commercial": PropertyType.COMMERCIAL,
        "pg": PropertyType.PG,
        "paying guest": PropertyType.PG,
    }
    return alias_map.get(normalized, PropertyType.OTHER)


def _normalize_furnishing(value: Any) -> FurnishingStatus | None:
    """Convert furnishing text to the DB enum when possible."""
    if isinstance(value, FurnishingStatus):
        return value

    normalized = str(value or "").strip().lower()
    alias_map = {
        "unfurnished": FurnishingStatus.UNFURNISHED,
        "semi": FurnishingStatus.SEMI_FURNISHED,
        "semi furnished": FurnishingStatus.SEMI_FURNISHED,
        "semi-furnished": FurnishingStatus.SEMI_FURNISHED,
        "furnished": FurnishingStatus.FULLY_FURNISHED,
        "fully furnished": FurnishingStatus.FULLY_FURNISHED,
        "fully-furnished": FurnishingStatus.FULLY_FURNISHED,
    }
    return alias_map.get(normalized)


async def init_db():
    """Create tables if they don't exist (handled by FastAPI usually, but safe to call)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database connected via SQLAlchemy (PostgreSQL)")


# ─── USER OPERATIONS ─────────────────────────────────────────────────────────

async def is_new_user(telegram_id: int) -> bool:
    """Check if a Telegram user is new (not in DB)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.id).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none() is None


async def get_or_create_user(
    telegram_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
) -> Dict[str, Any]:
    """Get existing user or create new one. Returns user dict."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            return {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_verified": user.is_verified,
            }

        new_user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(new_user)
        try:
            await session.commit()
            await session.refresh(new_user)
            return {
                "id": str(new_user.id),
                "telegram_id": new_user.telegram_id,
                "username": new_user.username,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "is_verified": new_user.is_verified,
            }
        except Exception as e:
            await session.rollback()
            raise e


async def mark_user_verified(telegram_id: int):
    """Mark a user as verified (completed onboarding)."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(is_verified=True, updated_at=datetime.utcnow())
        )
        await session.commit()


async def is_user_verified(telegram_id: int) -> bool:
    """Check if user has completed onboarding."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.is_verified).where(User.telegram_id == telegram_id)
        )
        val = result.scalar_one_or_none()
        return bool(val)


# ─── PROPERTY OPERATIONS ─────────────────────────────────────────────────────

async def save_property(user_telegram_id: int, prop_data: Dict[str, Any], source: str = "chat") -> str:
    """
    Save a normalized property to the database.
    Returns the stringified UUID of the property.
    """
    async with AsyncSessionLocal() as session:
        # Get user ID
        result = await session.execute(select(User).where(User.telegram_id == user_telegram_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User with telegram_id {user_telegram_id} not found")
        
        prop_type_val = prop_data.get("property_type", "other").lower()
        if prop_type_val not in [e.value for e in PropertyType]:
            prop_type_val = "other"
            
        listing_type_val = prop_data.get("listing_type", "rent").lower()
        if listing_type_val not in [e.value for e in ListingType]:
            listing_type_val = "rent"
            
        furnishing_val = prop_data.get("furnishing", None)
        if furnishing_val and furnishing_val.lower() not in ["unfurnished", "semi-furnished", "fully-furnished"]:
            furnishing_val = None

        new_prop = Property(
            user_id=user.id,
            listing_type=listing_type_val,
            property_type=prop_type_val,
            title=prop_data.get("title", "Untitled Property"),
            description=prop_data.get("description", ""),
            price=float(prop_data.get("price", 0)),
            city=prop_data.get("city", "Unknown"),
            locality=prop_data.get("locality", ""),
            pincode=prop_data.get("pincode", ""),
            bedrooms=int(prop_data.get("bedrooms")) if prop_data.get("bedrooms") is not None else None,
            bathrooms=int(prop_data.get("bathrooms")) if prop_data.get("bathrooms") is not None else None,
            carpet_area=float(prop_data["carpet_area"]) if prop_data.get("carpet_area") else None,
            furnishing=furnishing_val,
            floor_number=int(prop_data.get("floor_number")) if prop_data.get("floor_number") else None,
            total_floors=int(prop_data.get("total_floors")) if prop_data.get("total_floors") else None,
            status=PropertyStatus.AVAILABLE,
            source=source,
            raw_input_text=prop_data.get("raw_input_text", ""),
            # Contact metadata can go loosely into metadata for now or specific columns since they're in schema
        )
        
        features = prop_data.get("features", {})
        if isinstance(features, dict) and features:
            prop_feature = PropertyFeature(
                has_parking=features.get("has_parking", False),
                has_lift=features.get("has_lift", False),
                has_gym=features.get("has_gym", False),
                has_swimming_pool=features.get("has_swimming_pool", False),
                # Add more features parsing or dump entirely to additional_features
                additional_features=features
            )
            new_prop.features = prop_feature
        
        session.add(new_prop)
        await session.commit()
        return str(new_prop.id)


async def find_duplicates(prop: Dict[str, Any]) -> List[Dict]:
    """
    Check if a similar property already exists in the database.
    Matches on: city + price (±10%) + property_type.
    """
    price = float(prop.get("price", 0))
    price_low = price * 0.9
    price_high = price * 1.1
    property_type = _normalize_property_type(prop.get("property_type", "other"))

    async with AsyncSessionLocal() as session:
        query = select(Property).where(
            Property.status == PropertyStatus.AVAILABLE,
            func.lower(Property.city) == str(prop.get("city", "")).lower(),
            Property.property_type == property_type,
            Property.price >= price_low,
            Property.price <= price_high
        )
        
        if prop.get("bedrooms") is not None:
             query = query.where(Property.bedrooms == int(prop["bedrooms"]))
             
        if prop.get("locality"):
             query = query.where(func.lower(Property.locality).like(f"%{prop['locality'].lower()}%"))

        result = await session.execute(query)
        properties = result.scalars().all()
        
        out = []
        for p in properties:
            out.append({
                "id": str(p.id),
                "title": p.title,
                "price": float(p.price),
                "city": p.city,
                "locality": p.locality,
                "property_type": p.property_type.value if hasattr(p.property_type, 'value') else p.property_type,
                "bedrooms": p.bedrooms,
            })
        return out


async def get_user_properties(telegram_id: int) -> List[Dict]:
    """Get all properties for a user."""
    async with AsyncSessionLocal() as session:
        query = select(Property).join(User).where(
            User.telegram_id == telegram_id
        ).order_by(desc(Property.created_at))
        
        result = await session.execute(query)
        properties = result.scalars().all()
        
        out = []
        for p in properties:
            out.append({
                "id": str(p.id),
                "title": p.title,
                "price": float(p.price),
                "city": p.city,
                "locality": p.locality,
                "property_type": p.property_type.value if hasattr(p.property_type, 'value') else p.property_type,
                "bedrooms": p.bedrooms,
                "status": p.status.value if hasattr(p.status, 'value') else p.status,
            })
        return out


async def search_properties(filters: Dict[str, Any]) -> List[Dict]:
    """
    Search properties using a dict of filters from the LLM query plan.
    Returns matching properties.
    """
    if isinstance(filters, list):
        filters = {"filters": filters}

    async with AsyncSessionLocal() as session:
        query = select(Property).where(Property.status == PropertyStatus.AVAILABLE)

        intent = filters.get("intent")
        if intent == "rent":
            query = query.where(Property.listing_type == ListingType.RENT)
        elif intent == "buy":
            query = query.where(Property.listing_type == ListingType.SELL)

        for f in filters.get("filters", []):
            field = f.get("field", "").lower()
            op = f.get("operator", "=")
            value = f.get("value")

            if not field or value is None:
                continue
            if field == "listing_type":
                continue  

            allowed_fields = {
                "city": Property.city, 
                "locality": Property.locality, 
                "property_type": Property.property_type, 
                "price": Property.price, 
                "bedrooms": Property.bedrooms,
                "bathrooms": Property.bathrooms, 
                "carpet_area": Property.carpet_area, 
                "furnishing": Property.furnishing, 
                "floor_number": Property.floor_number,
                "pets_allowed": Property.pets_allowed,
            }
            if field not in allowed_fields:
                continue
                
            col = allowed_fields[field]

            if op == "like":
                query = query.where(func.lower(col).like(f"%{str(value).lower()}%"))
            elif op == "=":
                if field == "property_type" and isinstance(value, str):
                    query = query.where(col == _normalize_property_type(value))
                elif field == "furnishing" and isinstance(value, str):
                    furnishing = _normalize_furnishing(value)
                    if furnishing is None:
                        continue
                    query = query.where(col == furnishing)
                else:
                    query = query.where(col == value)
            elif op == "!=":
                query = query.where(col != value)
            elif op == ">":
                query = query.where(col > value)
            elif op == ">=":
                query = query.where(col >= value)
            elif op == "<":
                query = query.where(col < value)
            elif op == "<=":
                query = query.where(col <= value)

        sort_by = filters.get("sort_by", "price")
        sort_order = filters.get("sort_order", "asc").lower()
        
        order_col = Property.price
        if sort_by == "bedrooms":
            order_col = Property.bedrooms
        elif sort_by == "carpet_area":
            order_col = Property.carpet_area
        elif sort_by == "created_at":
            order_col = Property.created_at
            
        if sort_order == "desc":
            query = query.order_by(desc(order_col))
        else:
            query = query.order_by(order_col)

        limit = min(int(filters.get("limit", 20)), 50)
        query = query.limit(limit)

        result = await session.execute(query)
        properties = result.scalars().all()
        
        out = []
        for p in properties:
             out.append({
                "id": str(p.id),
                "title": p.title,
                "price": float(p.price),
                "city": p.city,
                "locality": p.locality,
                "property_type": p.property_type.value if hasattr(p.property_type, 'value') else p.property_type,
                "bedrooms": p.bedrooms,
                "listing_type": p.listing_type.value if hasattr(p.listing_type, 'value') else p.listing_type,
            })
        return out


async def get_property_count() -> int:
    """Get total number of properties in DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(Property.id)))
        return result.scalar()
