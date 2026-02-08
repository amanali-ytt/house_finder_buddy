# 🏠 AI Property Management Telegram Bot

An AI-powered Telegram bot for property management and discovery. Users can add properties via chat, PDF, or Excel and query them using natural language.

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │ ──▶ │   FastAPI API   │ ──▶ │   PostgreSQL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │
         │                      ▼
         │              ┌─────────────────┐
         │              │   AI Agents     │
         │              │                 │
         │              │ • Conversation  │
         │              │ • Normalizer    │
         │              │ • Query Planner │
         └──────────────└─────────────────┘
```

### Security Model
- **LLM outputs JSON only** - never raw SQL
- **Secure Query Builder** validates all filters against whitelist
- All database queries are parameterized
- Role-based access control

## 📁 Project Structure

```
├── app/                    # FastAPI Backend
│   ├── agents/             # AI Agents
│   │   ├── prompts.py      # System prompts
│   │   ├── conversation_agent.py
│   │   ├── normalizer_agent.py
│   │   └── query_planner.py
│   ├── routers/            # API Routes
│   │   ├── properties.py   # CRUD endpoints
│   │   └── query.py        # Natural language search
│   ├── services/
│   │   ├── query_builder.py  # Secure SQL builder
│   │   └── file_processor.py # PDF/Excel parser
│   ├── config.py
│   ├── database.py
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   └── main.py             # FastAPI app
├── bot/                    # Telegram Bot
│   ├── handlers.py         # Message handlers
│   ├── states.py           # Conversation states
│   └── main.py             # Bot entry point
├── database/
│   └── schema.sql          # PostgreSQL schema
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 15+
- OpenAI API key
- Telegram Bot Token (from @BotFather)

### 2. Setup

```bash
# Clone and enter directory
cd "Telegram project"

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env
# Edit .env with your keys
```

### 3. Database Setup

```bash
# With Docker
docker-compose up -d postgres

# Or manually run schema.sql on your PostgreSQL
```

### 4. Run

```bash
# Terminal 1: Start API
uvicorn app.main:app --reload

# Terminal 2: Start Bot
python -m bot.main
```

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and menu |
| `/add` | List a new property |
| `/search` | Natural language search |
| `/my_properties` | View your listings |
| `/help` | Get help |
| `/cancel` | Cancel current operation |

## 📱 Example Flows

### Adding a Property

```
User: /add
Bot: 🏠 Let's list your property! Are you putting it up for RENT or SALE?

User: Rent
Bot: 🔑 Great, a rental! What type of property is it?

User: Apartment
Bot: Got it! What's the monthly rent? (Use formats like 25k, 50L)

User: 25000
Bot: 📍 Which city and locality?

User: Andheri West, Mumbai
Bot: 🛏️ How many bedrooms?

User: 2
Bot: 📋 Here's your listing summary:
     🔑 For Rent
     🏷️ Type: Apartment
     📍 Location: Andheri West, Mumbai
     🛏️ Bedrooms: 2
     💰 Rent: ₹25,000/month
     
     Would you like to save this listing?

User: Yes
Bot: ✅ Property saved successfully!
```

### Searching Properties

```
User: 2BHK flat for rent in Mumbai under 30k

Bot: 🔍 Searching...

Bot: 🏠 Found 15 properties:

     1. 🔑 Rent | 2BHK Apartment
        📍 Andheri West, Mumbai
        💰 ₹25,000/mo
     
     2. 🔑 Rent | 2BHK Apartment
        📍 Bandra East, Mumbai
        💰 ₹28,000/mo
     ...
```

## 🔒 Security

### Query Whitelist
Only these fields can be queried:
- `listing_type`, `property_type`, `city`, `locality`
- `price`, `bedrooms`, `bathrooms`, `carpet_area`
- `furnishing`, `has_parking`, `has_gym`, etc.

### Allowed Operators
- Comparison: `=`, `!=`, `>`, `>=`, `<`, `<=`
- Text: `like` (contains)
- List: `in`

### Query Limits
- Max 10 filters per query
- Max 100 results per request
- All queries are parameterized

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/properties/` | Create property |
| `GET` | `/api/v1/properties/` | List with filters |
| `GET` | `/api/v1/properties/my` | User's properties |
| `GET` | `/api/v1/properties/{id}` | Get single |
| `PUT` | `/api/v1/properties/{id}` | Update |
| `DELETE` | `/api/v1/properties/{id}` | Delete |
| `POST` | `/api/v1/query/search` | Natural language search |
| `POST` | `/api/v1/query/parse` | Parse query (debug) |

## 🛠️ Configuration

Key environment variables in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/property_bot
TELEGRAM_BOT_TOKEN=your_token
OPENAI_API_KEY=your_key
OPENAI_MODEL_REGULAR=gpt-4o-mini
OPENAI_MODEL_ADVANCED=gpt-4o
```

## 📈 Scalability

- **Stateless backend** - horizontal scaling ready
- **Async database** - connection pooling built-in
- **Webhook mode** - efficient for high traffic
- **PostgreSQL indexes** - optimized for common queries

Tested for 30k+ users with proper infrastructure.
