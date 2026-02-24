from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode

from app.config import settings
from app.deepseek import ask_deepseek
from app.ocr import ocr_image_bytes

api = FastAPI()
bot = Bot(settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Бот работает. Напиши вопрос или отправь фото.")

@dp.message(F.photo)
async def photo(message: Message):
    file = await bot.get_file(message.photo[-1].file_id)
    f = await bot.download_file(file.file_path)
    text = ocr_image_bytes(f.read())
    answer = await ask_deepseek("Реши задачу: " + text, reason=True)
    await message.answer(answer)

@dp.message()
async def text(message: Message):
    answer = await ask_deepseek(message.text)
    await message.answer(answer)

@api.on_event("startup")
async def startup():
    await bot.set_webhook(settings.WEBHOOK_URL)

@api.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    await dp.feed_webhook_update(bot, data)
    return {"ok": True}
