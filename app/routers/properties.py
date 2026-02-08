"""
Properties CRUD API router.
Handles property creation, listing, updates, and deletion.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Property, PropertyFeature, PropertyTransport, PropertyMedia, User
from app.schemas import (
    PropertyCreate, PropertyUpdate, PropertyResponse, PropertyListResponse,
    PropertyFeatureCreate, PropertyTransportCreate
)

router = APIRouter(prefix="/properties", tags=["properties"])


async def get_or_create_user(db: AsyncSession, telegram_id: int) -> User:
    """Get existing user or create new one."""
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        await db.flush()
    
    return user


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    telegram_id: int = Query(..., description="User's Telegram ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new property listing.
    
    The property can be for rent or sale, as specified in listing_type.
    """
    # Get or create user
    user = await get_or_create_user(db, telegram_id)
    
    # Create property
    property_dict = property_data.model_dump(exclude={"features", "transport", "media"})
    property_obj = Property(user_id=user.id, **property_dict)
    db.add(property_obj)
    await db.flush()  # Get property ID
    
    # Add features if provided
    if property_data.features:
        feature = PropertyFeature(
            property_id=property_obj.id,
            **property_data.features.model_dump()
        )
        db.add(feature)
    
    # Add transport entries
    for transport in property_data.transport:
        transport_obj = PropertyTransport(
            property_id=property_obj.id,
            **transport.model_dump()
        )
        db.add(transport_obj)
    
    # Add media entries
    for media in property_data.media:
        media_obj = PropertyMedia(
            property_id=property_obj.id,
            **media.model_dump()
        )
        db.add(media_obj)
    
    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(Property)
        .options(
            selectinload(Property.features),
            selectinload(Property.transport),
            selectinload(Property.media)
        )
        .where(Property.id == property_obj.id)
    )
    return result.scalar_one()


@router.get("/", response_model=PropertyListResponse)
async def list_properties(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    listing_type: Optional[str] = Query(None, description="Filter by rent/sell"),
    city: Optional[str] = Query(None),
    bedrooms: Optional[int] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    property_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    List properties with optional filters.
    """
    # Build query
    query = select(Property).options(
        selectinload(Property.features),
        selectinload(Property.transport),
        selectinload(Property.media)
    ).where(Property.status == "available")
    
    count_query = select(func.count(Property.id)).where(Property.status == "available")
    
    # Apply filters
    if listing_type:
        query = query.where(Property.listing_type == listing_type)
        count_query = count_query.where(Property.listing_type == listing_type)
    
    if city:
        query = query.where(Property.city.ilike(f"%{city}%"))
        count_query = count_query.where(Property.city.ilike(f"%{city}%"))
    
    if bedrooms:
        query = query.where(Property.bedrooms == bedrooms)
        count_query = count_query.where(Property.bedrooms == bedrooms)
    
    if min_price:
        query = query.where(Property.price >= min_price)
        count_query = count_query.where(Property.price >= min_price)
    
    if max_price:
        query = query.where(Property.price <= max_price)
        count_query = count_query.where(Property.price <= max_price)
    
    if property_type:
        query = query.where(Property.property_type == property_type)
        count_query = count_query.where(Property.property_type == property_type)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Property.created_at.desc()).offset(offset).limit(page_size)
    
    # Execute
    result = await db.execute(query)
    properties = result.scalars().all()
    
    return PropertyListResponse(
        items=list(properties),
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )


@router.get("/my", response_model=List[PropertyResponse])
async def get_my_properties(
    telegram_id: int = Query(..., description="User's Telegram ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get all properties for a specific user."""
    # Get user
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return []
    
    # Get properties
    result = await db.execute(
        select(Property)
        .options(
            selectinload(Property.features),
            selectinload(Property.transport),
            selectinload(Property.media)
        )
        .where(Property.user_id == user.id)
        .order_by(Property.created_at.desc())
    )
    
    return result.scalars().all()


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a single property by ID."""
    result = await db.execute(
        select(Property)
        .options(
            selectinload(Property.features),
            selectinload(Property.transport),
            selectinload(Property.media)
        )
        .where(Property.id == property_id)
    )
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return property_obj


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    updates: PropertyUpdate,
    telegram_id: int = Query(..., description="User's Telegram ID"),
    db: AsyncSession = Depends(get_db)
):
    """Update a property. Only the owner can update."""
    # Get user
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found"
        )
    
    # Get property
    result = await db.execute(
        select(Property)
        .options(
            selectinload(Property.features),
            selectinload(Property.transport),
            selectinload(Property.media)
        )
        .where(Property.id == property_id, Property.user_id == user.id)
    )
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or you don't have permission"
        )
    
    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(property_obj, field, value)
    
    await db.commit()
    await db.refresh(property_obj)
    
    return property_obj


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: UUID,
    telegram_id: int = Query(..., description="User's Telegram ID"),
    db: AsyncSession = Depends(get_db)
):
    """Delete a property. Only the owner can delete."""
    # Get user
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found"
        )
    
    # Get property
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user.id)
    )
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or you don't have permission"
        )
    
    await db.delete(property_obj)
    await db.commit()
