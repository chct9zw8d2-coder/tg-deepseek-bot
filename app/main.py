from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.deepseek import ask_text, ask_vision

app = FastAPI()
api = app

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def main_menu_kb() -> ReplyKeyboardMarkup:
    # Кнопки меню (ReplyKeyboard — чтобы реально отображались)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1) Помощь с дз"), KeyboardButton(text="2) Фото → решить дз")],
            [KeyboardButton(text="3) Ответить на вопрос")],
            [KeyboardButton(text="4) Подписка"), KeyboardButton(text="6) Докупить")],
            [KeyboardButton(text="5) Реферальная программа")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери пункт меню 👇",
    )


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu_kb()
    )


@dp.message(lambda m: (m.text or "").strip() in ["1) Помощь с дз", "3) Ответить на вопрос"])
async def menu_text_mode(message: types.Message):
    await message.answer(
        "Ок! Напиши свой вопрос текстом — я отвечу ✅",
        reply_markup=main_menu_kb()
    )


@dp.message(lambda m: (m.text or "").strip() == "2) Фото → решить дз")
async def menu_photo_mode(message: types.Message):
    await message.answer(
        "Отправь фото задания 📷 (лучше ровно, без наклона). Я решу и пришлю ответ ✅",
        reply_markup=main_menu_kb()
    )


@dp.message(lambda m: (m.text or "").strip() in ["4) Подписка", "5) Реферальная программа", "6) Докупить"])
async def menu_stub(message: types.Message):
    # Заглушка (чтобы меню работало сразу). Подписки/рефералка/докупка подключаются отдельными хендлерами.
    await message.answer(
        "Этот раздел в процессе подключения. Сейчас доступны: 1) текст, 2) фото.\n\n"
        "Напиши вопрос или отправь фото 👇",
        reply_markup=main_menu_kb()
    )


@dp.message(lambda m: m.photo is not None)
async def handle_photo(message: types.Message):
    try:
        photo = message.photo[-1]  # самое большое
        file = await bot.get_file(photo.file_id)
        # скачиваем файл в память
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()
    except Exception as e:
        await message.answer(f"❌ Не смог скачать фото: {e}", reply_markup=main_menu_kb())
        return

    await message.answer("🧠 Думаю над задачей с фото...")

    answer = await ask_vision(image_bytes, "Реши задачу с фото. Ответ дай обычным текстом, без LaTeX.")
    await message.answer(answer, reply_markup=main_menu_kb())


@dp.message()
async def handle_text(message: types.Message):
    text = (message.text or "").strip()
    if not text:
        return

    await message.answer("🧠 Думаю...")

    answer = await ask_text(text)
    await message.answer(answer, reply_markup=main_menu_kb())


@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(settings.WEBHOOK_URL)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok"}
