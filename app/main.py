from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings

api = FastAPI()  # ВАЖНО: Railway ищет app.main:api

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


@dp.message()
async def handle_message(message: types.Message):
    await message.answer("Бот работает ✅")


@api.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@api.get("/")
async def root():
    return {"status": "ok"}


@api.on_event("startup")
async def on_startup():
    # ставим webhook при запуске
    await bot.set_webhook(settings.WEBHOOK_URL)
