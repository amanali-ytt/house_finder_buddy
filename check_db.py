import sqlite3

conn = sqlite3.connect('bot_properties.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 70)
print("  📊 PROPERTY BOT DATABASE STATUS")
print("=" * 70)

# Users
cur.execute("SELECT * FROM users")
users = cur.fetchall()
print(f"\n👥 USERS ({len(users)}):")
print("-" * 50)
for u in users:
    verified = "✅ Verified" if u["is_verified"] else "❌ Not Verified"
    name = u["first_name"] or "Unknown"
    username = f"@{u['username']}" if u["username"] and u["username"] != "None" else ""
    print(f"  {name} {username} | Telegram ID: {u['telegram_id']} | {verified}")

# Properties
cur.execute("SELECT * FROM properties ORDER BY created_at DESC")
properties = cur.fetchall()
print(f"\n🏠 PROPERTIES ({len(properties)}):")
print("-" * 70)

if not properties:
    print("  (No properties yet — users need to upload a document and tap Save)")
else:
    for i, p in enumerate(properties, 1):
        price = float(p["price"])
        if p["listing_type"] == "rent":
            price_str = f"₹{price:,.0f}/month"
        elif price >= 10000000:
            price_str = f"₹{price/10000000:.1f} Cr"
        elif price >= 100000:
            price_str = f"₹{price/100000:.0f} L"
        else:
            price_str = f"₹{price:,.0f}"

        beds = f"{p['bedrooms']}BHK" if p["bedrooms"] else "N/A"
        furn = p["furnishing"] or "N/A"
        loc = f"{p['locality']}, " if p["locality"] else ""

        print(f"\n  [{i}] {p['title'] or 'Untitled'}")
        print(f"      Type:     {p['listing_type'].upper()} | {p['property_type'].title()}")
        print(f"      Price:    {price_str}")
        print(f"      Location: {loc}{p['city']}")
        print(f"      Specs:    {beds} | {furn.replace('-',' ').title()}")
        phone = p["contact_phone"] if "contact_phone" in p.keys() and p["contact_phone"] else "N/A"
        maps_url = p["google_maps_url"] if "google_maps_url" in p.keys() and p["google_maps_url"] else "N/A"
        print(f"      Phone:    {phone}")
        print(f"      Maps:     {maps_url}")
        print(f"      Source:   {p['source']} | Status: {p['status']}")
        print(f"      Added:    {p['created_at']}")

print("\n" + "=" * 70)
conn.close()
