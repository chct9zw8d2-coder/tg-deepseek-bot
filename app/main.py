import os
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://xxxxx.up.railway.app/webhook
WEBHOOK_PATH = "/webhook"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set")


# --- Aiogram ---
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())

router = Router()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Учёба"), KeyboardButton(text="🧠 Спросить ИИ")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="💳 Подписка")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! 👋\nВот меню:",
        reply_markup=main_menu_kb(),
    )


dp.include_router(router)


# --- FastAPI ---
app = FastAPI()


@app.get("/")
async def health():
    return {"ok": True}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    # ставим webhook на WEBHOOK_URL (он должен заканчиваться на /webhook)
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")


@app.on_event("shutdown")
async def on_shutdown():
    # снимаем webhook и закрываем сессию
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()
    logging.info("Webhook deleted, bot session closed")
