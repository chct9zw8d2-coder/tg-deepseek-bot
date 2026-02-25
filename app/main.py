import os
import logging
from typing import Optional, List

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Update, Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# ВАЖНО: эти функции должны реально существовать в app/deepseek.py
from app.deepseek import ask_deepseek_text, ask_deepseek_vision

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # например https://xxx.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

app = FastAPI()


# ---------- FSM (чтобы понимать, что ждём от пользователя) ----------
class Dialog(StatesGroup):
    waiting_text = State()
    waiting_photo = State()


# ---------- Клавиатура меню ----------
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Задать вопрос", callback_data="menu:ask")],
            [InlineKeyboardButton(text="📷 Решить по фото", callback_data="menu:photo")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
        ]
    )


# ---------- Команда /start ----------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu()
    )


# ---------- Нажатия кнопок меню ----------
@router.callback_query(F.data.startswith("menu:"))
async def menu_click(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":", 1)[1]

    # чтобы Telegram Web/мобилка не “крутили загрузку” на кнопке
    await cb.answer()

    if action == "ask":
        await state.set_state(Dialog.waiting_text)
        await cb.message.answer("Напиши свой вопрос текстом ✍️")

    elif action == "photo":
        await state.set_state(Dialog.waiting_photo)
        await cb.message.answer(
            "Пришли фото задания 📷\n\n"
            "Совет: чтобы распознавание было лучше — фото ровно, без наклона, текст крупно."
        )

    elif action == "help":
        await cb.message.answer(
            "Как пользоваться:\n"
            "• 🧠 Задать вопрос — пишешь текстом\n"
            "• 📷 Решить по фото — отправляешь фото задания\n\n"
            "Если меню не видно в Telegram Web — это норма, там иногда глючит inline UI.\n"
            "В телефоне должно работать стабильно.",
            reply_markup=main_menu()
        )


# ---------- Текстовый вопрос ----------
@router.message(Dialog.waiting_text, F.text)
async def handle_text_question(message: Message, state: FSMContext):
    question = message.text.strip()
    if not question:
        await message.answer("Напиши вопрос текстом 🙂")
        return

    await message.answer("Думаю... ⏳")

    try:
        answer = await ask_deepseek_text(question)
    except Exception as e:
        log.exception("DeepSeek text error")
        await message.answer(f"Ошибка DeepSeek: {e}")
        return

    await message.answer(answer, reply_markup=main_menu())
    await state.clear()


# ---------- Фото задания ----------
@router.message(Dialog.waiting_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    await message.answer("Считываю фото и решаю... ⏳")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        img_bytes = file_bytes.read()

        prompt = (
            "Распознай задачу с фото и реши её аккуратно.\n"
            "Пиши ответ структурировано, без лишних символов, формулы оформляй понятно."
        )
        answer = await ask_deepseek_vision(img_bytes, prompt)

    except Exception as e:
        log.exception("DeepSeek vision error")
        await message.answer(f"Ошибка Vision: {e}\n\nПришли другое фото (чётче/ровнее).")
        return

    await message.answer(answer, reply_markup=main_menu())
    await state.clear()


# ---------- Если прислали что-то не то в режиме фото ----------
@router.message(Dialog.waiting_photo)
async def waiting_photo_wrong(message: Message):
    await message.answer("Я жду именно фото 📷 (не документ и не текст).")


# ---------- Фоллбек: любые сообщения вне режима ----------
@router.message(F.text)
async def fallback_text(message: Message):
    # чтобы бот не “молчал”, если человек просто пишет без меню
    await message.answer("Выбери пункт меню 👇", reply_markup=main_menu())


# ---------- Webhook endpoint ----------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# ---------- Healthcheck ----------
@app.get("/")
async def root():
    return {"status": "ok"}


# ---------- Startup / Shutdown ----------
@app.on_event("startup")
async def on_startup():
    # ставим вебхук один раз
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )
    log.info("Webhook set.")


@app.on_event("shutdown")
async def on_shutdown():
    # аккуратно снимаем вебхук и закрываем сессию
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await bot.session.close()
