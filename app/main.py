from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Update, Message, ReplyKeyboardMarkup, KeyboardButton

from aiogram.fsm.storage.memory import MemoryStorage

from io import BytesIO

from app.config import settings
from app.deepseek import ask_text, solve_homework_vision


app = FastAPI()
api = app

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# простой режим
USER_MODE = {}  # user_id -> "any" | "photo"


def menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Помощь с дз"), KeyboardButton(text="📷 Фото → решить дз")],
            [KeyboardButton(text="❓ Ответить на любой вопрос")],
            [KeyboardButton(text="💎 Подписка"), KeyboardButton(text="➕ Докупить")],
            [KeyboardButton(text="👥 Реферальная программа")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери пункт меню 👇",
    )


@dp.message(CommandStart())
async def start_cmd(message: Message):
    USER_MODE[message.from_user.id] = "any"
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=menu_kb())


@dp.message(F.text == "📷 Фото → решить дз")
async def set_photo_mode(message: Message):
    USER_MODE[message.from_user.id] = "photo"
    await message.answer(
        "Отправь фото задачи 📷\n\n"
        "Советы:\n"
        "• лучше как *файл* (без сжатия)\n"
        "• кадр ближе, без бликов и наклона",
        parse_mode="Markdown",
        reply_markup=menu_kb(),
    )


@dp.message(F.text.in_({"📚 Помощь с дз", "❓ Ответить на любой вопрос"}))
async def set_any_mode(message: Message):
    USER_MODE[message.from_user.id] = "any"
    await message.answer("Ок! Напиши вопрос текстом — отвечу 👇", reply_markup=menu_kb())


@dp.message(F.text.in_({"💎 Подписка", "👥 Реферальная программа", "➕ Докупить"}))
async def stub(message: Message):
    await message.answer(
        "Этот раздел подключим следующим шагом.\n"
        "Сейчас доступны: текстовые вопросы и решение по фото ✅",
        reply_markup=menu_kb(),
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    await message.answer("📷 Принял фото. Решаю через Vision...")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        buf = BytesIO()
        await bot.download_file(file.file_path, destination=buf)
        image_bytes = buf.getvalue()
    except Exception as e:
        await message.answer(f"❌ Не смог скачать фото: {e}", reply_markup=menu_kb())
        return

    answer = await solve_homework_vision(
        image_bytes,
        "Реши задачу с фото. Ответ дай обычным текстом, без LaTeX и без обратных слешей."
    )
    await message.answer(answer, reply_markup=menu_kb())


@dp.message(F.text)
async def text_handler(message: Message):
    # игнорируем команды кроме /start
    if message.text.startswith("/"):
        return

    await message.answer("🧠 Думаю...")

    answer = await ask_text(message.text)
    await message.answer(answer, reply_markup=menu_kb())


@app.on_event("startup")
async def on_startup():
    # это лечит дубли, если сервис падал и Telegram накопил апдейты
    await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True


@app.get("/")
async def root():
    return {"status": "ok"}
