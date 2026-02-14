"""
LLM helper functions for the Telegram bot.
Wraps the NvidiaLLMClient for property validation, normalization, and search.
"""

import json
import re
import logging
from typing import Optional, Dict, Any, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.llm_client import llm_client
from app.agents.prompts import QUERY_PLANNER_SYSTEM
from app.services.file_processor import file_processor

logger = logging.getLogger(__name__)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences and thinking tags."""
    text = text.strip()
    
    # Remove <think>...</think> blocks (DeepSeek reasoning)
    text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
    
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            json_lines.append(line)
        text = "\n".join(json_lines)
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in response
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON array
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")


# ─── DOCUMENT VALIDATION ─────────────────────────────────────────────────────

VALIDATION_PROMPT = """You are a document validation agent. Determine if a text contains property/real estate information.

A valid property document contains: property type, price/rent, location, or specifications.

Return ONLY a JSON object (no markdown, no explanation):
{"is_property_document": true, "confidence": 0.85, "reason": "Contains property listings", "properties_found": 3}

Or if NOT property:
{"is_property_document": false, "confidence": 0.95, "reason": "Not a property document"}"""


async def validate_property_document(text: str) -> Dict[str, Any]:
    """Use LLM to check if text contains property information."""
    snippet = text[:3000]
    
    try:
        response = await llm_client.complete(
            system_prompt=VALIDATION_PROMPT,
            user_message=f"Is this a property document?\n\n{snippet}",
            temperature=0.2,
            max_tokens=256,
        )
        
        logger.info(f"📋 VALIDATE: Response: {response[:200]}")
        result = _parse_json_response(response)
        return {
            "is_property_document": bool(result.get("is_property_document", False)),
            "confidence": float(result.get("confidence", 0)),
            "reason": str(result.get("reason", "Unknown")),
            "properties_found": int(result.get("properties_found", 0)),
        }
    except Exception as e:
        logger.error(f"❌ VALIDATE error: {e}")
        # Default to True so we don't block users
        return {
            "is_property_document": True,
            "confidence": 0.5,
            "reason": f"Validation uncertain, proceeding anyway",
            "properties_found": 0,
        }


# ─── PROPERTY NORMALIZATION ──────────────────────────────────────────────────

EXTRACT_ALL_PROMPT = """Extract ALL properties from this text. Return a JSON object with a "properties" array.

