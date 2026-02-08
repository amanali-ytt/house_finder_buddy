"""
Test script for free LLM integration.
Tests both PDF extraction AND AI normalization using Groq or Ollama.

Usage:
  # With Groq (set GROQ_API_KEY in environment)
  set GROQ_API_KEY=your_key_here
  python tests/test_free_llm.py
  
  # With Ollama (run Ollama first: ollama serve)
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
    """Test if LLM provider is working."""
    print("🔌 Testing LLM Connection...")
    print("-" * 50)
    
    info = llm_client.get_provider_info()
    print(f"Provider: {info['provider'].upper()}")
    print(f"Model: {info['model']}")
    print(f"Status: {info['status']}")
    
    if info['provider'] == 'ollama' and not os.getenv("GROQ_API_KEY"):
        print("\n⚠️  Using Ollama (local). Make sure Ollama is running!")
        print("   Start with: ollama serve")
        print("   Pull model: ollama pull llama3.1")
    
    # Simple test
    try:
        response = await llm_client.complete(
            system_prompt="You are a helpful assistant.",
            user_message="Say 'Hello, Property Bot!' in exactly 3 words.",
            temperature=0.1,
            max_tokens=50
        )
        print(f"\n✅ LLM Response: {response.strip()}")
        return True
    except Exception as e:
        print(f"\n❌ LLM Connection Failed: {e}")
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
    
    # Test normalization on first property
    first_property = properties[0][:2000]  # Limit size
    
    print("\n🤖 Normalizing first property with AI...")
    
    from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM
    
    try:
        response = await llm_client.complete(
            system_prompt=PROPERTY_NORMALIZER_SYSTEM,
            user_message=f"Extract property details from:\n\n{first_property}",
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        print("\n✅ AI Normalization Result:")
        print("-" * 50)
        
        # Try to parse JSON
        import json
        try:
            # Handle markdown code blocks
            clean_response = response.strip()
            if clean_response.startswith("```"):
                lines = clean_response.split("\n")
                clean_response = "\n".join(lines[1:-1])
            
            data = json.loads(clean_response)
            
            print(f"🏷️  Listing Type: {data.get('listing_type', 'N/A')}")
            print(f"🏠 Property Type: {data.get('property_type', 'N/A')}")
            print(f"📍 City: {data.get('city', 'N/A')}")
            print(f"📍 Locality: {data.get('locality', 'N/A')}")
            print(f"💰 Price: ₹{data.get('price', 0):,}")
            print(f"🛏️  Bedrooms: {data.get('bedrooms', 'N/A')}")
            print(f"📊 Confidence: {data.get('confidence_score', 0) * 100:.0f}%")
            
            if data.get('transport'):
                print(f"🚇 Transport: {data['transport']}")
                
        except json.JSONDecodeError:
            print("Raw response (not JSON):")
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
    
    from app.agents.prompts import QUERY_PLANNER_SYSTEM
    
    test_query = "2BHK flat for rent in Chennai under 30k near metro"
    
    print(f"Query: \"{test_query}\"")
    print("\n🤖 Converting to structured filters...")
    
    try:
        response = await llm_client.complete(
            system_prompt=QUERY_PLANNER_SYSTEM,
            user_message=f"User Query: {test_query}",
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        import json
        clean_response = response.strip()
        if clean_response.startswith("```"):
            lines = clean_response.split("\n")
            clean_response = "\n".join(lines[1:-1])
        
        data = json.loads(clean_response)
        
        print("\n✅ Query Plan:")
        print(f"   Intent: {data.get('intent', 'N/A')}")
        print(f"   Filters:")
        for f in data.get('filters', []):
            print(f"     - {f.get('field')} {f.get('operator')} {f.get('value')}")
        print(f"   Sort: {data.get('sort_by', 'N/A')} {data.get('sort_order', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Query planning failed: {e}")


async def main():
    """Run all tests."""
    print("🧪 Property Bot - Free LLM Testing")
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
