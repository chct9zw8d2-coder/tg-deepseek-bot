import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

from app.config import settings
from app.keyboards import main_menu
from app.deepseek import ask_deepseek, ask_deepseek_vision
from app.db import db

# логирование
logging.basicConfig(level=logging.INFO)

# FastAPI
app = FastAPI()

# Bot
bot = Bot(
    token=settings.BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Dispatcher
dp = Dispatcher()


# =========================
# START COMMAND
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message):
    await db.ensure_user(message.from_user.id)

    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu()
    )


# =========================
# TEXT HANDLER
# =========================
@dp.message(F.text)
async def text_handler(message: Message):
    try:
        await message.answer("Думаю... 🤔")

        answer = await ask_deepseek(message.text)

        await message.answer(answer)

    except Exception as e:
        logging.exception(e)
        await message.answer("Ошибка при обработке запроса ❌")


# =========================
# PHOTO HANDLER (VISION)
# =========================
@dp.message(F.photo)
async def photo_handler(message: Message):
    try:
        await message.answer("Анализирую фото... 📷")

        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"

        answer = await ask_deepseek_vision(file_url)

        await message.answer(answer)

    except Exception as e:
        logging.exception(e)
        await message.answer("Ошибка анализа фото ❌")


# =========================
# STARTUP
# =========================
@app.on_event("startup")
async def on_startup():
    logging.info("Starting bot...")

    await db.connect()
    await db.init()

    await bot.set_webhook(
        settings.WEBHOOK_URL,
        drop_pending_updates=True
    )

    logging.info("Bot started!")


# =========================
# WEBHOOK
# =========================
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# =========================
# ROOT
# =========================
@app.get("/")
async def root():
    return {"status": "ok"}
