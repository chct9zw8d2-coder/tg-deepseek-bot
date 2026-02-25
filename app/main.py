# app/main.py
import os
import logging
from typing import Optional

from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Update,
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://<service>.up.railway.app/webhook
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set (example: https://<service>.up.railway.app/webhook)")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

app = FastAPI()


# ---------- UI (меню) ----------
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Решить по тексту", callback_data="solve_text")],
            [InlineKeyboardButton(text="📷 Решить по фото", callback_data="solve_photo")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
        ]
    )


# ---------- DeepSeek wrappers (аккуратно, чтобы не падало от разных имён функций) ----------
async def deepseek_text(prompt: str) -> str:
    """
    Пытаемся импортировать функцию из app/deepseek.py разными именами.
    Если ничего не найдено — вернём понятную ошибку в ответ пользователю, а не уроним контейнер.
    """
    try:
        import app.deepseek as ds

        fn = getattr(ds, "ask_deepseek_text", None) or getattr(ds, "ask_text", None) or getattr(ds, "ask_deepseek", None)
        if not fn:
            return "⚠️ В app/deepseek.py не найдена функция ask_deepseek_text / ask_text / ask_deepseek."
        return await fn(prompt)
    except Exception as e:
        logger.exception("deepseek_text error")
        return f"⚠️ Ошибка DeepSeek (text): {e}"


async def deepseek_vision(image_bytes: bytes, prompt: str) -> str:
    """
    Пытаемся вызвать vision-функцию, если она есть.
    """
    try:
        import app.deepseek as ds

        fn = getattr(ds, "ask_deepseek_vision", None) or getattr(ds, "ask_vision", None)
        if not fn:
            return "⚠️ Vision не подключён в app/deepseek.py (нет ask_deepseek_vision / ask_vision)."
        return await fn(image_bytes=image_bytes, prompt=prompt)
    except Exception as e:
        logger.exception("deepseek_vision error")
        return f"⚠️ Ошибка DeepSeek (vision): {e}"


# ---------- Handlers ----------
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Как пользоваться:\n"
        "1) 📝 <b>Решить по тексту</b> — напиши задачу сообщением.\n"
        "2) 📷 <b>Решить по фото</b> — отправь фото задачи.\n\n"
        "Если меню не видно в Telegram Web — попробуй Telegram Desktop/телефон (у Web бывают баги с inline-кнопками).",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "solve_text")
async def cb_solve_text(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Ок! Пришли задачу <b>текстом</b> одним сообщением 👇")


@router.callback_query(F.data == "solve_photo")
async def cb_solve_photo(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Ок! Пришли <b>фото</b> задачи 👇")


@router.message(F.photo)
async def on_photo(message: Message):
    # берём фото максимального размера
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_bytes = await bot.download_file(file.file_path)

    # aiogram возвращает BufferedReader-like, приводим к bytes
    data = image_bytes.read() if hasattr(image_bytes, "read") else bytes(image_bytes)

    await message.answer("✅ Фото получил. Пытаюсь распознать и решить…")

    # Пытаемся vision
    result = await deepseek_vision(data, prompt="Распознай задание с фото и реши пошагово. Пиши аккуратно без лишних символов.")
    await message.answer(result, reply_markup=main_menu())


@router.message(F.text)
async def on_text(message: Message):
    text = (message.text or "").strip()
    if not text:
        return

    # не отвечаем второй раз на /start (на всякий)
    if text.startswith("/start"):
        return

    await message.answer("🧠 Думаю…")
    result = await deepseek_text(text)
    await message.answer(result, reply_markup=main_menu())


# ---------- Webhook + health ----------
@app.get("/")
async def health():
    return {"ok": True}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    # Ставим webhook
    try:
        logger.info("Setting webhook...")
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        logger.info("Webhook set OK")
    except Exception:
        logger.exception("Failed to set webhook")


@app.on_event("shutdown")
async def on_shutdown():
    # Снимаем webhook и закрываем сессию
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    try:
        await bot.session.close()
    except Exception:
        pass
