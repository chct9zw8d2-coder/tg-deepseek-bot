import os
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import CommandStart

# =====================
# ЛОГИ
# =====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================
# ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set")

WEBHOOK_PATH = "/webhook"
WEBHOOK_FULL = f"{WEBHOOK_URL}{WEBHOOK_PATH}"

# =====================
# FASTAPI
# =====================
app = FastAPI()

# =====================
# TELEGRAM
# =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =====================
# HANDLERS
# =====================
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Бот работает через Railway webhook.\n"
        "Отправь сообщение."
    )


@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Ты написал:\n{message.text}")


# =====================
# HEALTHCHECK
# =====================
@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# =====================
# WEBHOOK ENDPOINT
# =====================
@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# =====================
# STARTUP
# =====================
@app.on_event("startup")
async def on_startup():
    logger.info("Bot starting...")

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_FULL)

    logger.info(f"Webhook set to: {WEBHOOK_FULL}")


# =====================
# SHUTDOWN
# =====================
@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Bot shutdown")
    await bot.session.close()


# =====================
# LOCAL RUN ONLY
# =====================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
