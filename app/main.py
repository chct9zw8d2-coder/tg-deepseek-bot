import logging
from io import BytesIO

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Update, Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.keyboards import main_menu
from app.deepseek import ask_deepseek, ask_deepseek_vision

logging.basicConfig(level=logging.INFO)

app = FastAPI()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

USER_MODE = {}  # user_id -> "hw" | "any" | "photo"


@dp.message(CommandStart())
async def start_cmd(message: Message):
    USER_MODE[message.from_user.id] = "any"
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=main_menu())


@dp.callback_query(F.data.startswith("menu:"))
async def menu_router(cb: CallbackQuery):
    logging.info(f"CALLBACK from {cb.from_user.id}: {cb.data}")

    action = cb.data.split(":", 1)[1]
    uid = cb.from_user.id

    if action == "hw":
        USER_MODE[uid] = "hw"
        await cb.message.answer("📚 Напиши задание текстом — решу и объясню 👇", reply_markup=main_menu())

    elif action == "photo":
        USER_MODE[uid] = "photo"
        await cb.message.answer("📷 Пришли фото задачи — решу через Vision ✅", reply_markup=main_menu())

    elif action == "any":
        USER_MODE[uid] = "any"
        await cb.message.answer("❓ Задай любой вопрос — отвечу 👇", reply_markup=main_menu())

    elif action == "sub":
        await cb.message.answer(
            "💎 Подписка на месяц:\n"
            "1) Старт — 50 запросов/сутки — 199 ⭐\n"
            "2) Про — 100 запросов/сутки — 350 ⭐\n"
            "3) Премиум — 200 запросов/сутки — 700 ⭐\n\n"
            "Оплата Stars подключим следующим шагом.",
            reply_markup=main_menu()
        )

    elif action == "ref":
        await cb.message.answer("👥 Реферальная программа — подключим следующим шагом.", reply_markup=main_menu())

    elif action == "topup":
        await cb.message.answer(
            "➕ Докупить запросы:\n"
            "+10 запросов — 99 ⭐\n"
            "+50 запросов — 150 ⭐\n\n"
            "Оплата Stars подключим следующим шагом.",
            reply_markup=main_menu()
        )

    await cb.answer()  # обязательно, иначе Telegram “крутит”


@dp.message(F.photo)
async def handle_photo(message: Message):
    uid = message.from_user.id
    mode = USER_MODE.get(uid, "any")

    # даже если режим не photo — всё равно решаем фото
    await message.answer("📷 Принял фото. Решаю...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    buf = BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    image_bytes = buf.getvalue()

    prompt = "Реши задачу с фото. Пиши обычным текстом, без LaTeX. Дай итоговый ответ в конце."
    answer = await ask_deepseek_vision(image_bytes, prompt)

    await message.answer(answer, reply_markup=main_menu())


@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith("/"):
        return

    uid = message.from_user.id
    mode = USER_MODE.get(uid, "any")

    if mode == "hw":
        prompt = (
            "Реши задачу и объясни кратко.\n"
            "Пиши обычным текстом, без LaTeX.\n"
            "Формат: Решение -> Ответ.\n\n"
            f"Задача:\n{message.text}"
        )
    else:
        prompt = message.text

    await message.answer("Думаю... 🤔")
    answer = await ask_deepseek(prompt)
    await message.answer(answer, reply_markup=main_menu())


@app.on_event("startup")
async def on_startup():
    logging.info("Setting webhook...")
    await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)
    logging.info("Webhook set.")


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok"}
