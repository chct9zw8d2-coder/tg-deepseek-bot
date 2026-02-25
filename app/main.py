from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Update,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.deepseek import ask_deepseek

# --- FastAPI ---
app = FastAPI()

# --- Bot / Dispatcher ---
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# =========================
# INLINE MENU
# =========================
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Помощь с дз", callback_data="menu:hw")],
            [InlineKeyboardButton(text="📷 Фото и решить дз", callback_data="menu:photo")],
            [InlineKeyboardButton(text="❓ Ответить на любой вопрос", callback_data="menu:any")],
            [InlineKeyboardButton(text="💎 Подписка", callback_data="menu:sub")],
            [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="menu:ref")],
            [InlineKeyboardButton(text="➕ Докупить", callback_data="menu:topup")],
        ]
    )


# =========================
# START
# =========================
@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu(),
    )


# =========================
# CALLBACK MENU HANDLERS
# =========================
@dp.callback_query(F.data == "menu:hw")
async def cb_hw(cb: CallbackQuery):
    await cb.message.answer("📚 Напиши задание текстом — решу и объясню 👇")
    await cb.answer()


@dp.callback_query(F.data == "menu:photo")
async def cb_photo(cb: CallbackQuery):
    await cb.message.answer("📷 Пришли фото задачи — я распознаю и решу.")
    await cb.answer()


@dp.callback_query(F.data == "menu:any")
async def cb_any(cb: CallbackQuery):
    await cb.message.answer("❓ Задай любой вопрос — отвечу 👇")
    await cb.answer()


@dp.callback_query(F.data == "menu:sub")
async def cb_sub(cb: CallbackQuery):
    await cb.message.answer(
        "💎 Подписка на месяц:\n\n"
        "Старт — 50 запросов/сутки — 199 ⭐\n"
        "Про — 100 запросов/сутки — 350 ⭐\n"
        "Премиум — 200 запросов/сутки — 700 ⭐"
    )
    await cb.answer()


@dp.callback_query(F.data == "menu:ref")
async def cb_ref(cb: CallbackQuery):
    await cb.message.answer(
        "👥 Реферальная программа:\n\n"
        "Скоро здесь появится твоя ссылка и заработок."
    )
    await cb.answer()


@dp.callback_query(F.data == "menu:topup")
async def cb_topup(cb: CallbackQuery):
    await cb.message.answer(
        "➕ Докупить запросы:\n\n"
        "+10 запросов — 99 ⭐\n"
        "+50 запросов — 150 ⭐"
    )
    await cb.answer()


# =========================
# TEXT HANDLER (DeepSeek)
# =========================
@dp.message(F.text)
async def handle_text(message: Message):
    # игнорируем команды
    if message.text.startswith("/"):
        return

    await message.answer("⏳ Думаю...")

    try:
        answer = await ask_deepseek(message.text)
    except Exception as e:
        answer = f"Ошибка DeepSeek: {e}"

    await message.answer(answer)


# =========================
# WEBHOOK
# =========================
@app.on_event("startup")
async def on_startup():
    # очищаем старые апдейты (устраняет дубли)
    await bot.set_webhook(
        settings.WEBHOOK_URL,
        drop_pending_updates=True,
    )


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok"}
