"""
Test script to verify PDF processing and property normalization.
Run this to test the Chennai_Properties.pdf file.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.file_processor import file_processor, FileProcessingError


def test_pdf_extraction():
    """Test PDF text extraction."""
    pdf_path = "Chennai_Properties.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return None
    
    print(f"📄 Reading PDF: {pdf_path}")
    print("-" * 50)
    
    # Read file
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()
    
    print(f"📏 File size: {len(file_bytes) / 1024:.1f} KB")
    
    # Validate file
    is_valid, message = file_processor.validate_file(file_bytes, pdf_path)
    print(f"✅ Validation: {message}" if is_valid else f"❌ Validation: {message}")
    
    if not is_valid:
        return None
    
    # Extract text
    try:
        extracted_text = file_processor.extract_from_pdf(file_bytes)
        print(f"\n📝 Extracted text length: {len(extracted_text)} characters")
        print("\n" + "=" * 50)
        print("EXTRACTED TEXT (first 2000 chars):")
        print("=" * 50)
        print(extracted_text[:2000])
        print("\n..." if len(extracted_text) > 2000 else "")
        print("=" * 50)
        
        # Try to parse multiple properties
        properties = file_processor.parse_multiple_properties(extracted_text)
        print(f"\n🏠 Detected {len(properties)} potential properties")
        
        return extracted_text
        
    except FileProcessingError as e:
        print(f"❌ Extraction failed: {e}")
        return None


async def test_normalization(extracted_text: str):
    """Test property normalization with the extracted text."""
    # Check if OpenAI key is available
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n⚠️ OPENAI_API_KEY not set - skipping normalization test")
        print("Set OPENAI_API_KEY environment variable to test AI normalization")
        return
    
    print("\n" + "=" * 50)
    print("TESTING AI NORMALIZATION")
    print("=" * 50)
    
    from app.agents.normalizer_agent import normalizer_agent
    
    # Take first 3000 chars for test
    test_text = extracted_text[:3000]
    
    print("🤖 Calling Property Normalizer Agent...")
    
    try:
        result = await normalizer_agent.normalize(test_text, source="pdf")
        
        print("\n✅ Normalization successful!")
        print(f"\n📊 Extracted Data:")
        print(f"   Listing Type: {result.listing_type}")
        print(f"   Property Type: {result.property_type}")
        print(f"   City: {result.city}")
        print(f"   Locality: {result.locality}")
        print(f"   Price: ₹{result.price:,.0f}")
        print(f"   Bedrooms: {result.bedrooms}")
        print(f"   Bathrooms: {result.bathrooms}")
        print(f"   Carpet Area: {result.carpet_area} sq ft")
        print(f"   Furnishing: {result.furnishing}")
        print(f"   Confidence: {result.confidence_score * 100:.0f}%")
        
        if result.missing_fields:
            print(f"\n⚠️ Missing fields: {', '.join(result.missing_fields)}")
        
        if result.features:
            print(f"\n🏋️ Features detected:")
            feature_dict = result.features.model_dump()
            for key, val in feature_dict.items():
                if val and key.startswith("has_"):
                    print(f"   ✓ {key.replace('has_', '').replace('_', ' ').title()}")
        
        if result.transport:
            print(f"\n🚇 Transport nearby:")
            for t in result.transport:
                print(f"   • {t.name} ({t.transport_type}) - {t.distance_km} km")
                
    except Exception as e:
        print(f"❌ Normalization failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("🧪 Property Bot - PDF Processing Test")
    print("=" * 50 + "\n")
    
    # Test extraction
    extracted_text = test_pdf_extraction()
    
    if extracted_text:
        # Test normalization
        asyncio.run(test_normalization(extracted_text))
    
    print("\n" + "=" * 50)
    print("🏁 Test complete!")


if __name__ == "__main__":
    main()
