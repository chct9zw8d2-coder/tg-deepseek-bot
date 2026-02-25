# app/main.py
import logging
import os

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://<service>.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set (example: https://<service>.up.railway.app/webhook)")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ✅ ВАЖНО: здесь должен быть router = Router() в app/bot.py
from app.bot import router  # если файл/переменная иначе — поменяй только эту строку

dp.include_router(router)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    # ставим webhook один раз при старте
    logger.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set OK")


@app.on_event("shutdown")
async def on_shutdown():
    # корректно закрываем сессию, чтобы не было "Unclosed client session"
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await bot.session.close()


@app.get("/")
async def health():
    # ✅ healthcheck для Railway (поставь Healthcheck Path = "/")
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
