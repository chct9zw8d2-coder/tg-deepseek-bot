from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Update, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.deepseek import ask_deepseek

app = FastAPI()
api = app  # оставил как у тебя

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- Главное меню (Reply Keyboard) ---
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Помощь с дз"), KeyboardButton(text="📷 Фото и решить дз")],
            [KeyboardButton(text="❓ Ответить на вопрос"), KeyboardButton(text="💎 Подписка")],
            [KeyboardButton(text="👥 Реферальная программа"), KeyboardButton(text="➕ Докупить")],
        ],
        resize_keyboard=True,
        selective=True,
    )


@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    # очищаем состояние (на будущее, если FSM используешь)
    await state.clear()

    # Важно: reply_markup=main_menu() чтобы меню точно появилось
    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu()
    )


# --- Нажатия на пункты меню ---
@dp.message(F.text == "📚 Помощь с дз")
async def menu_help_hw(message: Message):
    await message.answer("Напиши вопрос/задание текстом — я помогу 👇")


@dp.message(F.text == "📷 Фото и решить дз")
async def menu_photo(message: Message):
    await message.answer("Пришли фото задачи (картинкой). Я распознаю и решу ✅")


@dp.message(F.text == "❓ Ответить на вопрос")
async def menu_any_question(message: Message):
    await message.answer("Задай любой вопрос — отвечу 👇")


@dp.message(F.text == "💎 Подписка")
async def menu_sub(message: Message):
    await message.answer(
        "Подписка на месяц:\n"
        "1) Старт — 50 запросов/сутки за 199 ⭐\n"
        "2) Про — 100 запросов/сутки за 350 ⭐\n"
        "3) Премиум — 200 запросов/сутки за 700 ⭐\n\n"
        "Пока это меню-заглушка. Дальше подключим оплату Stars."
    )


@dp.message(F.text == "👥 Реферальная программа")
async def menu_ref(message: Message):
    await message.answer(
        "Реферальная программа (заглушка):\n"
        "Скоро здесь будет твоя ссылка и начисления."
    )


@dp.message(F.text == "➕ Докупить")
async def menu_topup(message: Message):
    await message.answer(
        "Докупить запросы (заглушка):\n"
        "+10 запросов — 99 ⭐\n"
        "+50 запросов — 150 ⭐\n\n"
        "Дальше подключим оплату Stars."
    )


# --- Общий обработчик текста (важно: не отвечаем на команды) ---
@dp.message(F.text)
async def handle_text(message: Message):
    # команды типа /start не трогаем, чтобы не было дублей
    if message.text and message.text.startswith("/"):
        return

    answer = await ask_deepseek(message.text)
    await message.answer(answer)


@app.on_event("startup")
async def on_startup():
    # Важно: очищаем очередь накопленных апдейтов (это и давало много одинаковых /start)
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
