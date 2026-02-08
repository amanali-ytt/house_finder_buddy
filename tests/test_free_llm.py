"""
Test script for Hugging Face free LLM integration.
Tests PDF extraction AND AI normalization - NO API KEY NEEDED!

Usage:
  python tests/test_free_llm.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.file_processor import file_processor
from app.agents.llm_client import llm_client


async def test_llm_connection():
    """Test if Hugging Face API is working."""
    print("🤗 Testing Hugging Face Connection...")
    print("-" * 50)
    
    info = llm_client.get_provider_info()
    print(f"Provider: {info['provider'].upper()}")
    print(f"Model: {info['model']}")
    print(f"Free: {info['free']}")
    
    print("\n📡 Sending test request (may take 10-30s on first call)...")
    
    try:
        response = await llm_client.complete(
            system_prompt="You are a helpful assistant. Be concise.",
            user_message="Say hello in exactly 5 words.",
            temperature=0.5,
            max_tokens=50
        )
        print(f"✅ Response: {response.strip()}")
        return True
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_pdf_with_llm():
    """Test PDF extraction with AI normalization."""
    pdf_path = "Chennai_Properties.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    print("\n" + "=" * 50)
    print("📄 TESTING PDF + AI NORMALIZATION")
    print("=" * 50)
    
    # Extract PDF
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()
    
    extracted_text = file_processor.extract_from_pdf(file_bytes)
    print(f"📝 Extracted {len(extracted_text)} characters from PDF")
    
    # Take first property for testing
    properties = file_processor.parse_multiple_properties(extracted_text)
    print(f"🏠 Found {len(properties)} properties")
    
    if not properties:
        return
    
    # Test normalization on first property (limit text size for free tier)
    first_property = properties[0][:1500]
    
    print("\n🤖 Normalizing first property with Hugging Face...")
    print("   (This may take 15-30 seconds on free tier)")
    
    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM
    
    # Simplified prompt for smaller models
    simple_prompt = """Extract property details and return JSON with these fields:
- listing_type: "rent" or "sell"
- property_type: apartment/house/villa/pg/other
- city: city name
- locality: area name  
- price: number (monthly rent or sale price)
- bedrooms: number
- nearest_metro: name and distance
- confidence_score: 0 to 1"""
    
    try:
        response = await llm_client.complete(
            system_prompt=simple_prompt,
            user_message=f"Extract from:\n\n{first_property}",
            temperature=0.3,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        print("\n✅ AI Normalization Result:")
        print("-" * 50)
        
        import json
        try:
            data = json.loads(response)
            
            print(f"🏷️  Listing Type: {data.get('listing_type', 'N/A')}")
            print(f"🏠 Property Type: {data.get('property_type', 'N/A')}")
            print(f"📍 City: {data.get('city', 'N/A')}")
            print(f"📍 Locality: {data.get('locality', 'N/A')}")
            price = data.get('price', 0)
            if isinstance(price, (int, float)):
                print(f"💰 Price: ₹{price:,}")
            else:
                print(f"💰 Price: {price}")
            print(f"🛏️  Bedrooms: {data.get('bedrooms', 'N/A')}")
            print(f"🚇 Metro: {data.get('nearest_metro', 'N/A')}")
            print(f"📊 Confidence: {float(data.get('confidence_score', 0)) * 100:.0f}%")
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse as JSON: {e}")
            print("Raw response:")
            print(response[:500])
            
    except Exception as e:
        print(f"❌ Normalization failed: {e}")
        import traceback
        traceback.print_exc()


async def test_query_planning():
    """Test natural language query planning."""
    print("\n" + "=" * 50)
    print("🔍 TESTING QUERY PLANNING")
    print("=" * 50)
    
    test_query = "2BHK flat for rent in Chennai under 25000"
    
    print(f"Query: \"{test_query}\"")
    print("\n🤖 Converting to structured filters...")
    
    simple_prompt = """Convert property search query to JSON filters:
Return JSON with:
- intent: "buy" or "rent"
- filters: array of {field, operator, value}
  - field: city, bedrooms, price, property_type
  - operator: =, >, <, >=, <=
- sort_by: field name
- sort_order: asc or desc"""
    
    try:
        response = await llm_client.complete(
            system_prompt=simple_prompt,
            user_message=f"Query: {test_query}",
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        import json
        data = json.loads(response)
        
        print("\n✅ Query Plan:")
        print(f"   Intent: {data.get('intent', 'N/A')}")
        print(f"   Filters:")
        for f in data.get('filters', []):
            print(f"     • {f.get('field')} {f.get('operator')} {f.get('value')}")
        print(f"   Sort: {data.get('sort_by', 'N/A')} {data.get('sort_order', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Query planning failed: {e}")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("🧪 Property Bot - Hugging Face FREE LLM Test")
    print("=" * 50)
    print("Using: Hugging Face InferenceClient (FREE)")
    print("Model: Qwen/Qwen2.5-Coder-32B-Instruct")
    print("=" * 50)
    
    # Test connection
    connected = await test_llm_connection()
    
    if connected:
        # Test PDF + normalization
        await test_pdf_with_llm()
        
        # Test query planning
        await test_query_planning()
    
    print("\n" + "=" * 50)
    print("🏁 Tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
