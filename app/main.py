# app/main.py
import base64
import logging
import os
from typing import Optional

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.deepseek import ask_deepseek_text, ask_deepseek_vision

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://xxx.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set (example: https://<service>.up.railway.app/webhook)")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

app = FastAPI()

# --- Кнопки меню (ReplyKeyboard) ---
BTN_SOLVE_TEXT = "📝 Решить (текст)"
BTN_SOLVE_PHOTO = "📷 Решить (фото)"
BTN_HELP = "ℹ️ Помощь"

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_SOLVE_TEXT), KeyboardButton(text=BTN_SOLVE_PHOTO)],
        [KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
    selective=False,
)

# Простейшее состояние "ждём фото?"
WAITING_PHOTO_USERS: set[int] = set()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    # ставим webhook один раз при старте
    logger.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    logger.info("Webhook set OK")


@app.on_event("shutdown")
async def on_shutdown():
    # снимаем webhook
    logger.info("Removing webhook...")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await bot.session.close()
    logger.info("Shutdown complete")


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@router.message(F.text == "/start")
async def cmd_start(message: Message):
    WAITING_PHOTO_USERS.discard(message.from_user.id)
    await message.answer(
        "Привет! Выбери режим:\n"
        "📝 <b>текст</b> — вставь задание\n"
        "📷 <b>фото</b> — пришли фото задания\n",
        reply_markup=main_kb,
    )


@router.message(F.text == BTN_HELP)
async def help_cmd(message: Message):
    WAITING_PHOTO_USERS.discard(message.from_user.id)
    await message.answer(
        "Как пользоваться:\n"
        "1) 📝 Решить (текст) — отправь текст задания.\n"
        "2) 📷 Решить (фото) — нажми и отправь фото.\n\n"
        "Я стараюсь писать ответ <b>обычным текстом</b> без LaTeX-кавычек.",
        reply_markup=main_kb,
    )


@router.message(F.text == BTN_SOLVE_TEXT)
async def solve_text_mode(message: Message):
    WAITING_PHOTO_USERS.discard(message.from_user.id)
    await message.answer(
        "Ок! Пришли текст задания одним сообщением 👇",
        reply_markup=main_kb,
    )


@router.message(F.text == BTN_SOLVE_PHOTO)
async def solve_photo_mode(message: Message):
    WAITING_PHOTO_USERS.add(message.from_user.id)
    await message.answer("Ок! Пришли фото задания 👇", reply_markup=main_kb)


@router.message(F.photo)
async def on_photo(message: Message):
    # Если пользователь не нажимал "фото режим" — всё равно обработаем, это удобнее
    user_id = message.from_user.id
    WAITING_PHOTO_USERS.discard(user_id)

    await message.answer("Считываю фото и решаю… ⏳")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    img_bytes = file_bytes.read()

    # подпись к фото как подсказка
    prompt = (message.caption or "").strip()
    if not prompt:
        prompt = "Распознай задание на изображении и реши. Ответ дай обычным текстом, без LaTeX скобок типа \\( \\) и \\[ \\]."

    try:
        answer = await ask_deepseek_vision(prompt=prompt, image_bytes=img_bytes, mime="image/jpeg")
    except Exception as e:
        logger.exception("Vision error")
        await message.answer(f"Ошибка vision: {e}")
        return

    await message.answer(answer, reply_markup=main_kb)


@router.message(F.text)
async def on_text(message: Message):
    text = (message.text or "").strip()
    if not text:
        return

    # если человек нажал "фото режим" но прислал текст — подскажем
    if message.from_user.id in WAITING_PHOTO_USERS:
        await message.answer("Я жду фото 🙂 Пришли фото задания.")
        return

    await message.answer("Думаю… ⏳")
    try:
        answer = await ask_deepseek_text(prompt=text)
    except Exception as e:
        logger.exception("Text error")
        await message.answer(f"Ошибка text: {e}")
        return

    await message.answer(answer, reply_markup=main_kb)
