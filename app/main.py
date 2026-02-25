import logging
import os

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, Update
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from app.deepseek import ask_text, ask_vision


logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL not set")


# ========= INIT =========

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()


# ========= MENU =========

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Решить по фото")],
        [KeyboardButton(text="❓ Задать вопрос")],
    ],
    resize_keyboard=True
)


# ========= HANDLERS =========

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=menu
    )


@dp.message(F.photo)
async def handle_photo(message: Message):
    await message.answer("Обрабатываю фото...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    image_bytes = file_bytes.read()

    try:
        result = await ask_vision(image_bytes)
        await message.answer(result)
    except Exception as e:
        logging.exception(e)
        await message.answer("Ошибка при обработке фото.")


@dp.message()
async def handle_text(message: Message):
    text = message.text

    if text in ["📸 Решить по фото", "❓ Задать вопрос"]:
        await message.answer("Отправь фото или напиши вопрос.")
        return

    try:
        result = await ask_text(text)
        await message.answer(result)
    except Exception as e:
        logging.exception(e)
        await message.answer("Ошибка при обработке запроса.")


# ========= WEBHOOK =========

@app.on_event("startup")
async def on_startup():
    logging.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)
    logging.info("Webhook set.")


@app.on_event("shutdown")
async def on_shutdown():
    logging.info("Removing webhook...")
    await bot.delete_webhook()
    await bot.session.close()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# ========= HEALTH CHECK =========

@app.get("/")
async def root():
    return {"status": "ok"}
