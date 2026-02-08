"""
Property Normalizer Agent - Converts raw text to structured property data.
Uses GPT-4O for complex extraction and normalization.
"""

import json
from typing import Optional, Dict, Any, List

from app.agents.llm_client import llm_client
from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM
from app.schemas import NormalizedPropertyOutput, PropertyCreate, PropertyFeatureCreate, PropertyTransportCreate
from app.schemas import ListingType, PropertyType, FurnishingStatus
from app.config import get_settings

settings = get_settings()


class PropertyNormalizerAgent:
    """
    Agent that extracts and normalizes property information from raw text.
    Handles text from chat messages, PDFs, and Excel files.
    """
    
    def __init__(self):
        self.system_prompt = PROPERTY_NORMALIZER_SYSTEM
    
    async def normalize(
        self,
        raw_text: str,
        source: str = "chat",
        additional_context: Optional[str] = None,
    ) -> NormalizedPropertyOutput:
        """
        Normalize raw property text into structured data.
        
        Args:
            raw_text: Raw extracted text from user/file
            source: Source of text ('chat', 'pdf', 'excel')
            additional_context: Optional context about the input
            
        Returns:
            NormalizedPropertyOutput with structured property data
        """
        # Build user message
        user_message = f"""Source: {source}

Raw Property Text:
{raw_text}

{f'Additional Context: {additional_context}' if additional_context else ''}

Extract and normalize all property information from the above text. Return a valid JSON object."""

        # Use GPT-4O for complex normalization
        response = await llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            model=settings.openai_model_advanced,  # GPT-4O for accuracy
            temperature=0.3,  # Lower for structured output
            response_format={"type": "json_object"}
        )
        
        # Parse response
        try:
            data = json.loads(response)
            return self._validate_and_convert(data)
        except (json.JSONDecodeError, Exception) as e:
            # Return minimal valid output on error
            return NormalizedPropertyOutput(
                listing_type=ListingType.SELL,
                property_type=PropertyType.OTHER,
                price=0,
                city="Unknown",
                confidence_score=0.0,
                missing_fields=["listing_type", "price", "city", "property_type"]
            )
    
    def _validate_and_convert(self, data: Dict[str, Any]) -> NormalizedPropertyOutput:
        """Validate and convert raw LLM output to typed output."""
        # Handle listing_type
        listing_type = data.get("listing_type", "sell").lower()
        if listing_type not in ["rent", "sell"]:
            listing_type = "sell"
        
        # Handle property_type
        property_type = data.get("property_type", "other").lower()
        valid_types = ["apartment", "house", "villa", "plot", "commercial", "pg", "other"]
        if property_type not in valid_types:
            property_type = "other"
        
        # Handle furnishing
        furnishing = data.get("furnishing")
        if furnishing:
            furnishing = furnishing.lower().replace(" ", "-")
            if furnishing not in ["unfurnished", "semi-furnished", "fully-furnished"]:
                furnishing = None
        
        # Build features if present
        features = None
        if "features" in data and data["features"]:
            features = PropertyFeatureCreate(**{
                k: v for k, v in data["features"].items()
                if k.startswith("has_") or k in ["parking_type", "parking_count", "additional_features"]
            })
        
        # Build transport list
        transport = []
        if "transport" in data and isinstance(data["transport"], list):
            for t in data["transport"]:
                if isinstance(t, dict) and "transport_type" in t:
                    transport.append(PropertyTransportCreate(
                        transport_type=t.get("transport_type"),
                        name=t.get("name"),
                        distance_km=t.get("distance_km"),
                        distance_minutes=t.get("distance_minutes")
                    ))
        
        return NormalizedPropertyOutput(
            listing_type=ListingType(listing_type),
            property_type=PropertyType(property_type),
            title=data.get("title"),
            description=data.get("description"),
            price=data.get("price", 0),
            city=data.get("city", "Unknown"),
            locality=data.get("locality"),
            pincode=data.get("pincode"),
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            carpet_area=data.get("carpet_area"),
            built_up_area=data.get("built_up_area"),
            furnishing=FurnishingStatus(furnishing) if furnishing else None,
            features=features,
            transport=transport,
            confidence_score=data.get("confidence_score", 0.5),
            missing_fields=data.get("missing_fields", [])
        )
    
    async def normalize_multiple(
        self,
        property_texts: List[str],
        source: str = "excel",
    ) -> List[NormalizedPropertyOutput]:
        """
        Normalize multiple properties from a list of text chunks.
        
        Args:
            property_texts: List of raw property descriptions
            source: Source of data
            
        Returns:
            List of normalized property outputs
        """
        results = []
        for text in property_texts:
            if text.strip():
                result = await self.normalize(text, source)
                results.append(result)
        return results
    
    def to_property_create(
        self,
        normalized: NormalizedPropertyOutput,
        source: str = "chat",
        raw_text: str = ""
    ) -> PropertyCreate:
        """Convert normalized output to PropertyCreate schema."""
        return PropertyCreate(
            listing_type=normalized.listing_type,
            property_type=normalized.property_type,
            title=normalized.title,
            description=normalized.description,
            price=normalized.price,
            city=normalized.city,
            locality=normalized.locality,
            pincode=normalized.pincode,
            bedrooms=normalized.bedrooms,
            bathrooms=normalized.bathrooms,
            carpet_area=normalized.carpet_area,
            built_up_area=normalized.built_up_area,
            furnishing=normalized.furnishing or FurnishingStatus.UNFURNISHED,
            features=normalized.features,
            transport=normalized.transport,
            source=source,
            raw_input_text=raw_text
        )


# Singleton instance
normalizer_agent = PropertyNormalizerAgent()
