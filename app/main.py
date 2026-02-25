# app/main.py
import os
import logging
from typing import Callable, Awaitable, Optional

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    CallbackQuery,
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://<service>.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set (example: https://<service>.up.railway.app/webhook)")

# --- Try to import DeepSeek helpers with fallback names ---
ask_deepseek_text: Optional[Callable[[str], Awaitable[str]]] = None
ask_deepseek_vision: Optional[Callable[[str, bytes], Awaitable[str]]] = None

try:
    # варианты имен, которые у тебя встречались в логах/правках
    from app.deepseek import ask_deepseek_text as _t  # type: ignore
    ask_deepseek_text = _t
except Exception:
    try:
        from app.deepseek import ask_text as _t  # type: ignore
        ask_deepseek_text = _t
    except Exception:
        try:
            from app.deepseek import ask_deepseek as _t  # type: ignore
            ask_deepseek_text = _t
        except Exception:
            ask_deepseek_text = None

try:
    from app.deepseek import ask_deepseek_vision as _v  # type: ignore
    ask_deepseek_vision = _v
except Exception:
    try:
        from app.deepseek import ask_vision as _v  # type: ignore
        ask_deepseek_vision = _v
    except Exception:
        try:
            from app.deepseek import ask_deepseek_vl as _v  # type: ignore
            ask_deepseek_vision = _v
        except Exception:
            ask_deepseek_vision = None


# --- Bot / Dispatcher ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧠 Спросить (текст)", callback_data="mode:text"),
            InlineKeyboardButton(text="👁️ Спросить (фото)", callback_data="mode:vision"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
        ],
    ])


@router.message(F.text.in_({"/start", "start"}))
async def cmd_start(message: Message):
    text = (
        "Привет! Я бот.\n\n"
        "Выбери режим:\n"
        "🧠 <b>Текст</b> — задаёшь вопрос текстом\n"
        "👁️ <b>Фото</b> — присылаешь фото + вопрос\n"
    )
    await message.answer(text, reply_markup=main_menu())


@router.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Как пользоваться:\n"
        "1) Нажми 🧠 и задай вопрос текстом\n"
        "2) Нажми 👁️ и пришли фото с подписью-вопросом\n"
    )


# simple mode flags in memory (на один инстанс)
USER_MODE: dict[int, str] = {}


@router.callback_query(F.data.startswith("mode:"))
async def cb_mode(call: CallbackQuery):
    await call.answer()
    mode = call.data.split(":", 1)[1]
    USER_MODE[call.from_user.id] = mode
    if mode == "text":
        await call.message.answer("Ок, режим 🧠. Напиши вопрос текстом.")
    else:
        await call.message.answer("Ок, режим 👁️. Пришли фото с подписью-вопросом (caption).")


@router.message(F.photo)
async def on_photo(message: Message):
    mode = USER_MODE.get(message.from_user.id, "vision")
    if mode != "vision":
        await message.answer("Сейчас включён режим 🧠. Нажми 👁️ в меню, если хочешь разбор фото.")
        return

    if ask_deepseek_vision is None:
        await message.answer("Vision-функция не подключилась в коде (нет подходящей функции в app/deepseek.py).")
        return

    caption = (message.caption or "").strip()
    if not caption:
        caption = "Опиши, что на фото, и реши задачу/объясни."

    # скачать фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    data = await bot.download_file(file.file_path)
    img_bytes = data.read()

    await message.answer("⏳ Думаю по фото...")
    try:
        reply = await ask_deepseek_vision(caption, img_bytes)
    except Exception as e:
        logger.exception("Vision request failed")
        await message.answer(f"Ошибка vision-запроса: {e}")
        return

    await message.answer(reply)


@router.message(F.text)
async def on_text(message: Message):
    mode = USER_MODE.get(message.from_user.id, "text")
    if mode != "text":
        # если человек написал текст, но режим vision — всё равно отвечаем текстом, чтобы “не молчало”
        mode = "text"

    if ask_deepseek_text is None:
        await message.answer("Text-функция не подключилась в коде (нет подходящей функции в app/deepseek.py).")
        return

    question = message.text.strip()
    await message.answer("⏳ Думаю...")
    try:
        reply = await ask_deepseek_text(question)
    except Exception as e:
        logger.exception("Text request failed")
        await message.answer(f"Ошибка text-запроса: {e}")
        return

    await message.answer(reply)


# --- FastAPI app ---
app = FastAPI()


@app.get("/")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    # ставим webhook
    logger.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set OK")


# ВАЖНО: на shutdown webhook можно НЕ снимать, чтобы не было “мигания” при рестартах Railway
@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Closing bot session...")
    await bot.session.close()
