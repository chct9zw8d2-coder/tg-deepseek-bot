import os
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Update, Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.deepseek import ask_deepseek_text, ask_deepseek_vision, close_http

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # https://xxx.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

app = FastAPI()


class Dialog(StatesGroup):
    waiting_text = State()
    waiting_photo = State()


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Задать вопрос", callback_data="m:ask")],
            [InlineKeyboardButton(text="📷 Решить по фото", callback_data="m:photo")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="m:help")],
        ]
    )


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=menu_kb())


@router.callback_query(F.data.startswith("m:"))
async def menu_click(cb: CallbackQuery, state: FSMContext):
    await cb.answer()  # важно, чтобы Telegram не "крутил" кнопку

    action = cb.data.split(":", 1)[1]

    if action == "ask":
        await state.set_state(Dialog.waiting_text)
        await cb.message.answer("Напиши вопрос текстом ✍️")

    elif action == "photo":
        await state.set_state(Dialog.waiting_photo)
        await cb.message.answer(
            "Пришли фото задания 📷\n"
            "Совет: фото ровно, текст крупно, без бликов."
        )

    elif action == "help":
        await cb.message.answer(
            "Как пользоваться:\n"
            "• 🧠 Задать вопрос — пишешь текст\n"
            "• 📷 Решить по фото — отправляешь фото задания\n\n"
            "Если Telegram Web глючит с меню — проверяй в телефоне.",
            reply_markup=menu_kb()
        )


@router.message(Dialog.waiting_text, F.text)
async def handle_text(message: Message, state: FSMContext):
    q = (message.text or "").strip()
    if not q:
        await message.answer("Напиши вопрос текстом 🙂")
        return

    await message.answer("Думаю... ⏳")
    try:
        ans = await ask_deepseek_text(q)
    except Exception as e:
        log.exception("DeepSeek text error")
        await message.answer(f"Ошибка DeepSeek TEXT: {e}", reply_markup=menu_kb())
        await state.clear()
        return

    await message.answer(ans, reply_markup=menu_kb())
    await state.clear()


@router.message(Dialog.waiting_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    await message.answer("Считываю фото и решаю... ⏳")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        buf = await bot.download_file(file.file_path)
        img_bytes = buf.read()

        prompt = (
            "Распознай задание с фото и реши аккуратно.\n"
            "Пиши ответ понятным текстом, без LaTeX-скобок типа \\( \\) и \\[ \\].\n"
            "Если формулы нужны — пиши их обычным текстом."
        )
        ans = await ask_deepseek_vision(img_bytes, prompt)

    except Exception as e:
        log.exception("DeepSeek vision error")
        await message.answer(
            f"Ошибка DeepSeek VISION: {e}\n\n"
            "Попробуй другое фото: ровнее/чётче/без бликов.",
            reply_markup=menu_kb()
        )
        await state.clear()
        return

    await message.answer(ans, reply_markup=menu_kb())
    await state.clear()


@router.message(Dialog.waiting_photo)
async def waiting_photo_wrong(message: Message):
    await message.answer("Я жду именно фото 📷 (не документ и не текст).")


@router.message(F.text)
async def fallback(message: Message):
    await message.answer("Выбери пункт меню 👇", reply_markup=menu_kb())


@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    # ВАЖНО: явно разрешаем callback_query + message
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    log.info("Webhook set OK")


@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await bot.session.close()
    await close_http()
