from __future__ import annotations
import uuid
from dataclasses import dataclass
from aiogram.types import LabeledPrice

# Stars currency
CURRENCY = "XTR"

@dataclass(frozen=True)
class Plan:
    key: str
    title: str
    stars: int
    daily_limit: int
    days: int = 30

PLANS = {
    "start": Plan(key="start", title="Подписка Старт", stars=199, daily_limit=50),
    "pro": Plan(key="pro", title="Подписка Про", stars=350, daily_limit=100),
    "premium": Plan(key="premium", title="Подписка Премиум", stars=700, daily_limit=200),
}

TOPUPS = {
    "10": {"title": "Пакет +10 запросов", "stars": 99, "amount": 10},
    "50": {"title": "Пакет +50 запросов", "stars": 150, "amount": 50},
}

def make_payload(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex}"

def prices_for_stars(stars: int) -> list[LabeledPrice]:
    # In Stars, amount is in "stars" units
    return [LabeledPrice(label=f"{stars}⭐", amount=stars)]
