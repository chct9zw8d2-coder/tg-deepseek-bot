from fastapi import FastAPI, Request
import os
import logging

# импорт твоих модулей (оставь если уже есть)
from app.config import BOT_TOKEN
from app.deepseek import ask_deepseek
from app.db import init_db
from app.keyboards import get_main_keyboard

app = FastAPI()

logging.basicConfig(level=logging.INFO)


# ✅ ЭТОТ ENDPOINT НУЖЕН ДЛЯ RAILWAY (убирает 502)
@app.get("/")
async def root():
    return {"status": "ok"}


# webhook endpoint
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    logging.info(f"Webhook received: {data}")

    # здесь твоя логика бота
    return {"ok": True}


# startup event
@app.on_event("startup")
async def startup():
    logging.info("Starting application...")
    await init_db()
    logging.info("Application startup complete.")


# shutdown event
@app.on_event("shutdown")
async def shutdown():
    logging.info("Application shutdown complete.")
