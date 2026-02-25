import logging
import os

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.filters import CommandStart
from aiogram.types import Update

# ВАЖНО:
# В deepseek.py должны быть функции:
#   async def ask_deepseek_text(prompt: str) -> str
#   async def ask_deepseek_vision(image_bytes: bytes, prompt: str) -> str
from app.deepseek import ask_deepseek_text, ask_deepseek_vision

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # например https://xxx.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set (must end with /webhook)")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- Меню ---
menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧮 Решить задачу"), KeyboardButton(text="🖼️ Решить по фото")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)

# --- /start ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=menu_kb)

# --- Кнопки меню ---
@dp.message(F.text == "ℹ️ Помощь")
async def help_(message: Message):
    await message.answer(
        "• 🧮 Решить задачу — напиши текстом условие\n"
        "• 🖼️ Решить по фото — отправь фото с задачей\n\n"
        "Можно просто отправить текст или фото — я пойму 🙂",
        reply_markup=menu_kb
    )

@dp.message(F.text == "🧮 Решить задачу")
async def solve_text_hint(message: Message):
    await message.answer("Ок! Пришли условие задачи текстом 👇", reply_markup=menu_kb)

@dp.message(F.text == "🖼️ Решить по фото")
async def solve_photo_hint(message: Message):
    await message.answer("Ок! Отправь фото задачи 📸 (желательно ровно и крупно) 👇", reply_markup=menu_kb)

# --- Фото -> vision ---
@dp.message(F.photo)
async def on_photo(message: Message):
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        img_bytes = file_bytes.read()

        prompt = (
            "Считай текст задачи с изображения аккуратно. "
            "НЕ добавляй лишние символы типа \\( или \\[. "
            "Реши задачу и оформи ответ понятно. "
            "Формулы пиши обычным текстом, без LaTeX-обвязки."
        )
        answer = await ask_deepseek_vision(img_bytes, prompt)
        await message.answer(answer, reply_markup=menu_kb)
    except Exception as e:
        log.exception("vision error")
        await message.answer(f"Ошибка обработки фото: {e}", reply_markup=menu_kb)

# --- Текст -> text model ---
@dp.message(F.text)
async def on_text(message: Message):
    text = message.text.strip()
    if not text:
        return
    try:
        prompt = (
            "Реши задачу. Пиши аккуратно, структурировано. "
            "Формулы — обычным текстом (без \\( \\) и без \\[ \\]).\n\n"
            f"Задача:\n{text}"
        )
        answer = await ask_deepseek_text(prompt)
        await message.answer(answer, reply_markup=menu_kb)
    except Exception as e:
        log.exception("text error")
        await message.answer(f"Ошибка: {e}", reply_markup=menu_kb)

# --- FastAPI endpoints ---
@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# --- lifecycle ---
@app.on_event("startup")
async def on_startup():
    log.info("Setting webhook...")
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )
    log.info("Webhook set.")

@app.on_event("shutdown")
async def on_shutdown():
    # чтобы не было Unclosed client session
    await bot.session.close()
    log.info("Bot session closed.")
