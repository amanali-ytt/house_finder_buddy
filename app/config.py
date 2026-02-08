"""
Configuration module for the Property Bot application.
Loads settings from environment variables with validation.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/property_bot"
    database_sync_url: str = "postgresql://user:password@localhost:5432/property_bot"
    
    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_url: Optional[str] = None
    
    # OpenAI
    openai_api_key: str = ""
    openai_model_regular: str = "gpt-4o-mini"
    openai_model_advanced: str = "gpt-4o"
    
    # Application
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Security
    secret_key: str = "change-me-in-production"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"
    
    # Query Limits
    max_query_results: int = 100
    max_filters_per_query: int = 10
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
