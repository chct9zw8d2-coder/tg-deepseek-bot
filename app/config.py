from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Set
import re

def _parse_admin_ids(v: str | None) -> Set[int]:
    if not v:
        return set()
    parts = re.split(r"[ ,;]+", v.strip())
    out=set()
    for p in parts:
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            continue
    return out

class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str = Field(..., description="Telegram bot token")
    BOT_USERNAME: Optional[str] = Field(default=None, description="@username without @, used for referral links")
    WEBHOOK_URL: str = Field(..., description="Public webhook url, e.g. https://xxx.up.railway.app/webhook")

    # Admin(s)
    ADMIN_ID: Optional[str] = None
    ADMIN_IDS: Optional[str] = None

    # DeepSeek (OpenAI-compatible)
    DEEPSEEK_API_KEY: str = Field(..., description="DeepSeek API key")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com", description="DeepSeek base url")
    DEEPSEEK_TEXT_MODEL: str = Field(default="deepseek-chat", description="Text model id")

    # Optional vision endpoint (OpenAI-compatible). If not set, bot uses OCR -> text -> DeepSeek.
    DEEPSEEK_VISION_BASE_URL: Optional[str] = None
    DEEPSEEK_VISION_MODEL: Optional[str] = None
    DEEPSEEK_VISION_API_KEY: Optional[str] = None

    # Database (Railway Postgres). Railway often provides postgres://... which we auto-convert.
    DATABASE_URL: str = Field(..., description="Postgres connection string")

    # Limits / referral bonuses
    REF_BONUS_REQUESTS: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def admin_ids(self) -> Set[int]:
        # Accept ADMIN_ID or ADMIN_IDS (comma/space separated)
        combined = ",".join([x for x in [self.ADMIN_ID, self.ADMIN_IDS] if x])
        return _parse_admin_ids(combined)

    @property
    def database_url_async(self) -> str:
        url = self.DATABASE_URL
        # Railway often gives postgres://; SQLAlchemy async wants postgresql+asyncpg://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

settings = Settings()
