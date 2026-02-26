import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()  # например: https://tg-deepseek-bot-production.up.railway.app/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()
router = Router()
dp.include_router(router)

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Помощь"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🧾 Статус")],
    ],
    resize_keyboard=True,
)

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("✅ Бот запущен. Выбери действие:", reply_markup=menu_kb)

@router.message(F.text == "🧾 Статус")
async def status(message: Message):
    await message.answer("🟢 Status: ok")

@router.message(F.text == "📚 Помощь")
async def help_(message: Message):
    await message.answer("Напиши /start чтобы открыть меню.")

@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    await message.answer("Настройки пока в разработке.")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    await dp.feed_raw_update(bot, update)
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    # ВАЖНО: включаем вебхук только если WEBHOOK_URL задан
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"Webhook set to: {WEBHOOK_URL}")
    else:
        logging.warning("WEBHOOK_URL is not set (webhook will NOT be configured)")

@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
