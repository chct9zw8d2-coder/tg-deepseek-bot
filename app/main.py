import os
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # должен быть .../webhook

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()


# ✅ healthcheck для Railway
@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="💬 Чат")],
            [types.KeyboardButton(text="🧠 Vision")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Выберите режим:", reply_markup=keyboard)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    # Важно: WEBHOOK_URL должен оканчиваться на /webhook
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query", "inline_query"],
        drop_pending_updates=True,
    )
    logging.info(f"Webhook set to: {WEBHOOK_URL}")


@app.on_event("shutdown")
async def on_shutdown():
    # ⚠️ лучше НЕ удалять webhook на Railway (частые рестарты)
    # await bot.delete_webhook()
    await bot.session.close()
