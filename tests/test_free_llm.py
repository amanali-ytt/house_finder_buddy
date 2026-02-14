"""
Test script for NVIDIA LLM Integration (Kimi K2.5).
Tests real API calls to the NVIDIA endpoint.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.llm_client import llm_client


async def test_llm_connection():
    """Test if NVIDIA LLM is reachable."""
    print("🤖 Testing NVIDIA Kimi K2.5 Connection...")
    print("-" * 50)

    info = llm_client.get_provider_info()
    print(f"Provider: {info['provider'].upper()}")
    print(f"Model: {info['model']}")
    print(f"Status: {info['status']}")
    print(f"API URL: {info['api_url']}")

    response = await llm_client.complete(
        system_prompt="You are a helpful assistant. Be very brief.",
        user_message="Say hello in one sentence.",
        temperature=0.5,
        max_tokens=100
    )
    print(f"✅ Response: {response.strip()}")
    return True


async def test_property_normalization():
    """Test property text normalization via NVIDIA LLM."""
    print("\n" + "=" * 50)
    print("🏠 TESTING PROPERTY NORMALIZATION")
    print("=" * 50)

    sample_property = """
    2BHK Apartment for Rent in OMR, Chennai
    Rent: 25000/month
    Near Thoraipakkam Metro Station (1.5 km)
    Fully furnished, 1100 sq ft carpet area
    Contact: 9876543210
    Has parking, gym, and power backup
    """

    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM

    print(f"📝 Input text:\n{sample_property.strip()}\n")

    response = await llm_client.complete(
        system_prompt=PROPERTY_NORMALIZER_SYSTEM,
        user_message=f"Extract and normalize:\n\n{sample_property}",
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    import json
    try:
        data = json.loads(response)
        print("✅ Normalized output:")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print(f"⚠️  Raw response (not JSON):\n{response[:500]}")


async def test_query_planning():
    """Test natural language query planning."""
    print("\n" + "=" * 50)
    print("🔍 TESTING QUERY PLANNING")
    print("=" * 50)

    test_queries = [
        "2BHK flat for rent in Chennai under 25000",
        "3BHK apartment in Mumbai below 50k with parking",
        "PG near metro in Bangalore under 15000",
    ]

    query_prompt = """You are a property search query planner. Convert the user's natural language 
property search into a structured JSON with these fields:
- intent: "rent", "buy", or "search"  
- filters: array of {field, operator, value} objects
- sort_by: field to sort by (e.g. "price", "created_at")
- sort_order: "asc" or "desc"

Valid fields: listing_type, property_type, price, city, locality, bedrooms, bathrooms, 
carpet_area, furnishing, has_parking, has_gym, near_metro.
Valid operators: =, !=, >, >=, <, <=, like, in"""

    for query in test_queries:
        print(f"\n📝 Query: \"{query}\"")

        response = await llm_client.complete(
            system_prompt=query_prompt,
            user_message=f"Query: {query}",
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        import json
        try:
            data = json.loads(response)

            print(f"   Intent: {data.get('intent', 'N/A')}")
            print(f"   Filters:")
            for f in data.get('filters', []):
                print(f"     • {f.get('field')} {f.get('operator')} {f.get('value')}")

        except json.JSONDecodeError:
            print(f"   Raw: {response[:200]}")


async def test_pdf_normalization():
    """Test PDF extraction + LLM normalization if PDF exists."""
    pdf_path = "Chennai_Properties.pdf"

    if not os.path.exists(pdf_path):
        print(f"\n⏭️  Skipping PDF test ({pdf_path} not found)")
        return

    print("\n" + "=" * 50)
    print("📄 TESTING PDF + LLM NORMALIZATION")
    print("=" * 50)

    from app.services.file_processor import file_processor
    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    extracted_text = file_processor.extract_from_pdf(file_bytes)
    print(f"📝 Extracted {len(extracted_text)} characters from PDF")

    properties = file_processor.parse_multiple_properties(extracted_text)
    print(f"🏠 Found {len(properties)} properties\n")

    if not properties:
        return

    # Test normalization on first 2 properties
    import json

    for i, prop_text in enumerate(properties[:2], 1):
        print(f"\n🏠 Property #{i}:")
        print(f"   Raw (first 200 chars): {prop_text[:200]}...")

        response = await llm_client.complete(
            system_prompt=PROPERTY_NORMALIZER_SYSTEM,
            user_message=f"Extract from:\n\n{prop_text[:1500]}",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        try:
            data = json.loads(response)
            print(f"   🏷️  Type: {data.get('listing_type', 'N/A')} | {data.get('property_type', 'N/A')}")
            print(f"   📍 City: {data.get('city', 'N/A')}")
            if data.get('locality'):
                print(f"   📍 Locality: {data.get('locality')}")
            if data.get('price'):
                print(f"   💰 Price: ₹{data.get('price'):,}")
            if data.get('bedrooms'):
                print(f"   🛏️  Bedrooms: {data.get('bedrooms')}")
        except json.JSONDecodeError as e:
            print(f"   ⚠️  Parse error: {e}")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("🧪 Property Bot - NVIDIA Kimi K2.5 LLM Test")
    print("=" * 50)
    print(f"Using: NVIDIA API (model: {llm_client.model})")
    print("=" * 50)

    # Test connection
    await test_llm_connection()

    # Test property normalization
    await test_property_normalization()

    # Test query planning
    await test_query_planning()

    # Test PDF normalization
    await test_pdf_normalization()

    print("\n" + "=" * 50)
    print("✅ All tests complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
