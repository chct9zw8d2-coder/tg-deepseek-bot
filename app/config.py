from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str
    DEEPSEEK_API_KEY: str
    DATABASE_URL: str | None = None
    WEBHOOK_URL: str
    ADMIN_IDS: str = ""

    def get_database_url(self) -> str | None:
        if not self.DATABASE_URL:
            return None
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

settings = Settings()
