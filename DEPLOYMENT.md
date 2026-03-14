# Deployment Guide

This document explains how to run House Finder Buddy locally, on a VM, or with Docker.

## 1. What a deployer needs

- Python 3.11+
- PostgreSQL 15+
- Telegram bot token
- NVIDIA API key

## 2. Required environment variables

```env
DATABASE_URL=postgresql+asyncpg://propertybot:propertybot_secret@localhost:5432/property_bot
DATABASE_SYNC_URL=postgresql://propertybot:propertybot_secret@localhost:5432/property_bot
TELEGRAM_BOT_TOKEN=
NVIDIA_API_KEY=
NVIDIA_MODEL=deepseek-ai/deepseek-v3.2
LLM_MODEL_REGULAR=
LLM_MODEL_ADVANCED=
APP_ENV=production
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=change-this
ALLOWED_ORIGINS=https://your-frontend.example.com
```

## 3. Local VM deployment

### Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Create database

```sql
CREATE ROLE propertybot LOGIN PASSWORD 'propertybot_secret';
CREATE DATABASE property_bot OWNER propertybot;
```

### Initialize schema

```bash
.venv\Scripts\python.exe -c "import asyncio; from bot import database as db; asyncio.run(db.init_db())"
```

### Start services

API:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Bot:

```bash
.venv\Scripts\python.exe -m bot.main
```

## 4. Docker deployment

If Docker is installed:

```bash
docker compose up -d --build
```

The compose file expects:
- `TELEGRAM_BOT_TOKEN`
- `NVIDIA_API_KEY`
- optional `NVIDIA_MODEL`
- optional `LLM_MODEL_REGULAR`
- optional `LLM_MODEL_ADVANCED`

## 5. Webhook mode

To run the Telegram bot via webhook instead of polling:

```env
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
```

The bot will automatically switch from polling to webhook mode when that variable is set.

## 6. Reverse proxy recommendations

For public API hosting:
- terminate TLS at nginx, Caddy, or a cloud load balancer
- forward traffic to the FastAPI process on port `8000`
- allow only required origins in `ALLOWED_ORIGINS`

## 7. Logging and operations

Recommended improvements before serious production use:
- structured logging
- process supervision with systemd, NSSM, or container restart policies
- database backups
- real Alembic migrations
- rate limiting and auth hardening

## 8. Known blockers before real production

- client-controlled `telegram_id` is not secure enough for a public API
- schema lifecycle is model-driven rather than migration-driven
- Telegram persistence still has in-memory behavior for some user data
- no secret manager integration yet
