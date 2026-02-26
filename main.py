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

# ======================
# LOGGING
# ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

# ======================
# ENV
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

# Railway обычно даёт публичный домен вида *.up.railway.app
# Попробуем собрать WEBHOOK_BASE сами, если WEBHOOK_URL не задан.
# Ты можешь задать WEBHOOK_URL вручную: https://tg-deepseek-bot-production.up.railway.app
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # base url, без /webhook

# Часто полезно, если Railway прокидывает публичный домен в переменные (может отличаться)
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")

WEBHOOK_PATH = "/webhook"

def build_webhook_base() -> str:
    if WEBHOOK_URL:
        return WEBHOOK_URL.rstrip("/")
    if RAILWAY_PUBLIC_DOMAIN:
        # RAILWAY_PUBLIC_DOMAIN может быть без схемы
        domain = RAILWAY_PUBLIC_DOMAIN.strip().rstrip("/")
        if domain.startswith("http://") or domain.startswith("https://"):
            return domain
        return f"https://{domain}"
    # Фоллбек (у тебя домен известен) — можно заменить на свой,
    # но лучше всё же задать WEBHOOK_URL в переменных Railway.
    return "https://tg-deepseek-bot-production.up.railway.app"

WEBHOOK_BASE = build_webhook_base()
WEBHOOK_FULL = f"{WEBHOOK_BASE}{WEBHOOK_PATH}"

# ======================
# BOT
# ======================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# ======================
# HANDLERS
# ======================
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("✅ Бот работает!\n\nМеню скоро будет здесь.")

@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Ты написал:\n{message.text}")

# ======================
# FASTAPI LIFESPAN
# ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot...")
    logger.info("Webhook will be set to: %s", WEBHOOK_FULL)
    logger.info("PORT env: %s", os.getenv("PORT"))

    # Ставим вебхук. drop_pending_updates=True можно включить,
    # но delete_webhook делать не обязательно.
    await bot.set_webhook(WEBHOOK_FULL, drop_pending_updates=True)

    yield

    logger.info("Stopping bot...")
    await bot.session.close()

# ======================
# FASTAPI APP
# ======================
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
