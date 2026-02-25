import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBHOOK_URL: str
    BOT_USERNAME: str | None = None
    ADMIN_IDS: str | None = None

    # DB
    DATABASE_URL: str | None = None

    # DeepSeek
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_TEXT_MODEL: str = "deepseek-chat"
    DEEPSEEK_VISION_MODEL: str = "deepseek-vl2"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
