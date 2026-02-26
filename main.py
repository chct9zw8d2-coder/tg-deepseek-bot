import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # базовый домен, без /webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

# Пытаемся угадать публичный домен Railway, если WEBHOOK_URL не задан
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")

WEBHOOK_PATH = "/webhook"

def build_webhook_base() -> str:
    if WEBHOOK_URL:
        return WEBHOOK_URL.rstrip("/")
    if RAILWAY_PUBLIC_DOMAIN:
        # иногда приходит с https://, иногда без
        base = RAILWAY_PUBLIC_DOMAIN.strip()
        if not base.startswith("http://") and not base.startswith("https://"):
            base = "https://" + base
        return base.rstrip("/")
    raise RuntimeError("WEBHOOK_URL not set (and Railway public domain env not found)")

WEBHOOK_FULL = build_webhook_base() + WEBHOOK_PATH

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("✅ Бот работает!\n\nМеню скоро будет здесь.")

@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Ты написал:\n{message.text}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot...")

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_FULL)

    logger.info(f"Webhook set to: {WEBHOOK_FULL}")
    yield
    logger.info("Stopping bot...")
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})
