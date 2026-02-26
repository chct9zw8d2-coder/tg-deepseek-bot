import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Update
from aiogram.filters import CommandStart
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://tg-deepseek-bot-production.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    # простое меню/ответ
    await message.answer("Меню: \n1) ... \n2) ...")

dp.include_router(router)

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook set to: {WEBHOOK_URL}")
    else:
        logging.warning("WEBHOOK_URL is not set, webhook will NOT be configured")


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
