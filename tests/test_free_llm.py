"""
Optional live tests for the NVIDIA-backed LLM integration.
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.llm_client import llm_client


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.getenv("NVIDIA_API_KEY"), reason="NVIDIA_API_KEY not configured"),
]


async def test_llm_connection():
    response = await llm_client.complete(
        system_prompt="You are a helpful assistant. Be very brief.",
        user_message="Say hello in one sentence.",
        temperature=0.5,
        max_tokens=100,
    )

    assert response.strip()


async def test_property_normalization():
    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM

    sample_property = """
    2BHK Apartment for Rent in OMR, Chennai
    Rent: 25000/month
    Near Thoraipakkam Metro Station (1.5 km)
    Fully furnished, 1100 sq ft carpet area
    Contact: 9876543210
    Has parking, gym, and power backup
    """

    response = await llm_client.complete(
        system_prompt=PROPERTY_NORMALIZER_SYSTEM,
        user_message=f"Extract and normalize:\n\n{sample_property}",
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    data = json.loads(response)
    assert data["city"].lower() == "chennai"


async def test_query_planning():
    query_prompt = """You are a property search query planner. Convert the user's natural language
property search into a structured JSON with these fields:
- intent: "rent", "buy", or "search"
- filters: array of {field, operator, value} objects
- sort_by: field to sort by (e.g. "price", "created_at")
- sort_order: "asc" or "desc"

Valid fields: listing_type, property_type, price, city, locality, bedrooms, bathrooms,
carpet_area, furnishing, has_parking, has_gym, near_metro.
Valid operators: =, !=, >, >=, <, <=, like, in"""

    response = await llm_client.complete(
        system_prompt=query_prompt,
        user_message="Query: 2BHK flat for rent in Chennai under 25000",
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    data = json.loads(response)
    assert "intent" in data
    assert "filters" in data


async def test_pdf_normalization():
    pdf_path = "Chennai_Properties.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip(f"PDF not found: {pdf_path}")

    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM
    from app.services.file_processor import file_processor

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    extracted_text = file_processor.extract_from_pdf(file_bytes)
    properties = file_processor.parse_multiple_properties(extracted_text)

    if not properties:
        pytest.skip("No property chunks detected in sample PDF")

    response = await llm_client.complete(
        system_prompt=PROPERTY_NORMALIZER_SYSTEM,
        user_message=f"Extract from:\n\n{properties[0][:1500]}",
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    data = json.loads(response)
    assert "property_type" in data


async def main():
    await test_llm_connection()
    await test_property_normalization()
    await test_query_planning()
    await test_pdf_normalization()


if __name__ == "__main__":
    asyncio.run(main())
