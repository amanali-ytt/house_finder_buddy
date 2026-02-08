"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ListingType(str, Enum):
    RENT = "rent"
    SELL = "sell"


class PropertyType(str, Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    PLOT = "plot"
    COMMERCIAL = "commercial"
    PG = "pg"
    OTHER = "other"


class FurnishingStatus(str, Enum):
    UNFURNISHED = "unfurnished"
    SEMI_FURNISHED = "semi-furnished"
    FULLY_FURNISHED = "fully-furnished"


class PropertyStatus(str, Enum):
    AVAILABLE = "available"
    SOLD = "sold"
    RENTED = "rented"
    INACTIVE = "inactive"


# =============================================================================
# USER SCHEMAS
# =============================================================================

class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    is_verified: bool
    is_active: bool
    role: str
    created_at: datetime


# =============================================================================
# PROPERTY FEATURE SCHEMAS
# =============================================================================

class PropertyFeatureBase(BaseModel):
    has_parking: bool = False
    parking_type: Optional[str] = None
    parking_count: int = 0
    has_lift: bool = False
    has_power_backup: bool = False
    has_water_supply_24x7: bool = False
    has_security: bool = False
    has_cctv: bool = False
    has_intercom: bool = False
    has_gym: bool = False
    has_swimming_pool: bool = False
    has_club_house: bool = False
    has_children_play_area: bool = False
    has_garden: bool = False
    has_sports_facility: bool = False
    has_gas_pipeline: bool = False
    has_ac: bool = False
    has_wifi: bool = False
    has_geyser: bool = False
    has_washing_machine: bool = False
    has_refrigerator: bool = False
    has_tv: bool = False
    has_modular_kitchen: bool = False
    has_wardrobe: bool = False
    additional_features: List[str] = []


class PropertyFeatureCreate(PropertyFeatureBase):
    pass


class PropertyFeatureResponse(PropertyFeatureBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID


# =============================================================================
# PROPERTY TRANSPORT SCHEMAS
# =============================================================================

class PropertyTransportBase(BaseModel):
    transport_type: str  # 'metro', 'bus_stop', 'railway', 'airport', 'highway'
    name: Optional[str] = None
    distance_km: Optional[Decimal] = None
    distance_minutes: Optional[int] = None


class PropertyTransportCreate(PropertyTransportBase):
    pass


class PropertyTransportResponse(PropertyTransportBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID


# =============================================================================
# PROPERTY MEDIA SCHEMAS
# =============================================================================

class PropertyMediaBase(BaseModel):
    media_type: str  # 'image', 'video', 'document', 'floor_plan'
    file_url: str
    file_name: Optional[str] = None
    is_primary: bool = False
    display_order: int = 0


class PropertyMediaCreate(PropertyMediaBase):
    pass


class PropertyMediaResponse(PropertyMediaBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID


# =============================================================================
# PROPERTY SCHEMAS
# =============================================================================

class PropertyBase(BaseModel):
    listing_type: ListingType
    property_type: PropertyType
    title: Optional[str] = None
    description: Optional[str] = None
    
    # Pricing
    price: Decimal
    price_negotiable: bool = True
    security_deposit: Optional[Decimal] = None
    maintenance_monthly: Optional[Decimal] = None
    
    # Location
    address: Optional[str] = None
    city: str
    locality: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    
    # Property Specs
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    balconies: int = 0
    carpet_area: Optional[Decimal] = None
    built_up_area: Optional[Decimal] = None
    super_built_up_area: Optional[Decimal] = None
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    facing: Optional[str] = None
    age_of_property: Optional[int] = None
    
    # Availability
    furnishing: FurnishingStatus = FurnishingStatus.UNFURNISHED
    available_from: Optional[date] = None
    status: PropertyStatus = PropertyStatus.AVAILABLE
    
    # Preferences
    preferred_tenant: Optional[str] = None
    pets_allowed: bool = False


class PropertyCreate(PropertyBase):
    features: Optional[PropertyFeatureCreate] = None
    transport: List[PropertyTransportCreate] = []
    media: List[PropertyMediaCreate] = []
    source: str = "chat"
    raw_input_text: Optional[str] = None


class PropertyUpdate(BaseModel):
    """Partial update schema - all fields optional."""
    listing_type: Optional[ListingType] = None
    property_type: Optional[PropertyType] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    price_negotiable: Optional[bool] = None
    security_deposit: Optional[Decimal] = None
    maintenance_monthly: Optional[Decimal] = None
    address: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    pincode: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    carpet_area: Optional[Decimal] = None
    furnishing: Optional[FurnishingStatus] = None
    available_from: Optional[date] = None
    status: Optional[PropertyStatus] = None
    preferred_tenant: Optional[str] = None
    pets_allowed: Optional[bool] = None


class PropertyResponse(PropertyBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    source: str
    created_at: datetime
    updated_at: datetime
    
    features: Optional[PropertyFeatureResponse] = None
    transport: List[PropertyTransportResponse] = []
    media: List[PropertyMediaResponse] = []


class PropertyListResponse(BaseModel):
    """Paginated property list response."""
    items: List[PropertyResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =============================================================================
# QUERY SCHEMAS (For natural language search)
# =============================================================================

class QueryFilterOperator(str, Enum):
    EQ = "="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    LIKE = "like"
    IN = "in"


class QueryFilter(BaseModel):
    """Single filter condition from Query Planner Agent."""
    field: str
    operator: QueryFilterOperator
    value: Any


class QueryPlannerOutput(BaseModel):
    """Output from the Query Planner Agent."""
    intent: str  # 'buy', 'rent', 'search'
    filters: List[QueryFilter]
    sort_by: Optional[str] = None
    sort_order: str = "asc"
    limit: int = 20


class NaturalLanguageQuery(BaseModel):
    """Input for natural language search."""
    query: str = Field(..., min_length=3, max_length=500)


class QueryResponse(BaseModel):
    """Response for natural language search."""
    query: str
    interpreted_as: QueryPlannerOutput
    results: List[PropertyResponse]
    total_count: int


# =============================================================================
# AGENT SCHEMAS
# =============================================================================

class NormalizedPropertyOutput(BaseModel):
    """Output from Property Normalizer Agent."""
    listing_type: ListingType
    property_type: PropertyType
    title: Optional[str] = None
    description: Optional[str] = None
    price: Decimal
    city: str
    locality: Optional[str] = None
    pincode: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    carpet_area: Optional[Decimal] = None
    built_up_area: Optional[Decimal] = None
    furnishing: Optional[FurnishingStatus] = None
    
    # Features extracted
    features: Optional[PropertyFeatureCreate] = None
    
    # Transport extracted
    transport: List[PropertyTransportCreate] = []
    
    # Extraction confidence
    confidence_score: float = Field(ge=0.0, le=1.0)
    missing_fields: List[str] = []


class ConversationAgentOutput(BaseModel):
    """Output from Conversation Agent."""
    message_to_user: str
    collected_fields: dict = {}
    next_action: str  # 'ask_field', 'confirm', 'save', 'cancel'
    missing_required_fields: List[str] = []
    is_complete: bool = False
