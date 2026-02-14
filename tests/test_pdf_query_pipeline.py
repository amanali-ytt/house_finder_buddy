"""
Full Pipeline Test: PDF → LLM Normalization → Query with LLM → Results

This test:
1. Extracts properties from Chennai_Properties.pdf using the file processor
2. Normalizes each property using the NVIDIA LLM
3. Runs natural language queries against the normalized data
4. Reports what works and what doesn't
"""

import asyncio
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.file_processor import file_processor
from app.agents.llm_client import llm_client
from app.agents.prompts import PROPERTY_NORMALIZER_SYSTEM, QUERY_PLANNER_SYSTEM


# ─── STEP 1: Extract properties from PDF ────────────────────────────────────

def extract_pdf_properties():
    """Extract property texts from the PDF."""
    pdf_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Chennai_Properties.pdf"
    )

    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found at: {pdf_path}")
        sys.exit(1)

    print("📄 Extracting properties from Chennai_Properties.pdf...")
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    extracted_text = file_processor.extract_from_pdf(file_bytes)
    print(f"   Extracted {len(extracted_text)} characters")

    properties = file_processor.parse_multiple_properties(extracted_text)
    print(f"   Found {len(properties)} property chunks")

    # Show a snippet of first property
    if properties:
        print(f"\n   📝 First property snippet:")
        snippet = properties[0][:300].replace('\n', '\n      ')
        print(f"      {snippet}...")

    return properties


# ─── STEP 2: Normalize properties via LLM ──────────────────────────────────

async def normalize_property(raw_text: str, index: int) -> dict:
    """Normalize a single property text via LLM."""
    response = await llm_client.complete(
        system_prompt=PROPERTY_NORMALIZER_SYSTEM,
        user_message=f"Extract and normalize this property listing:\n\n{raw_text[:2000]}",
        temperature=0.2,
        max_tokens=1024,
        response_format={"type": "json_object"}
    )

    text = response.strip()

    # Handle markdown-wrapped JSON
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            json_lines.append(line)
        text = "\n".join(json_lines)

    # Try to find JSON in response
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            data = json.loads(json_match.group())
        else:
            print(f"   ⚠️  Property #{index}: Could not parse LLM response")
            return None

    return data


async def normalize_all_properties(raw_properties: list) -> list:
    """Normalize all extracted properties via LLM."""
    print(f"\n🤖 Normalizing {len(raw_properties)} properties via NVIDIA LLM...")
    print("   (This may take a minute...)\n")

    normalized = []
    # Process all properties from the PDF
    for i, raw_text in enumerate(raw_properties, 1):
        print(f"   Normalizing property #{i}...", end=" ", flush=True)
        try:
            data = await normalize_property(raw_text, i)
            if data:
                # Ensure required fields have defaults
                data.setdefault("listing_type", "rent")
                data.setdefault("property_type", "apartment")
                data.setdefault("city", "Chennai")
                data.setdefault("price", 0)
                data.setdefault("bedrooms", None)
                data.setdefault("furnishing", "unfurnished")
                data.setdefault("status", "available")
                normalized.append(data)
                price = data.get("price", 0)
                city = data.get("city", "?")
                beds = data.get("bedrooms", "?")
                ptype = data.get("property_type", "?")
                print(f"✅ {ptype} | {beds}BHK | ₹{price:,} | {city}")
            else:
                print("⚠️ Failed")
        except Exception as e:
            print(f"❌ Error: {e}")

    return normalized


# ─── STEP 3: Query against normalized data ──────────────────────────────────

def apply_filters_to_properties(properties: list, query_plan: dict) -> list:
    """Apply LLM-generated filters to normalized property data."""
    results = list(properties)

    # Apply intent
    intent = query_plan.get("intent", "search")
    if intent == "rent":
        results = [p for p in results if p.get("listing_type", "").lower() == "rent"]
    elif intent == "buy":
        results = [p for p in results if p.get("listing_type", "").lower() == "sell"]

    # Apply each filter
    for f in query_plan.get("filters", []):
        field = f.get("field", "").lower()
        op = f.get("operator", "=")
        value = f.get("value")

        if value is None:
            continue

        # Skip listing_type (handled by intent)
        if field == "listing_type":
            continue

        filtered = []
        for p in results:
            # Check main fields and nested features
            pval = p.get(field)
            if pval is None and isinstance(p.get("features"), dict):
                pval = p["features"].get(field)
            if pval is None and isinstance(p.get("transport"), list):
                # Check transport entries for station names etc
                pass

            if pval is None:
                # If filter requires True and field is missing, skip
                if op == "=" and value is True:
                    continue
                elif op in ("<=", "<", ">=", ">"):
                    continue
                else:
                    continue

            try:
                if op in ("=", "=="):
                    if isinstance(pval, str) and isinstance(value, str):
                        if pval.lower() == value.lower():
                            filtered.append(p)
                    elif isinstance(pval, bool):
                        if pval == bool(value):
                            filtered.append(p)
                    elif float(pval) == float(value):
                        filtered.append(p)
                elif op in ("!=", "<>"):
                    if str(pval).lower() != str(value).lower():
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
                elif op == "in":
                    if isinstance(value, list):
                        if str(pval).lower() in [str(v).lower() for v in value]:
                            filtered.append(p)
                    else:
                        if str(pval).lower() == str(value).lower():
                            filtered.append(p)
                else:
                    filtered.append(p)
            except (ValueError, TypeError):
                continue

        results = filtered

    # Sort
    sort_by = query_plan.get("sort_by", "price")
    sort_order = query_plan.get("sort_order", "asc")
    try:
        results.sort(
            key=lambda p: float(p.get(sort_by, 0) or 0),
            reverse=(sort_order == "desc")
        )
    except (ValueError, TypeError):
        pass

    return results


