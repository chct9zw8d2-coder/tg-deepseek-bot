from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Update, Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage

from io import BytesIO

from app.config import settings
from app.keyboards import main_menu

# ВАЖНО: подставь правильные функции из твоего deepseek.py:
# Если у тебя есть ask_text / solve_homework_vision — используй их.
# Если у тебя ask_deepseek / ask_deepseek_vision — используй их.
try:
    from app.deepseek import ask_text as ask_deepseek_text
except Exception:
    from app.deepseek import ask_deepseek as ask_deepseek_text

try:
    from app.deepseek import solve_homework_vision as ask_deepseek_vision
except Exception:
    try:
        from app.deepseek import ask_vision as ask_deepseek_vision
    except Exception:
        from app.deepseek import ask_deepseek_vision  # если у тебя так названо


app = FastAPI()
api = app

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# режим для пользователя
USER_MODE = {}  # user_id -> "hw" | "any" | "photo"


@dp.message(CommandStart())
async def start_cmd(message: Message):
    USER_MODE[message.from_user.id] = "any"
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=main_menu())


@dp.callback_query(F.data == "menu:hw")
async def cb_hw(cb: CallbackQuery):
    USER_MODE[cb.from_user.id] = "hw"
    await cb.message.answer("📚 Напиши задание текстом — решу и объясню 👇", reply_markup=main_menu())
    await cb.answer()


@dp.callback_query(F.data == "menu:photo")
async def cb_photo(cb: CallbackQuery):
    USER_MODE[cb.from_user.id] = "photo"
    await cb.message.answer("📷 Пришли фото задачи — решу через Vision ✅", reply_markup=main_menu())
    await cb.answer()


@dp.callback_query(F.data == "menu:any")
async def cb_any(cb: CallbackQuery):
    USER_MODE[cb.from_user.id] = "any"
    await cb.message.answer("❓ Задай любой вопрос — отвечу 👇", reply_markup=main_menu())
    await cb.answer()


@dp.callback_query(F.data == "menu:sub")
async def cb_sub(cb: CallbackQuery):
    await cb.message.answer(
        "💎 Подписка на месяц:\n"
        "Старт — 50 запросов/сутки — 199 ⭐\n"
        "Про — 100 запросов/сутки — 350 ⭐\n"
        "Премиум — 200 запросов/сутки — 700 ⭐",
        reply_markup=main_menu()
    )
    await cb.answer()


@dp.callback_query(F.data == "menu:ref")
async def cb_ref(cb: CallbackQuery):
    await cb.message.answer("👥 Реферальная программа — подключим следующим шагом.", reply_markup=main_menu())
    await cb.answer()


@dp.callback_query(F.data == "menu:topup")
async def cb_topup(cb: CallbackQuery):
    await cb.message.answer(
        "➕ Докупить запросы:\n"
        "+10 — 99 ⭐\n"
        "+50 — 150 ⭐",
        reply_markup=main_menu()
    )
    await cb.answer()


@dp.message(F.photo)
async def handle_photo(message: Message):
    await message.answer("📷 Принял фото. Решаю через Vision...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    buf = BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    image_bytes = buf.getvalue()

    answer = await ask_deepseek_vision(
        image_bytes,
        "Реши задачу с фото. Ответ обычным текстом, без LaTeX."
    )
    await message.answer(answer, reply_markup=main_menu())


@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith("/"):
        return

    mode = USER_MODE.get(message.from_user.id, "any")

    if mode == "hw":
        prompt = (
            "Реши задачу. Пиши обычным текстом (без LaTeX).\n"
            "Формат: Условие / Решение / Ответ.\n\n"
            f"Задача:\n{message.text}"
        )
        answer = await ask_deepseek_text(prompt)
    else:
        answer = await ask_deepseek_text(message.text)

    await message.answer(answer, reply_markup=main_menu())


@app.on_event("startup")
async def on_startup():
    # чтобы не было дублей после падений
    await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok"}