Each property needs:
- listing_type: "rent" or "sell" (default "rent")
- property_type: "apartment"|"house"|"villa"|"plot"|"commercial"|"pg"|"other"
- title: short description
- price: number only (25000 not "25k")
- city: city name
- locality: area name
- bedrooms: number (0 if unknown)
- bathrooms: number (0 if unknown)
- furnishing: "unfurnished"|"semi-furnished"|"fully-furnished" or null
- contact_phone: phone/mobile number found near this property listing (include country code if present)
- google_maps_url: Google Maps link if found (full URL starting with https://maps.google.com or https://goo.gl/maps)

Rules:
- "flat" = "apartment"
- "PG"/"paying guest" = "pg"
- Price: "25k" = 25000, "50L" = 5000000, "1.5Cr" = 15000000
- Extract EVERY property you can find
- Look for phone numbers near each property listing (e.g., "Contact: 9876543210")
- Look for Google Maps links near each property
- Return ONLY valid JSON, no markdown, no explanation

Example response:
{"properties": [{"listing_type": "rent", "property_type": "pg", "title": "PG in Vepery", "price": 12000, "city": "Chennai", "locality": "Vepery", "bedrooms": 1, "bathrooms": 1, "furnishing": "fully-furnished", "contact_phone": "9876543210", "google_maps_url": "https://maps.google.com/..."}]}"""


async def normalize_property_text(text: str) -> List[Dict[str, Any]]:
    """Extract and normalize ALL properties from text in one LLM call."""
    logger.info(f"📝 NORMALIZE: Starting, text length={len(text)}")
    
    # Truncate to prevent overwhelming the LLM
    snippet = text[:4000]
    
    try:
        response = await llm_client.complete(
            system_prompt=EXTRACT_ALL_PROMPT,
            user_message=f"Extract ALL properties:\n\n{snippet}",
            temperature=0.2,
            max_tokens=4096,
        )
        
        logger.info(f"📝 NORMALIZE: Response length={len(response)}")
        logger.info(f"📝 NORMALIZE: Preview: {response[:500]}")
        
        data = _parse_json_response(response)
        
        # Handle {"properties": [...]}
        if isinstance(data, dict) and "properties" in data:
            raw_props = data["properties"]
        elif isinstance(data, list):
            raw_props = data
        elif isinstance(data, dict):
            raw_props = [data]
        else:
            logger.warning(f"📝 NORMALIZE: Unexpected type: {type(data)}")
            raw_props = []
        
        properties = []
        for prop in raw_props:
            if isinstance(prop, dict):
                _clean_property(prop)
                properties.append(prop)
        
        logger.info(f"✅ NORMALIZE: Extracted {len(properties)} properties")
        return properties
        
    except Exception as e:
        logger.error(f"❌ NORMALIZE FAILED: {e}", exc_info=True)
        return []


def _clean_property(prop: Dict[str, Any]):
    """Ensure required fields have defaults and valid values."""
    prop.setdefault("listing_type", "rent")
    prop.setdefault("property_type", "other")
    prop.setdefault("city", "Unknown")
    prop.setdefault("price", 0)
    prop.setdefault("title", "Untitled Property")
    prop.setdefault("bedrooms", None)
    prop.setdefault("furnishing", None)
    prop.setdefault("status", "available")
    
    # Normalize property_type
    pt_map = {"flat": "apartment", "flats": "apartment", "paying guest": "pg", "hostel": "pg"}
    if isinstance(prop.get("property_type"), str):
        prop["property_type"] = pt_map.get(prop["property_type"].lower(), prop["property_type"].lower())
    
    allowed_types = {"apartment", "house", "villa", "plot", "commercial", "pg", "other"}
    if prop.get("property_type") not in allowed_types:
        prop["property_type"] = "other"
    
    # Normalize furnishing
    furn_map = {"furnished": "fully-furnished", "fully furnished": "fully-furnished",
                "semi": "semi-furnished", "semi furnished": "semi-furnished"}
    if isinstance(prop.get("furnishing"), str):
        val = furn_map.get(prop["furnishing"].lower(), prop["furnishing"].lower())
        allowed_furn = {"unfurnished", "semi-furnished", "fully-furnished"}
        prop["furnishing"] = val if val in allowed_furn else None
    
    prop.setdefault("contact_phone", "")
    prop.setdefault("google_maps_url", "")
    
    # Ensure price is numeric
    try:
        prop["price"] = float(prop["price"])
    except (ValueError, TypeError):
        prop["price"] = 0
    
    # Normalize listing_type
    if prop.get("listing_type") not in ("rent", "sell"):
        prop["listing_type"] = "rent"
    
    # Clean phone number (remove spaces, dashes)
    phone = str(prop.get("contact_phone", "")).strip()
    phone = phone.replace(" ", "").replace("-", "")
    if phone and not phone.startswith("+"):
        # If 10 digits, assume Indian number
        if len(phone) == 10 and phone.isdigit():
            phone = "+91" + phone
    prop["contact_phone"] = phone
    
    # Clean maps URL
    maps_url = str(prop.get("google_maps_url", "")).strip()
    if maps_url and not maps_url.startswith("http"):
        maps_url = ""  # Invalid URL
    prop["google_maps_url"] = maps_url


# ─── FILE PROCESSING ─────────────────────────────────────────────────────────

async def process_uploaded_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Process an uploaded file: extract text → validate → normalize."""
    try:
        # Step 1: Extract text
        logger.info(f"📁 PROCESS: Extracting text from '{filename}'...")
        raw_text = file_processor.extract_text(file_bytes, filename)
        if not raw_text or len(raw_text.strip()) < 20:
            logger.warning("📁 PROCESS: No text extracted")
            return {"success": False, "error": "Could not extract text from the file."}
        logger.info(f"📁 PROCESS: Extracted {len(raw_text)} characters")
        
        # Step 2: Validate
        logger.info("📁 PROCESS: Validating document...")
        validation = await validate_property_document(raw_text)
        logger.info(f"📁 PROCESS: Validation: {validation}")
        
        if not validation["is_property_document"]:
            return {
                "success": False,
                "validation": validation,
                "error": f"Not a property document. {validation['reason']}",
            }
        
        # Step 3: Normalize
        logger.info("📁 PROCESS: Extracting properties via LLM...")
        properties = await normalize_property_text(raw_text)
        logger.info(f"📁 PROCESS: Got {len(properties)} properties")
        
        if not properties:
            return {
                "success": False,
                "validation": validation,
                "error": "Found property info but couldn't extract structured data.",
            }
        
        return {
            "success": True,
            "validation": validation,
            "properties": properties,
            "raw_text": raw_text,
        }
        
    except Exception as e:
        logger.error(f"📁 PROCESS ERROR: {e}", exc_info=True)
        return {"success": False, "error": f"Error: {str(e)}"}


# ─── SEARCH / QUERY PLANNING ─────────────────────────────────────────────────

async def plan_search_query(user_query: str) -> Dict[str, Any]:
    """Convert natural language search to structured filters."""
    response = await llm_client.complete(
        system_prompt=QUERY_PLANNER_SYSTEM,
        user_message=f"User Query: {user_query}\n\nConvert to structured filters. Return JSON.",
        temperature=0.2,
        max_tokens=512,
    )
    
    query_plan = _parse_json_response(response)
    
    cleaned_filters = []
    for f in query_plan.get("filters", []):
        field = f.get("field", "").lower()
        if field == "listing_type":
            continue
        if field == "price" and f.get("operator") == "=" and f.get("value") in (0, "0"):
            continue
        
        if field == "property_type" and isinstance(f.get("value"), str):
            pt_map = {"flat": "apartment", "flats": "apartment", "paying guest": "pg"}
            f["value"] = pt_map.get(f["value"].lower(), f["value"].lower())
        
        if field == "furnishing" and isinstance(f.get("value"), str):
            furn_map = {"furnished": "fully-furnished", "semi": "semi-furnished"}
            f["value"] = furn_map.get(f["value"].lower(), f["value"].lower())
        
        cleaned_filters.append(f)
    
    query_plan["filters"] = cleaned_filters
    return query_plan


# ─── CHAT-BASED PROPERTY INPUT ───────────────────────────────────────────────

CHAT_NORMALIZER_PROMPT = """Extract property info from this chat message. Return ONLY valid JSON:
{"listing_type": "rent|sell", "property_type": "apartment|house|villa|plot|commercial|pg|other", "title": "title", "price": 25000, "city": "City", "locality": "Area", "bedrooms": 2, "bathrooms": 2, "carpet_area": 950, "furnishing": "unfurnished|semi-furnished|fully-furnished", "contact_phone": "9876543210", "google_maps_url": "https://maps.google.com/...", "confidence_score": 0.8, "missing_fields": ["bathrooms"]}

Rules: "flat"="apartment", "PG"="pg", "25k"=25000, "50L"=5000000. Default listing_type to "rent". Extract any phone number and Google Maps link if provided."""


async def normalize_chat_message(message: str, collected_so_far: Dict = None) -> Dict[str, Any]:
    """Normalize a chat message into property data."""
    context = ""
    if collected_so_far:
        context = f"\n\nAlready collected: {json.dumps(collected_so_far)}\nMerge with new info."
    
    response = await llm_client.complete(
        system_prompt=CHAT_NORMALIZER_PROMPT,
        user_message=f"Extract property info:{context}\n\n{message}",
        temperature=0.2,
        max_tokens=512,
    )
    
    data = _parse_json_response(response)
    _clean_property(data)
    return data
