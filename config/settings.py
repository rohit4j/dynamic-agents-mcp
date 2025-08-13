"""Application settings and configuration."""

import os
import logging
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    google_api_key: str
    gemini_model: str = "gemini-1.5-flash"
    
    # Database Configuration
    database_url: str = "postgresql://rohit.jain@localhost:5432/langgraph_chats"
    
    # Logging Configuration
    log_level: str = "DEBUG"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


def setup_logging(log_level: str = "DEBUG"):
    """Setup application logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def validate_settings(settings: Settings) -> None:
    """Validate required settings."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")