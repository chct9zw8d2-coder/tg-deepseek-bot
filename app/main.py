# app/main.py
import os
import logging

from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update, Message

from app.keyboards import main_menu_kb  # <- убедись, что функция/объект есть

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://xxx.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set (example: https://<service>.up.railway.app/webhook)")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

app = FastAPI()


# ---------- Healthcheck (Railway) ----------
@app.get("/")
async def health():
    return {"ok": True}


# ---------- Telegram handlers ----------
@router.message(F.text == "/start")
async def cmd_start(message: Message):
    # Меню (ReplyKeyboardMarkup) должно быть в app/keyboards.py
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=main_menu_kb())


# ---------- Webhook endpoint ----------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# ---------- Lifecycle ----------
@app.on_event("startup")
async def on_startup():
    logger.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set OK")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Removing webhook...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await bot.session.close()
    logger.info("Bot session closed")
