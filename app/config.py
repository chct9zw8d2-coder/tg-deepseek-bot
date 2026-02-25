from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):

    BOT_TOKEN: str
    DEEPSEEK_API_KEY: str
    DATABASE_URL: str
    WEBHOOK_URL: str
    ADMIN_IDS: str = ""

    def get_database_url(self) -> str:
        url = self.DATABASE_URL

        # Railway fix
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        return url


settings = Settings()
