"""
Lightweight SQLite database for the standalone Telegram bot.
Stores users and properties without needing PostgreSQL/Docker.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Database file lives next to the bot
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot_properties.db")


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_verified INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                listing_type TEXT NOT NULL CHECK(listing_type IN ('rent', 'sell')),
                property_type TEXT NOT NULL CHECK(property_type IN (
                    'apartment', 'house', 'villa', 'plot', 'commercial', 'pg', 'other'
                )),
                title TEXT,
                description TEXT,
                price REAL NOT NULL,
                city TEXT NOT NULL,
                locality TEXT,
                pincode TEXT,
                bedrooms INTEGER,
                bathrooms INTEGER,
                carpet_area REAL,
                furnishing TEXT CHECK(furnishing IN (
                    'unfurnished', 'semi-furnished', 'fully-furnished'
                )),
                floor_number INTEGER,
                total_floors INTEGER,
                status TEXT DEFAULT 'available' CHECK(status IN (
                    'available', 'sold', 'rented', 'inactive'
                )),
                source TEXT DEFAULT 'chat',
                features_json TEXT DEFAULT '{}',
                transport_json TEXT DEFAULT '[]',
                raw_input_text TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_properties_user_id ON properties(user_id);
            CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city);
            CREATE INDEX IF NOT EXISTS idx_properties_listing ON properties(listing_type);
            CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price);
            CREATE INDEX IF NOT EXISTS idx_properties_bedrooms ON properties(bedrooms);
            CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
        """)
        conn.commit()

        # Add new columns if they don't exist (safe migration)
        try:
            conn.execute("ALTER TABLE properties ADD COLUMN contact_phone TEXT")
            conn.commit()
            logger.info("  Added contact_phone column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE properties ADD COLUMN google_maps_url TEXT")
            conn.commit()
            logger.info("  Added google_maps_url column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        logger.info(f"✅ Database initialized at {DB_PATH}")
    finally:
        conn.close()


# ─── USER OPERATIONS ─────────────────────────────────────────────────────────

def is_new_user(telegram_id: int) -> bool:
    """Check if a Telegram user is new (not in DB)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row is None
    finally:
        conn.close()


def get_or_create_user(
    telegram_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
) -> Dict[str, Any]:
    """Get existing user or create new one. Returns user dict."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()

        if row:
            return dict(row)

        conn.execute(
            """INSERT INTO users (telegram_id, username, first_name, last_name)
               VALUES (?, ?, ?, ?)""",
            (telegram_id, username, first_name, last_name),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def mark_user_verified(telegram_id: int):
    """Mark a user as verified (completed onboarding)."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET is_verified = 1, updated_at = datetime('now') WHERE telegram_id = ?",
            (telegram_id,),
        )
        conn.commit()
    finally:
        conn.close()


def is_user_verified(telegram_id: int) -> bool:
    """Check if user has completed onboarding."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT is_verified FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return bool(row and row["is_verified"])
    finally:
        conn.close()


# ─── PROPERTY OPERATIONS ─────────────────────────────────────────────────────

def save_property(user_telegram_id: int, prop: Dict[str, Any], source: str = "chat") -> int:
    """
    Save a normalized property to the database.
    Returns the property ID.
    """
    conn = get_connection()
    try:
        # Get user ID
        user = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (user_telegram_id,)
        ).fetchone()
        if not user:
            raise ValueError(f"User with telegram_id {user_telegram_id} not found")

        user_id = user["id"]

        # Extract features and transport as JSON
        features = prop.get("features", {})
        transport = prop.get("transport", [])
        if isinstance(features, dict):
            features_json = json.dumps(features)
        else:
            features_json = "{}"
        if isinstance(transport, list):
            transport_json = json.dumps(transport)
        else:
            transport_json = "[]"

        cursor = conn.execute(
            """INSERT INTO properties (
                user_id, listing_type, property_type, title, description,
                price, city, locality, pincode, bedrooms, bathrooms,
                carpet_area, furnishing, floor_number, total_floors,
                status, source, features_json, transport_json, raw_input_text,
                contact_phone, google_maps_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                prop.get("listing_type", "rent"),
                prop.get("property_type", "other"),
                prop.get("title", "Untitled Property"),
                prop.get("description", ""),
                float(prop.get("price", 0)),
                prop.get("city", "Unknown"),
                prop.get("locality", ""),
                prop.get("pincode", ""),
                prop.get("bedrooms"),
                prop.get("bathrooms"),
                float(prop["carpet_area"]) if prop.get("carpet_area") else None,
                prop.get("furnishing"),
                prop.get("floor_number"),
                prop.get("total_floors"),
                "available",
                source,
                features_json,
                transport_json,
                prop.get("raw_input_text", ""),
                prop.get("contact_phone", ""),
                prop.get("google_maps_url", ""),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def find_duplicates(prop: Dict[str, Any], user_telegram_id: int = None) -> List[Dict]:
    """
    Check if a similar property already exists in the database.
    Matches on: city + locality + price (±10%) + bedrooms + property_type.
    """
    conn = get_connection()
    try:
        price = float(prop.get("price", 0))
        price_low = price * 0.9
        price_high = price * 1.1

        query = """
            SELECT p.*, u.telegram_id
            FROM properties p
            JOIN users u ON p.user_id = u.id
            WHERE p.status = 'available'
              AND LOWER(p.city) = LOWER(?)
              AND LOWER(p.property_type) = LOWER(?)
              AND p.price BETWEEN ? AND ?
        """
        params = [
            prop.get("city", ""),
            prop.get("property_type", ""),
            price_low,
            price_high,
        ]

        # Optional exact matches
        if prop.get("bedrooms") is not None:
            query += " AND p.bedrooms = ?"
            params.append(prop["bedrooms"])

        if prop.get("locality"):
            query += " AND LOWER(p.locality) LIKE ?"
            params.append(f"%{prop['locality'].lower()}%")

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_properties(telegram_id: int) -> List[Dict]:
    """Get all properties for a user."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT p.* FROM properties p
               JOIN users u ON p.user_id = u.id
               WHERE u.telegram_id = ?
               ORDER BY p.created_at DESC""",
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_properties(filters: Dict[str, Any]) -> List[Dict]:
    """
    Search properties using a dict of filters from the LLM query plan.
    Returns matching properties.
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM properties WHERE status = 'available'"
        params = []

        intent = filters.get("intent")
        if intent == "rent":
            query += " AND listing_type = 'rent'"
        elif intent == "buy":
            query += " AND listing_type = 'sell'"

        for f in filters.get("filters", []):
            field = f.get("field", "").lower()
            op = f.get("operator", "=")
            value = f.get("value")

            if not field or value is None:
                continue
            if field == "listing_type":
                continue  # handled by intent

            # Map allowed fields to columns
            allowed = {
                "city", "locality", "property_type", "price", "bedrooms",
                "bathrooms", "carpet_area", "furnishing", "floor_number",
                "pets_allowed",
            }
            if field not in allowed:
                continue

            # Map operators
            op_sql = {"=": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}

            if op == "like":
                query += f" AND LOWER({field}) LIKE ?"
                params.append(f"%{str(value).lower()}%")
            elif op in op_sql:
                query += f" AND {field} {op_sql[op]} ?"
                params.append(value)

        # Sorting
        sort_by = filters.get("sort_by", "price")
        if sort_by not in {"price", "bedrooms", "carpet_area", "created_at"}:
            sort_by = "price"
        sort_order = "DESC" if filters.get("sort_order", "asc").lower() == "desc" else "ASC"
        query += f" ORDER BY {sort_by} {sort_order}"

        # Limit
        limit = min(int(filters.get("limit", 20)), 50)
        query += f" LIMIT {limit}"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_property_count() -> int:
    """Get total number of properties in DB."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM properties").fetchone()
        return row["cnt"]
    finally:
        conn.close()
