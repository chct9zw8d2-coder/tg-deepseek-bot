from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings


# FastAPI app
app = FastAPI()


# Telegram bot
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Установка webhook при запуске
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(settings.WEBHOOK_URL)
    print("Webhook set:", settings.WEBHOOK_URL)


# Удаление webhook при остановке (не обязательно, но правильно)
@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
    print("Webhook removed")


# Обработка всех сообщений
@dp.message()
async def handle_message(message: types.Message):
    await message.answer("Бот работает ✅")


# Endpoint для Telegram webhook
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# Проверка что сервер работает
@app.get("/")
async def root():
    return {"status": "ok"}
