-- =============================================================================
-- AI Property Management Bot - PostgreSQL Schema
-- Supports: Rent & Sell categories, multi-property per user, natural language queries
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

CREATE TYPE listing_type AS ENUM ('rent', 'sell');
CREATE TYPE property_type AS ENUM ('apartment', 'house', 'villa', 'plot', 'commercial', 'pg', 'other');
CREATE TYPE furnishing_status AS ENUM ('unfurnished', 'semi-furnished', 'fully-furnished');
CREATE TYPE property_status AS ENUM ('available', 'sold', 'rented', 'inactive');

-- =============================================================================
-- USERS TABLE
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(20),
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(50) DEFAULT 'user',  -- 'user', 'agent', 'admin'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_role ON users(role);

-- =============================================================================
-- PROPERTIES TABLE
-- =============================================================================

CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Listing Details
    listing_type listing_type NOT NULL,  -- 'rent' or 'sell'
    property_type property_type NOT NULL,
    title VARCHAR(500),
    description TEXT,
    
    -- Pricing
    price DECIMAL(15, 2) NOT NULL,  -- Rent per month OR Sell price
    price_negotiable BOOLEAN DEFAULT TRUE,
    security_deposit DECIMAL(15, 2),  -- For rent
    maintenance_monthly DECIMAL(10, 2),
    
    -- Location
    address TEXT,
    city VARCHAR(100) NOT NULL,
    locality VARCHAR(200),
    pincode VARCHAR(10),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Property Specs
    bedrooms INTEGER,
    bathrooms INTEGER,
    balconies INTEGER DEFAULT 0,
    carpet_area DECIMAL(10, 2),  -- In sq ft
    built_up_area DECIMAL(10, 2),
    super_built_up_area DECIMAL(10, 2),
    floor_number INTEGER,
    total_floors INTEGER,
    facing VARCHAR(20),  -- 'north', 'south', 'east', 'west', etc.
    age_of_property INTEGER,  -- In years
    
    -- Availability
    furnishing furnishing_status DEFAULT 'unfurnished',
    available_from DATE,
    status property_status DEFAULT 'available',
    
    -- Preferences (for rent)
    preferred_tenant VARCHAR(100),  -- 'family', 'bachelor', 'any'
    pets_allowed BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    source VARCHAR(50) DEFAULT 'chat',  -- 'chat', 'pdf', 'excel'
    raw_input_text TEXT,  -- Original user input for reference
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_properties_user_id ON properties(user_id);
CREATE INDEX idx_properties_listing_type ON properties(listing_type);
CREATE INDEX idx_properties_property_type ON properties(property_type);
CREATE INDEX idx_properties_city ON properties(city);
CREATE INDEX idx_properties_locality ON properties(locality);
CREATE INDEX idx_properties_price ON properties(price);
CREATE INDEX idx_properties_bedrooms ON properties(bedrooms);
CREATE INDEX idx_properties_status ON properties(status);
CREATE INDEX idx_properties_created_at ON properties(created_at DESC);

-- Composite indexes for common filter combinations
CREATE INDEX idx_properties_city_listing ON properties(city, listing_type);
CREATE INDEX idx_properties_city_type_bed ON properties(city, property_type, bedrooms);
CREATE INDEX idx_properties_price_range ON properties(listing_type, price, city);

-- Full-text search on title and description
CREATE INDEX idx_properties_text_search ON properties USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));

-- =============================================================================
-- PROPERTY FEATURES (Amenities)
-- =============================================================================

