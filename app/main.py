import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ======================
# LOGGING
# ======================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================
# ENV
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL not set")

WEBHOOK_PATH = "/webhook"
WEBHOOK_FULL = f"{WEBHOOK_URL}{WEBHOOK_PATH}"

# ======================
# BOT
# ======================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()

# ======================
# HANDLERS
# ======================

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "✅ Бот работает!\n\n"
        "Меню скоро будет здесь."
    )


@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Ты написал:\n{message.text}")


# ======================
# FASTAPI LIFESPAN
# ======================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting bot...")

    # удалить старый webhook
    await bot.delete_webhook(drop_pending_updates=True)

    # установить новый webhook
    await bot.set_webhook(WEBHOOK_FULL)

    logger.info(f"Webhook set to: {WEBHOOK_FULL}")

    yield

    logger.info("Stopping bot...")
    await bot.session.close()


# ======================
# FASTAPI APP
# ======================

app = FastAPI(lifespan=lifespan)


# healthcheck
@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# webhook endpoint
@app.post(WEBHOOK_PATH)
async def webhook(request: Request):

    data = await request.json()

    update = Update.model_validate(data)

    await dp.feed_update(bot, update)

    return JSONResponse({"ok": True})
