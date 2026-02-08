"""
Test script using MOCK LLM - No API required!
Uses pattern matching to simulate LLM responses.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.file_processor import file_processor
from app.agents.llm_client import llm_client


async def test_llm_connection():
    """Test if Mock LLM is working."""
    print("🤖 Testing Mock LLM...")
    print("-" * 50)
    
    info = llm_client.get_provider_info()
    print(f"Provider: {info['provider'].upper()}")
    print(f"Model: {info['model']}")
    print(f"No API Required: {info.get('no_api_required', False)}")
    
    response = await llm_client.complete(
        system_prompt="You are a helpful assistant.",
        user_message="Say hello",
        temperature=0.5,
        max_tokens=50
    )
    print(f"✅ Response: {response.strip()}")
    return True


async def test_pdf_with_mock_llm():
    """Test PDF extraction with Mock LLM normalization."""
    pdf_path = "Chennai_Properties.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    print("\n" + "=" * 50)
    print("📄 TESTING PDF + MOCK LLM NORMALIZATION")
    print("=" * 50)
    
    # Extract PDF
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()
    
    extracted_text = file_processor.extract_from_pdf(file_bytes)
    print(f"📝 Extracted {len(extracted_text)} characters from PDF")
    
    # Parse multiple properties
    properties = file_processor.parse_multiple_properties(extracted_text)
    print(f"🏠 Found {len(properties)} properties\n")
    
    if not properties:
        return
    
    # Test normalization on first 3 properties
    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM
    
    print("-" * 50)
    print("Normalizing first 3 properties:")
    print("-" * 50)
    
    for i, prop_text in enumerate(properties[:3], 1):
        print(f"\n🏠 Property #{i}:")
        
        response = await llm_client.complete(
            system_prompt=PROPERTY_NORMALIZER_SYSTEM,
            user_message=f"Extract from:\n\n{prop_text[:1000]}",
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        import json
        try:
            data = json.loads(response)
            
            print(f"   🏷️  Type: {data.get('listing_type', 'N/A')} | {data.get('property_type', 'N/A')}")
            print(f"   📍 City: {data.get('city', 'N/A')}")
            if data.get('locality'):
                print(f"   📍 Locality: {data.get('locality')}")
            if data.get('price'):
                print(f"   💰 Price: ₹{data.get('price'):,}/month")
            if data.get('nearest_metro'):
                dist = data.get('metro_distance', '?')
                print(f"   🚇 Metro: {data.get('nearest_metro')} ({dist} km)")
            if data.get('contact'):
                print(f"   📞 Contact: {data.get('contact')}")
                
        except json.JSONDecodeError as e:
            print(f"   ⚠️  Parse error: {e}")


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
    
    simple_prompt = """Convert property search query to JSON filters."""
    
    for query in test_queries:
        print(f"\n📝 Query: \"{query}\"")
        
        response = await llm_client.complete(
            system_prompt=simple_prompt,
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
            print(f"   Raw: {response[:100]}")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("🧪 Property Bot - MOCK LLM Test")
    print("=" * 50)
    print("Using: Pattern-based Mock LLM (NO API NEEDED!)")
    print("=" * 50)
    
    # Test connection
    await test_llm_connection()
    
    # Test PDF + normalization
    await test_pdf_with_mock_llm()
    
    # Test query planning
    await test_query_planning()
    
    print("\n" + "=" * 50)
    print("✅ All tests complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
