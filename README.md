# House Finder Buddy

House Finder Buddy is a Telegram-first property listing and search app backed by FastAPI, PostgreSQL, and an LLM-powered parsing/query layer.

Users can:
- onboard by uploading a property document
- add listings through chat or file upload
- search listings in natural language
- view their own saved properties

## Stack

- Telegram bot: `python-telegram-bot`
- API: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy async
- LLM provider: NVIDIA hosted API on [build.nvidia.com](https://build.nvidia.com/)

## Project Layout

```text
app/        FastAPI app, models, routers, agents, services
bot/        Telegram bot handlers, persistence, DB adapter
database/   SQL schema reference
tests/      Regression tests and optional live-provider tests
```

## Recommended Provider Setup

This repo is configured to work best with an NVIDIA API key.

Recommended default model:
- `deepseek-ai/deepseek-v3.2`

You only need:
- `TELEGRAM_BOT_TOKEN`
- `NVIDIA_API_KEY`
- PostgreSQL running locally or remotely

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Telegram bot token from BotFather
- NVIDIA API key from [build.nvidia.com](https://build.nvidia.com/)

### 2. Clone and configure

```bash
git clone https://github.com/amanali-ytt/house_finder_buddy.git
cd house_finder_buddy
```

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create your env file:

```bash
copy .env.example .env
```

Then fill in at least:

```env
DATABASE_URL=postgresql+asyncpg://propertybot:propertybot_secret@localhost:5432/property_bot
DATABASE_SYNC_URL=postgresql://propertybot:propertybot_secret@localhost:5432/property_bot
TELEGRAM_BOT_TOKEN=your_bot_token
NVIDIA_API_KEY=your_nvidia_key
NVIDIA_MODEL=deepseek-ai/deepseek-v3.2
SECRET_KEY=replace-this-in-real-deployments
```

### 3. Start PostgreSQL

Option A: local PostgreSQL

Create a database and user that match `.env`:

```sql
CREATE ROLE propertybot LOGIN PASSWORD 'propertybot_secret';
CREATE DATABASE property_bot OWNER propertybot;
```

Option B: Docker

If Docker is available on your machine:

```bash
docker compose up -d postgres
```

### 4. Initialize schema

The app can create tables from SQLAlchemy models on startup via the bot DB initializer.

You can also initialize manually:

```bash
.venv\Scripts\python.exe -c "import asyncio; from bot import database as db; asyncio.run(db.init_db())"
```

### 5. Run the app

Start the API:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the bot in another terminal:

```bash
.venv\Scripts\python.exe -m bot.main
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Environment Variables

Main variables:

```env
DATABASE_URL=
DATABASE_SYNC_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_URL=
NVIDIA_API_KEY=
NVIDIA_MODEL=deepseek-ai/deepseek-v3.2
LLM_MODEL_REGULAR=
LLM_MODEL_ADVANCED=
APP_ENV=development
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
MAX_QUERY_RESULTS=100
MAX_FILTERS_PER_QUERY=10
```

Notes:
- `LLM_MODEL_REGULAR` and `LLM_MODEL_ADVANCED` are optional overrides.
- If those are blank, the app uses `NVIDIA_MODEL`.

## Telegram Commands

- `/start`
- `/add`
- `/upload`
- `/search`
- `/my_properties`
- `/help`
- `/cancel`

## Testing

Run the default test suite:

```bash
.venv\Scripts\python.exe -m pytest -q
```

Expected result without live provider credentials:
- regression tests pass
- live LLM tests are skipped

## Deployment Notes

### Minimal production checklist

- use a real `SECRET_KEY`
- use a dedicated PostgreSQL instance
- keep `.env` out of source control
- rotate any tokens used during development
- set `DEBUG=false`
- run behind a reverse proxy if exposing the API publicly

### Current production caveats

This project still needs hardening before a serious production deployment:
- API ownership checks currently rely on client-supplied `telegram_id`
- migrations are not yet formalized through Alembic workflow
- bot `user_data` persistence is still partly in-memory

For a more complete deployment guide, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Publishing Safety

Before pushing your own fork:

- make sure `.env` is not committed
- rotate any Telegram or NVIDIA keys that were ever stored locally in shared environments
- verify `git status` does not include local DB or log artifacts
