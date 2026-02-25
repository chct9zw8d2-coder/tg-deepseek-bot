from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.deepseek import ask_deepseek

app = FastAPI()
api = app  # ВАЖНО: Dockerfile запускает uvicorn "app.main:api"

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Привет! Напиши мне вопрос — отвечу через DeepSeek ✅")


@dp.message()
async def handle_message(message: types.Message):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришли текстом 🙂")
        return

    answer = await ask_deepseek(text)
    await message.answer(answer)


@app.on_event("startup")
async def on_startup():
    # Устанавливаем вебхук при старте
    # (WEBHOOK_URL должен быть вида https://.../webhook)
    await bot.set_webhook(settings.WEBHOOK_URL)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok"}
