import os
import logging

from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update, Message

from app.keyboards import main_menu_kb


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")


BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL not set")


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
router = Router()
dp.include_router(router)

app = FastAPI()


# healthcheck для Railway
@app.get("/")
async def root():
    return {"status": "ok"}


# команда start
@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет! Бот работает.",
        reply_markup=main_menu_kb()
    )


# webhook endpoint
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# запуск
@app.on_event("startup")
async def on_startup():
    logger.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set OK")


# остановка
@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Closing bot session...")
    await bot.session.close()
