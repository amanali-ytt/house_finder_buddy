"""
SQLAlchemy ORM models matching the PostgreSQL schema.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
import enum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Text,
    ForeignKey, Numeric, Enum as SQLEnum, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class ListingType(str, enum.Enum):
    RENT = "rent"
    SELL = "sell"


class PropertyType(str, enum.Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    PLOT = "plot"
    COMMERCIAL = "commercial"
    PG = "pg"
    OTHER = "other"


class FurnishingStatus(str, enum.Enum):
    UNFURNISHED = "unfurnished"
    SEMI_FURNISHED = "semi-furnished"
    FULLY_FURNISHED = "fully-furnished"


class PropertyStatus(str, enum.Enum):
    AVAILABLE = "available"
    SOLD = "sold"
    RENTED = "rented"
    INACTIVE = "inactive"


# =============================================================================
# MODELS
# =============================================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    phone = Column(String(20))
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(50), default="user")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    properties = relationship("Property", back_populates="owner", cascade="all, delete-orphan")
    conversation_states = relationship("ConversationState", back_populates="user", cascade="all, delete-orphan")


class Property(Base):
    __tablename__ = "properties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Listing Details
    listing_type = Column(SQLEnum(ListingType), nullable=False)
    property_type = Column(SQLEnum(PropertyType), nullable=False)
    title = Column(String(500))
    description = Column(Text)
    
    # Pricing
    price = Column(Numeric(15, 2), nullable=False)
    price_negotiable = Column(Boolean, default=True)
    security_deposit = Column(Numeric(15, 2))
    maintenance_monthly = Column(Numeric(10, 2))
    
    # Location
    address = Column(Text)
    city = Column(String(100), nullable=False, index=True)
    locality = Column(String(200), index=True)
    pincode = Column(String(10))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    
    # Property Specs
    bedrooms = Column(Integer, index=True)
    bathrooms = Column(Integer)
    balconies = Column(Integer, default=0)
    carpet_area = Column(Numeric(10, 2))
    built_up_area = Column(Numeric(10, 2))
    super_built_up_area = Column(Numeric(10, 2))
    floor_number = Column(Integer)
    total_floors = Column(Integer)
    facing = Column(String(20))
    age_of_property = Column(Integer)
    
    # Availability
    furnishing = Column(SQLEnum(FurnishingStatus), default=FurnishingStatus.UNFURNISHED)
    available_from = Column(Date)
    status = Column(SQLEnum(PropertyStatus), default=PropertyStatus.AVAILABLE, index=True)
    
    # Preferences
    preferred_tenant = Column(String(100))
    pets_allowed = Column(Boolean, default=False)
    
    # Metadata
    source = Column(String(50), default="chat")
    raw_input_text = Column(Text)
    metadata = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="properties")
    features = relationship("PropertyFeature", back_populates="property", uselist=False, cascade="all, delete-orphan")
    transport = relationship("PropertyTransport", back_populates="property", cascade="all, delete-orphan")
    media = relationship("PropertyMedia", back_populates="property", cascade="all, delete-orphan")


class PropertyFeature(Base):
    __tablename__ = "property_features"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    
    # Parking
    has_parking = Column(Boolean, default=False)
    parking_type = Column(String(50))
    parking_count = Column(Integer, default=0)
    
    # Building Amenities
    has_lift = Column(Boolean, default=False)
    has_power_backup = Column(Boolean, default=False)
    has_water_supply_24x7 = Column(Boolean, default=False)
    has_security = Column(Boolean, default=False)
    has_cctv = Column(Boolean, default=False)
    has_intercom = Column(Boolean, default=False)
    
    # Recreation
    has_gym = Column(Boolean, default=False)
    has_swimming_pool = Column(Boolean, default=False)
    has_club_house = Column(Boolean, default=False)
    has_children_play_area = Column(Boolean, default=False)
    has_garden = Column(Boolean, default=False)
    has_sports_facility = Column(Boolean, default=False)
    
    # Convenience
    has_gas_pipeline = Column(Boolean, default=False)
    has_ac = Column(Boolean, default=False)
    has_wifi = Column(Boolean, default=False)
    has_geyser = Column(Boolean, default=False)
    has_washing_machine = Column(Boolean, default=False)
    has_refrigerator = Column(Boolean, default=False)
    has_tv = Column(Boolean, default=False)
    has_modular_kitchen = Column(Boolean, default=False)
    has_wardrobe = Column(Boolean, default=False)
    
    additional_features = Column(JSONB, default=[])
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    property = relationship("Property", back_populates="features")


class PropertyTransport(Base):
    __tablename__ = "property_transport"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    
    transport_type = Column(String(50), nullable=False)
    name = Column(String(200))
    distance_km = Column(Numeric(5, 2))
    distance_minutes = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    property = relationship("Property", back_populates="transport")


class PropertyMedia(Base):
    __tablename__ = "property_media"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    
    media_type = Column(String(20), nullable=False)
    file_url = Column(Text, nullable=False)
    file_name = Column(String(255))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    property = relationship("Property", back_populates="media")


class UserQuery(Base):
    __tablename__ = "user_queries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    raw_query = Column(Text, nullable=False)
    parsed_filters = Column(JSONB)
    result_count = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ConversationState(Base):
    __tablename__ = "conversation_states"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    state_type = Column(String(50), nullable=False)
    current_step = Column(String(100))
    collected_data = Column(JSONB, default={})
    expires_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="conversation_states")
