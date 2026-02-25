import logging
import os

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Fallback: если WEBHOOK_URL не задан, пробуем собрать его из Railway domain (если есть)
railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
if not WEBHOOK_URL and railway_domain:
    WEBHOOK_URL = f"https://{railway_domain}/webhook"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
dp.include_router(router)

app = FastAPI()


# healthcheck endpoint (Railway будет дёргать его)
@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# webhook endpoint
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# startup
@app.on_event("startup")
async def on_startup():
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set. Bot will run, but webhook won't be configured.")
        logger.warning("Set WEBHOOK_URL to: https://<your-domain>.up.railway.app/webhook")
        return

    logger.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set OK: %s", WEBHOOK_URL)


# shutdown
@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Closing bot session...")
    await bot.session.close()
