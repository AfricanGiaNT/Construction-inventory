"""Configuration settings for the Construction Inventory Bot."""

import os
from typing import List, Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

from pydantic import validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Telegram Configuration
    telegram_bot_token: str
    telegram_allowed_chat_ids: str
    
    # Airtable Configuration
    airtable_api_key: str
    airtable_base_id: str
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_enabled: bool = False
    
    # Application Settings
    app_env: str = "production"
    log_level: str = "INFO"
    
    # Thresholds and Limits
    default_approval_threshold: int = 100
    rate_limit_per_minute: int = 30
    
    # Scheduled Jobs
    daily_report_time: str = "08:00"
    weekly_backup_day: int = 0  # Monday
    weekly_backup_time: str = "09:00"
    
    # Background Worker Settings
    worker_sleep_interval: int = 10  # seconds between polling cycles
    
    @validator("telegram_allowed_chat_ids")
    def parse_chat_ids(cls, v: str) -> List[int]:
        """Parse comma-separated chat IDs into a list of integers."""
        try:
            return [int(chat_id.strip()) for chat_id in v.split(",") if chat_id.strip()]
        except ValueError:
            raise ValueError("Invalid chat ID format. Use comma-separated integers.")
    
    class Config:
        env_file = "config/.env"
        env_file_encoding = "utf-8"


# Global settings instance - will be created when needed
# settings = Settings()
