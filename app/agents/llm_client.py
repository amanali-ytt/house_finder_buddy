"""
Mock LLM Client - Uses rule-based logic to simulate LLM responses.
No API required! Perfect for testing the complete pipeline.

This simulates what an LLM would return for property normalization
and query planning based on pattern matching.
"""

import json
import re
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel


class MockLLMClient:
    """
    Mock LLM that uses pattern matching to simulate realistic responses.
    No external API needed - perfect for testing!
    """
    
    def __init__(self):
        self.model = "mock-llm-v1"
    
    def _extract_property_from_text(self, text: str) -> Dict[str, Any]:
        """Extract property details using regex patterns."""
        result = {
            "listing_type": "rent",
            "property_type": "apartment",
            "title": "Property Listing",
            "city": None,
            "locality": None,
            "price": None,
            "bedrooms": None,
            "nearest_metro": None,
            "metro_distance": None,
            "contact": None,
            "confidence_score": 0.85,
            "missing_fields": []
        }
        
        text_lower = text.lower()
        
        # Detect listing type
        if "sale" in text_lower or "sell" in text_lower or "buy" in text_lower:
            result["listing_type"] = "sell"
        else:
            result["listing_type"] = "rent"
        
        # Extract rent/price - look for patterns like "45k", "25000", "24000 per"
        rent_patterns = [
            r'rent[:\s]+(\d+)k',
            r'rent[:\s]+₹?(\d{4,})',
            r'(\d+)k[/\s]*month',
            r'₹(\d{4,})[/\s]*(?:month|per)',
            r'(\d{4,})\s*(?:per|/)\s*(?:month|person)',
        ]
        for pattern in rent_patterns:
            match = re.search(pattern, text_lower)
            if match:
                price = int(match.group(1))
                if price < 1000:  # It's in 'k' format
                    price *= 1000
                result["price"] = price
                break
        
        # Extract city
        cities = ["chennai", "mumbai", "bangalore", "delhi", "hyderabad", "pune", "kolkata"]
        for city in cities:
            if city in text_lower:
                result["city"] = city.title()
                break
        
        # Extract locality from address patterns
        locality_patterns = [
            r'(?:in|at|near)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            r',\s*([A-Za-z]+(?:\s+[A-Za-z]+)?),',
            r'locality[:\s]+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
        ]
        for pattern in locality_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                locality = match.group(1).strip()
                if locality.lower() not in cities and len(locality) > 2:
                    result["locality"] = locality
                    break
        
        # Extract metro station
        metro_patterns = [
            r'(?:nearest\s+)?metro(?:\s+station)?[:\s]+([^,\n]+)',
            r'near\s+([A-Za-z]+)\s+metro',
        ]
        for pattern in metro_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["nearest_metro"] = match.group(1).strip()[:50]
                break
        
        # Extract metro distance
        distance_patterns = [
            r'(?:metro)?(?:\s+station)?\s*distance[:\s]+(\d+\.?\d*)\s*km',
            r'(\d+\.?\d*)\s*km\s*(?:from\s+)?metro',
        ]
        for pattern in distance_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["metro_distance"] = float(match.group(1))
                break
        
        # Extract contact
        contact_match = re.search(r'(?:\+91\s*)?(\d{10})', text)
        if contact_match:
            result["contact"] = contact_match.group(1)
        
        # Detect property type
        if "pg" in text_lower or "paying guest" in text_lower:
            result["property_type"] = "pg"
        elif "villa" in text_lower:
            result["property_type"] = "villa"
        elif "house" in text_lower:
            result["property_type"] = "house"
        elif "flat" in text_lower or "apartment" in text_lower:
            result["property_type"] = "apartment"
        
        # Extract bedrooms
        bhk_match = re.search(r'(\d)\s*bhk', text_lower)
        if bhk_match:
            result["bedrooms"] = int(bhk_match.group(1))
        
        # Calculate missing fields
        required = ["city", "price"]
        for field in required:
            if not result.get(field):
                result["missing_fields"].append(field)
        
        # Generate title
        parts = []
        if result.get("bedrooms"):
            parts.append(f"{result['bedrooms']}BHK")
        parts.append(result["property_type"].title())
        if result.get("listing_type") == "rent":
            parts.append("for Rent")
        else:
            parts.append("for Sale")
        if result.get("locality"):
            parts.append(f"in {result['locality']}")
        result["title"] = " ".join(parts)
        
        return result
    
    def _parse_search_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language search query into filters."""
        result = {
            "intent": "rent",
            "filters": [],
            "sort_by": "price",
            "sort_order": "asc"
        }
        
        query_lower = query.lower()
        
        # Detect intent
        if "buy" in query_lower or "sale" in query_lower or "sell" in query_lower:
            result["intent"] = "buy"
            result["filters"].append({"field": "listing_type", "operator": "=", "value": "sell"})
        else:
            result["filters"].append({"field": "listing_type", "operator": "=", "value": "rent"})
        
        # Extract city
        cities = ["chennai", "mumbai", "bangalore", "delhi", "hyderabad", "pune"]
        for city in cities:
            if city in query_lower:
                result["filters"].append({"field": "city", "operator": "=", "value": city.title()})
                break
        
        # Extract BHK
        bhk_match = re.search(r'(\d)\s*bhk', query_lower)
        if bhk_match:
            result["filters"].append({"field": "bedrooms", "operator": "=", "value": int(bhk_match.group(1))})
        
        # Extract price constraints
        under_match = re.search(r'under\s+(\d+)k?', query_lower)
        if under_match:
            price = int(under_match.group(1))
            if price < 1000:
                price *= 1000
            result["filters"].append({"field": "price", "operator": "<=", "value": price})
        
        below_match = re.search(r'below\s+(\d+)k?', query_lower)
        if below_match:
            price = int(below_match.group(1))
            if price < 1000:
                price *= 1000
            result["filters"].append({"field": "price", "operator": "<=", "value": price})
        
        # Extract property type
        if "flat" in query_lower or "apartment" in query_lower:
            result["filters"].append({"field": "property_type", "operator": "=", "value": "apartment"})
        elif "pg" in query_lower:
            result["filters"].append({"field": "property_type", "operator": "=", "value": "pg"})
        elif "villa" in query_lower:
            result["filters"].append({"field": "property_type", "operator": "=", "value": "villa"})
        
        # Check for amenities
        if "parking" in query_lower:
            result["filters"].append({"field": "has_parking", "operator": "=", "value": True})
        if "gym" in query_lower:
            result["filters"].append({"field": "has_gym", "operator": "=", "value": True})
        if "metro" in query_lower:
            result["filters"].append({"field": "near_metro", "operator": "=", "value": True})
        
        return result
    
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Simulate LLM completion using rule-based logic."""
        
        # Detect task type from system prompt
        if "extract" in system_prompt.lower() or "normaliz" in system_prompt.lower():
            # Property normalization task
            result = self._extract_property_from_text(user_message)
            return json.dumps(result, indent=2)
        
        elif "filter" in system_prompt.lower() or "query" in system_prompt.lower():
            # Query planning task
            result = self._parse_search_query(user_message)
            return json.dumps(result, indent=2)
        
        else:
            # Generic response
            return "Hello! I'm a mock LLM for testing purposes."
    
    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Handle conversation history."""
        last_message = messages[-1]["content"] if messages else ""
        return await self.complete(system_prompt, last_message)
    
    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> BaseModel:
        """Get structured response validated against Pydantic model."""
        response = await self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            response_format={"type": "json_object"}
        )
        data = json.loads(response)
        return response_model(**data)
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get provider info."""
        return {
            "provider": "mock",
            "model": self.model,
            "status": "ready",
            "free": True,
            "no_api_required": True
        }


# Singleton instance
llm_client = MockLLMClient()
