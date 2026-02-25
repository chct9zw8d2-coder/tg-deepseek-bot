import logging
import os
import base64

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode

from app.config import settings
from app.deepseek import ask_text as ask_deepseek_text, ask_vision as ask_deepseek_vision

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = settings.BOT_TOKEN
WEBHOOK_URL = settings.WEBHOOK_URL

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

app = FastAPI()


# ================= MENU =================

def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Решить задачу", callback_data="menu:solve")],
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="menu:ask")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
    ])
    return keyboard


# ================= START =================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logging.info(f"START from {message.from_user.id}")

    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu()
    )


# ================= CALLBACK MENU =================

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id

    logging.info(f"CALLBACK from {user_id}: {data}")

    if data == "menu:solve":
        await callback.message.answer(
            "📸 Отправь фото задачи, и я решу её"
        )

    elif data == "menu:ask":
        await callback.message.answer(
            "✏️ Напиши свой вопрос"
        )

    elif data == "menu:help":
        await callback.message.answer(
            "Я могу:\n"
            "• решать задачи по фото\n"
            "• отвечать на вопросы\n"
            "• помогать с учебой"
        )

    await callback.answer()


# ================= PHOTO HANDLER =================

@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    logging.info(f"PHOTO from {message.from_user.id}")

    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)

    image_bytes = file_bytes.read()

    await message.answer("🔍 Анализирую изображение...")

    answer = await ask_deepseek_vision(image_bytes)

    await message.answer(answer)


# ================= TEXT HANDLER =================

@dp.message()
async def handle_text(message: types.Message):
    text = message.text

    logging.info(f"TEXT from {message.from_user.id}: {text}")

    answer = await ask_deepseek_text(text)

    await message.answer(answer)


# ================= WEBHOOK =================

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# ================= STARTUP =================

@app.on_event("startup")
async def on_startup():
    logging.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