CREATE TABLE property_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    
    -- Common Amenities
    has_parking BOOLEAN DEFAULT FALSE,
    parking_type VARCHAR(50),  -- 'covered', 'open', 'both'
    parking_count INTEGER DEFAULT 0,
    
    has_lift BOOLEAN DEFAULT FALSE,
    has_power_backup BOOLEAN DEFAULT FALSE,
    has_water_supply_24x7 BOOLEAN DEFAULT FALSE,
    has_security BOOLEAN DEFAULT FALSE,
    has_cctv BOOLEAN DEFAULT FALSE,
    has_intercom BOOLEAN DEFAULT FALSE,
    
    -- Recreation
    has_gym BOOLEAN DEFAULT FALSE,
    has_swimming_pool BOOLEAN DEFAULT FALSE,
    has_club_house BOOLEAN DEFAULT FALSE,
    has_children_play_area BOOLEAN DEFAULT FALSE,
    has_garden BOOLEAN DEFAULT FALSE,
    has_sports_facility BOOLEAN DEFAULT FALSE,
    
    -- Convenience
    has_gas_pipeline BOOLEAN DEFAULT FALSE,
    has_ac BOOLEAN DEFAULT FALSE,
    has_wifi BOOLEAN DEFAULT FALSE,
    has_geyser BOOLEAN DEFAULT FALSE,
    has_washing_machine BOOLEAN DEFAULT FALSE,
    has_refrigerator BOOLEAN DEFAULT FALSE,
    has_tv BOOLEAN DEFAULT FALSE,
    has_modular_kitchen BOOLEAN DEFAULT FALSE,
    has_wardrobe BOOLEAN DEFAULT FALSE,
    
    -- Additional features as JSON for flexibility
    additional_features JSONB DEFAULT '[]',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_property_features_property_id ON property_features(property_id);

-- =============================================================================
-- PROPERTY TRANSPORT (Nearby Connectivity)
-- =============================================================================

CREATE TABLE property_transport (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    
    transport_type VARCHAR(50) NOT NULL,  -- 'metro', 'bus_stop', 'railway', 'airport', 'highway'
    name VARCHAR(200),  -- Station/Stop name
    distance_km DECIMAL(5, 2),
    distance_minutes INTEGER,  -- Walking time
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_property_transport_property_id ON property_transport(property_id);
CREATE INDEX idx_property_transport_type ON property_transport(transport_type);

-- =============================================================================
-- PROPERTY MEDIA
-- =============================================================================

CREATE TABLE property_media (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    
    media_type VARCHAR(20) NOT NULL,  -- 'image', 'video', 'document', 'floor_plan'
    file_url TEXT NOT NULL,
    file_name VARCHAR(255),
    file_size INTEGER,  -- In bytes
    mime_type VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_property_media_property_id ON property_media(property_id);
CREATE INDEX idx_property_media_type ON property_media(media_type);

-- =============================================================================
-- USER QUERIES LOG (For analytics and improving the bot)
-- =============================================================================

CREATE TABLE user_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    raw_query TEXT NOT NULL,
    parsed_filters JSONB,  -- The structured filters generated by Query Planner
    result_count INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_queries_user_id ON user_queries(user_id);
CREATE INDEX idx_user_queries_created_at ON user_queries(created_at DESC);

-- =============================================================================
-- CONVERSATION STATES (For multi-turn conversations)
-- =============================================================================

CREATE TABLE conversation_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    state_type VARCHAR(50) NOT NULL,  -- 'adding_property', 'searching', 'editing'
    current_step VARCHAR(100),
    collected_data JSONB DEFAULT '{}',
    expires_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_conversation_states_user_id ON conversation_states(user_id);
CREATE INDEX idx_conversation_states_expires ON conversation_states(expires_at);

-- =============================================================================
-- FUNCTIONS & TRIGGERS
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversation_states_updated_at
    BEFORE UPDATE ON conversation_states
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SAMPLE DATA FOR TESTING (Optional - Remove in production)
-- =============================================================================

-- Uncomment below to insert sample data
/*
INSERT INTO users (telegram_id, username, first_name, role) VALUES
(123456789, 'testuser', 'Test', 'user');

INSERT INTO properties (user_id, listing_type, property_type, title, price, city, locality, bedrooms, bathrooms)
SELECT id, 'rent', 'apartment', '2BHK near Metro Station', 25000, 'Mumbai', 'Andheri West', 2, 2
FROM users WHERE telegram_id = 123456789;
*/
