from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    DEEPSEEK_API_KEY: str
    WEBHOOK_URL: str

    DATABASE_URL: str
    ADMIN_IDS: str = ""          # "123,456"
    BOT_USERNAME: str = ""       # без @
    REF_PERCENT: int = 20

    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS.strip():
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]

settings = Settings()
