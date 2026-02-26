import os
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()


# HEALTHCHECK (важно для Railway)
@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# TEST COMMAND
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Бот работает ✅")


# WEBHOOK ENDPOINT
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.exception("Webhook error")
        return JSONResponse({"ok": False})


# STARTUP
@app.on_event("startup")
async def startup():
    logging.info("Bot started")


# SHUTDOWN
@app.on_event("shutdown")
async def shutdown():
    await bot.session.close()
