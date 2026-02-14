"""
End-to-End Test: Natural Language → LLM Query Plan → Database Results

This test:
1. Creates an in-memory SQLite database with sample Chennai properties
2. Sends a natural language query to the NVIDIA LLM (Llama 3.1)  
3. LLM converts it to structured filters (JSON)
4. Shows exactly what SQL query would be built and what results come back
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.llm_client import llm_client
from app.agents.prompts import QUERY_PLANNER_SYSTEM

# ─── Sample Property Database (simulating what's in PostgreSQL) ─────────────
SAMPLE_PROPERTIES = [
    {
        "id": 1,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "2BHK Apartment in OMR",
        "price": 18000,
        "city": "Chennai",
        "locality": "OMR",
        "bedrooms": 2,
        "bathrooms": 2,
        "furnishing": "semi-furnished",
        "carpet_area": 950,
        "has_parking": True,
        "has_gym": False,
        "near_metro": True,
        "nearest_metro": "Thoraipakkam",
        "metro_distance_km": 1.2,
        "status": "available",
    },
    {
        "id": 2,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "3BHK Luxury Flat in Adyar",
        "price": 35000,
        "city": "Chennai",
        "locality": "Adyar",
        "bedrooms": 3,
        "bathrooms": 2,
        "furnishing": "fully-furnished",
        "carpet_area": 1400,
        "has_parking": True,
        "has_gym": True,
        "near_metro": False,
        "nearest_metro": None,
        "metro_distance_km": None,
        "status": "available",
    },
    {
        "id": 3,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "2BHK Budget Flat in Tambaram",
        "price": 12000,
        "city": "Chennai",
        "locality": "Tambaram",
        "bedrooms": 2,
        "bathrooms": 1,
        "furnishing": "unfurnished",
        "carpet_area": 800,
        "has_parking": False,
        "has_gym": False,
        "near_metro": True,
        "nearest_metro": "Tambaram Metro",
        "metro_distance_km": 0.5,
        "status": "available",
    },
    {
        "id": 4,
        "listing_type": "rent",
        "property_type": "pg",
        "title": "PG for Men near OMR IT Park",
        "price": 8000,
        "city": "Chennai",
        "locality": "Sholinganallur",
        "bedrooms": 1,
        "bathrooms": 1,
        "furnishing": "fully-furnished",
        "carpet_area": 200,
        "has_parking": False,
        "has_gym": False,
        "near_metro": True,
        "nearest_metro": "Sholinganallur Metro",
        "metro_distance_km": 0.8,
        "status": "available",
    },
    {
        "id": 5,
        "listing_type": "sell",
        "property_type": "villa",
        "title": "Premium Villa in ECR",
        "price": 25000000,
        "city": "Chennai",
        "locality": "ECR",
        "bedrooms": 4,
        "bathrooms": 4,
        "furnishing": "fully-furnished",
        "carpet_area": 3200,
        "has_parking": True,
        "has_gym": True,
        "near_metro": False,
        "nearest_metro": None,
        "metro_distance_km": None,
        "status": "available",
    },
    {
        "id": 6,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "1BHK Studio in T.Nagar",
        "price": 15000,
        "city": "Chennai",
        "locality": "T.Nagar",
        "bedrooms": 1,
        "bathrooms": 1,
        "furnishing": "semi-furnished",
        "carpet_area": 550,
        "has_parking": False,
        "has_gym": False,
        "near_metro": True,
        "nearest_metro": "T.Nagar Metro",
        "metro_distance_km": 0.3,
        "status": "available",
    },
    {
        "id": 7,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "2BHK in Velachery with Gym",
        "price": 22000,
        "city": "Chennai",
        "locality": "Velachery",
        "bedrooms": 2,
        "bathrooms": 2,
        "furnishing": "semi-furnished",
        "carpet_area": 1050,
        "has_parking": True,
        "has_gym": True,
        "near_metro": True,
        "nearest_metro": "Velachery Metro",
        "metro_distance_km": 0.6,
        "status": "available",
    },
    {
        "id": 8,
        "listing_type": "sell",
        "property_type": "apartment",
        "title": "3BHK New Apartment in Anna Nagar",
        "price": 9500000,
        "city": "Chennai",
        "locality": "Anna Nagar",
        "bedrooms": 3,
        "bathrooms": 3,
        "furnishing": "unfurnished",
        "carpet_area": 1600,
        "has_parking": True,
        "has_gym": True,
        "near_metro": True,
        "nearest_metro": "Anna Nagar Metro",
        "metro_distance_km": 0.4,
        "status": "available",
    },
    {
        "id": 9,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "2BHK Fully Furnished in Guindy",
        "price": 24000,
        "city": "Chennai",
        "locality": "Guindy",
        "bedrooms": 2,
        "bathrooms": 2,
        "furnishing": "fully-furnished",
        "carpet_area": 1000,
        "has_parking": True,
        "has_gym": False,
        "near_metro": True,
        "nearest_metro": "Guindy Metro",
        "metro_distance_km": 0.7,
        "status": "available",
    },
    {
        "id": 10,
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "3BHK Spacious in Porur",
        "price": 20000,
        "city": "Chennai",
        "locality": "Porur",
        "bedrooms": 3,
        "bathrooms": 2,
        "furnishing": "semi-furnished",
        "carpet_area": 1350,
        "has_parking": True,
        "has_gym": False,
        "near_metro": False,
        "nearest_metro": None,
        "metro_distance_km": None,
        "status": "available",
    },
]


def apply_filters(properties: list, query_plan: dict) -> list:
    """Apply LLM-generated filters to our sample data (simulates SecureQueryBuilder)."""
    results = list(properties)

    # Apply intent
    intent = query_plan.get("intent", "search")
    if intent == "rent":
        results = [p for p in results if p["listing_type"] == "rent"]
    elif intent == "buy":
        results = [p for p in results if p["listing_type"] == "sell"]

    # Apply each filter
    for f in query_plan.get("filters", []):
        field = f.get("field", "").lower()
        op = f.get("operator", "=")
        value = f.get("value")

        if value is None:
            continue
        
        # Skip listing_type filter since already handled by intent
        if field == "listing_type":
            continue

        filtered = []
        for p in results:
            pval = p.get(field)
            if pval is None:
                continue

            try:
                if op in ("=", "=="):
                    if isinstance(pval, str):
                        if pval.lower() == str(value).lower():
                            filtered.append(p)
                    elif pval == value:
                        filtered.append(p)
                elif op in ("!=", "<>"):
                    if pval != value:
                        filtered.append(p)
                elif op == ">":
                    if float(pval) > float(value):
                        filtered.append(p)
                elif op == ">=":
                    if float(pval) >= float(value):
                        filtered.append(p)
                elif op == "<":
                    if float(pval) < float(value):
                        filtered.append(p)
                elif op == "<=":
                    if float(pval) <= float(value):
                        filtered.append(p)
                elif op == "like":
                    if str(value).lower() in str(pval).lower():
                        filtered.append(p)
                else:
                    filtered.append(p)
            except (ValueError, TypeError):
                continue

        results = filtered

    # Apply sorting
    sort_by = query_plan.get("sort_by", "price")
    sort_order = query_plan.get("sort_order", "asc")
    if sort_by and any(sort_by in p for p in results):
        results.sort(
            key=lambda p: p.get(sort_by, 0) or 0,
            reverse=(sort_order == "desc")
        )

    return results


async def run_query(user_query: str):
    """Run a single natural language query through the full pipeline."""
    print(f"\n{'='*60}")
    print(f"📝 USER QUERY: \"{user_query}\"")
    print(f"{'='*60}")

    # ─── STEP 1: LLM converts natural language → structured filters ───
    print("\n🤖 Step 1: Sending to NVIDIA LLM for query planning...")

    response = await llm_client.complete(
        system_prompt=QUERY_PLANNER_SYSTEM,
        user_message=f"User Query: {user_query}\n\nConvert this search query into structured filters. Return a valid JSON object with intent, filters, sort_by, sort_order, and limit.",
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    try:
        query_plan = json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            query_plan = json.loads(json_match.group())
        else:
            print(f"❌ LLM returned non-JSON: {response[:200]}")
            return

    print(f"\n📋 LLM Query Plan:")
    print(f"   Intent: {query_plan.get('intent', 'N/A')}")
    print(f"   Filters:")
    for f in query_plan.get("filters", []):
        print(f"      • {f.get('field')} {f.get('operator')} {f.get('value')}")
    print(f"   Sort: {query_plan.get('sort_by', 'price')} ({query_plan.get('sort_order', 'asc')})")

    # ─── STEP 2: Apply filters to database (simulated) ─────────────────
    print(f"\n🔍 Step 2: Executing query against database ({len(SAMPLE_PROPERTIES)} properties)...")

    results = apply_filters(SAMPLE_PROPERTIES, query_plan)

    # ─── STEP 3: Show results ──────────────────────────────────────────
    print(f"\n✅ RESULTS: {len(results)} properties found")
    print("-" * 60)

    if not results:
        print("   No matching properties found.")
    else:
        for i, p in enumerate(results, 1):
            print(f"\n   🏠 #{i}: {p['title']}")
            print(f"      💰 ₹{p['price']:,}/{'month' if p['listing_type'] == 'rent' else 'total'}")
            print(f"      📍 {p['locality']}, {p['city']}")
            print(f"      🛏️  {p['bedrooms']}BHK | 🛁 {p['bathrooms']} bath | 📐 {p['carpet_area']} sq ft")
            print(f"      🪑 {p['furnishing']}", end="")
            extras = []
            if p.get("has_parking"):
                extras.append("🅿️ Parking")
            if p.get("has_gym"):
                extras.append("💪 Gym")
            if p.get("near_metro"):
                extras.append(f"🚇 {p.get('nearest_metro', 'Metro')} ({p.get('metro_distance_km')} km)")
            if extras:
                print(f" | {' | '.join(extras)}")
            else:
                print()

    print(f"\n{'─'*60}")


async def main():
    print("=" * 60)
    print("🧪 END-TO-END TEST: LLM + Database Query Pipeline")
    print("=" * 60)
    print(f"LLM: NVIDIA API ({llm_client.model})")
    print(f"Database: {len(SAMPLE_PROPERTIES)} sample Chennai properties")
    print("=" * 60)

    # Test 3 different natural language queries
    test_queries = [
        "2BHK apartment for rent in Chennai under 20000",
        "3BHK flat in Chennai with gym and parking",
        "PG or 1BHK near metro in Chennai under 15000",
    ]

    for query in test_queries:
        await run_query(query)

    print(f"\n{'='*60}")
    print("✅ All queries complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