async def run_query_test(user_query: str, properties: list, test_num: int) -> dict:
    """Run a single query test and report results."""
    print(f"\n{'─'*60}")
    print(f"🔍 TEST {test_num}: \"{user_query}\"")
    print(f"{'─'*60}")

    # Get LLM query plan
    response = await llm_client.complete(
        system_prompt=QUERY_PLANNER_SYSTEM,
        user_message=f"User Query: {user_query}\n\nConvert to structured filters. Return JSON.",
        temperature=0.2,
        max_tokens=512,
        response_format={"type": "json_object"}
    )

    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            json_lines.append(line)
        text = "\n".join(json_lines)

    try:
        query_plan = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            query_plan = json.loads(json_match.group())
        else:
            print(f"   ❌ FAIL: Could not parse LLM query plan")
            print(f"   Raw: {response[:200]}")
            return {"query": user_query, "status": "PARSE_FAIL"}

    # Show query plan
    print(f"\n   📋 LLM Query Plan:")
    print(f"      Intent: {query_plan.get('intent', 'N/A')}")
    for f in query_plan.get("filters", []):
        print(f"      • {f.get('field')} {f.get('operator')} {f.get('value')}")
    print(f"      Sort: {query_plan.get('sort_by', 'price')} ({query_plan.get('sort_order', 'asc')})")

    # Apply filters
    results = apply_filters_to_properties(properties, query_plan)

    print(f"\n   📊 Results: {len(results)}/{len(properties)} properties matched")

    if results:
        for i, p in enumerate(results[:3], 1):
            title = p.get("title", "Untitled")
            price = p.get("price", 0)
            city = p.get("city", "?")
            locality = p.get("locality", "?")
            beds = p.get("bedrooms", "?")
            ptype = p.get("property_type", "?")
            lt = p.get("listing_type", "?")
            furnish = p.get("furnishing", "?")

            price_label = "month" if lt == "rent" else "total"
            print(f"\n      🏠 #{i}: {title}")
            print(f"         💰 ₹{price:,}/{price_label} | 📍 {locality}, {city}")
            print(f"         🛏️ {beds}BHK {ptype} | 🪑 {furnish}")

            # Show features if present
            features = p.get("features", {})
            if isinstance(features, dict):
                flags = [k for k, v in features.items() if v is True and k.startswith("has_")]
                if flags:
                    print(f"         ✨ {', '.join(f.replace('has_', '') for f in flags)}")

        if len(results) > 3:
            print(f"\n      ... and {len(results) - 3} more")
    else:
        print(f"      ⚠️ No properties matched!")

    # Evaluate
    status = "PASS" if len(results) > 0 else "NO_RESULTS"
    print(f"\n   {'✅' if status == 'PASS' else '⚠️'} Status: {status}")

    return {
        "query": user_query,
        "status": status,
        "plan": query_plan,
        "result_count": len(results),
    }


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("🧪 FULL PIPELINE TEST")
    print("   PDF → LLM Normalize → LLM Query → Results")
    print("=" * 60)
    print(f"LLM: NVIDIA API ({llm_client.model})")
    print("=" * 60)

    # Step 1: Extract from PDF
    raw_properties = extract_pdf_properties()
    if not raw_properties:
        print("❌ No properties extracted from PDF!")
        return

    # Step 2: Normalize with LLM
    normalized = await normalize_all_properties(raw_properties)
    if not normalized:
        print("❌ No properties normalized!")
        return

    # Show summary of normalized data
    print(f"\n{'='*60}")
    print(f"📊 NORMALIZED DATABASE: {len(normalized)} properties")
    print(f"{'='*60}")
    for i, p in enumerate(normalized, 1):
        price = p.get("price", 0)
        lt = p.get("listing_type", "?")
        pt = p.get("property_type", "?")
        city = p.get("city", "?")
        locality = p.get("locality", "?")
        beds = p.get("bedrooms", "?")
        print(f"   {i}. [{lt}] {beds}BHK {pt} in {locality}, {city} — ₹{price:,}")

    # Step 3: Run various queries
    print(f"\n{'='*60}")
    print("🔍 RUNNING QUERY TESTS...")
    print(f"{'='*60}")

    # Build test queries based on what's actually in our data
    test_queries = [
        "Show me all rental properties in Chennai",
        "PG accommodation in Chennai under 15000",
        "Cheapest property available in Chennai",
        "Properties for rent in Vepery Chennai",
        "House for rent in Koyambedu Chennai",
    ]

    results_summary = []
    for i, query in enumerate(test_queries, 1):
        result = await run_query_test(query, normalized, i)
        results_summary.append(result)

    # ─── FINAL REPORT ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("📋 FINAL REPORT")
    print(f"{'='*60}")

    passed = sum(1 for r in results_summary if r["status"] == "PASS")
    failed = sum(1 for r in results_summary if r["status"] != "PASS")

    print(f"\n   ✅ Passed: {passed}/{len(results_summary)}")
    print(f"   ❌ Failed: {failed}/{len(results_summary)}")

    if failed:
        print(f"\n   ⚠️ ISSUES FOUND:")
        for r in results_summary:
            if r["status"] != "PASS":
                print(f"      • \"{r['query']}\" → {r['status']}")
                if "plan" in r:
                    filters = r["plan"].get("filters", [])
                    for f in filters:
                        print(f"        Filter: {f.get('field')} {f.get('operator')} {f.get('value')}")

    print(f"\n{'='*60}")
    print("✅ Pipeline test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
