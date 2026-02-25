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

from io import BytesIO

from app.config import settings
from app.deepseek import ask_deepseek, solve_homework_from_text
from app.ocr import ocr_image  # <-- добавь файл app/ocr.py (ниже)


app = FastAPI()
api = app

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ----------------------------
# Простая "модальность" по пользователю
# ----------------------------
USER_MODE = {}  # user_id -> "hw" | "any" | "photo"


# ----------------------------
# Inline menu (видно в Telegram Web)
# ----------------------------
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


@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    USER_MODE[message.from_user.id] = "any"
    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu(),
    )


# ----------------------------
# CALLBACKS
# ----------------------------
@dp.callback_query(F.data == "menu:hw")
async def cb_hw(cb: CallbackQuery):
    USER_MODE[cb.from_user.id] = "hw"
    await cb.message.answer("📚 Напиши задание текстом — решу и объясню (обычным текстом, без LaTeX) 👇")
    await cb.answer()


@dp.callback_query(F.data == "menu:photo")
async def cb_photo(cb: CallbackQuery):
    USER_MODE[cb.from_user.id] = "photo"
    await cb.message.answer(
        "📷 Пришли фото задачи.\n"
        "Совет: лучше отправлять как *файл* (без сжатия) — так распознаёт намного точнее.",
        parse_mode="Markdown",
    )
    await cb.answer()


@dp.callback_query(F.data == "menu:any")
async def cb_any(cb: CallbackQuery):
    USER_MODE[cb.from_user.id] = "any"
    await cb.message.answer("❓ Задай любой вопрос — отвечу 👇")
    await cb.answer()


@dp.callback_query(F.data == "menu:sub")
async def cb_sub(cb: CallbackQuery):
    await cb.message.answer(
        "💎 Подписка на месяц:\n\n"
        "Старт — 50 запросов/сутки — 199 ⭐\n"
        "Про — 100 запросов/сутки — 350 ⭐\n"
        "Премиум — 200 запросов/сутки — 700 ⭐\n\n"
        "Подключим оплату Stars на следующем шаге."
    )
    await cb.answer()


@dp.callback_query(F.data == "menu:ref")
async def cb_ref(cb: CallbackQuery):
    await cb.message.answer("👥 Реферальная программа: подключим на следующем шаге (ссылка + начисления).")
    await cb.answer()


@dp.callback_query(F.data == "menu:topup")
async def cb_topup(cb: CallbackQuery):
    await cb.message.answer(
        "➕ Докупить запросы:\n\n"
        "+10 запросов — 99 ⭐\n"
        "+50 запросов — 150 ⭐\n\n"
        "Подключим оплату Stars на следующем шаге."
    )
    await cb.answer()


# ----------------------------
# PHOTO HANDLER (OCR -> DeepSeek)
# ----------------------------
@dp.message(F.photo)
async def handle_photo(message: Message):
    # Если пользователь не выбирал режим, всё равно попробуем решить
    mode = USER_MODE.get(message.from_user.id, "photo")

    await message.answer("📷 Принял фото. Распознаю текст...")

    # Берем самое большое фото
    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    buf = BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    image_bytes = buf.getvalue()

    text = ocr_image(image_bytes)

    if len(text) < 10:
        await message.answer(
            "Не получилось нормально распознать текст 😕\n"
            "Попробуй:\n"
            "1) отправить фото как *файл* (без сжатия)\n"
            "2) кадр ближе (задача занимает 80–90% кадра)\n"
            "3) без бликов/наклона",
            parse_mode="Markdown",
        )
        return

    await message.answer("✅ Текст распознал. Решаю...")

    # Решение по OCR тексту, без LaTeX
    answer = await solve_homework_from_text(text)
    await message.answer(answer)


# ----------------------------
# TEXT HANDLER (DeepSeek)
# ----------------------------
@dp.message(F.text)
async def handle_text(message: Message):
    # команды типа /start не трогаем
    if message.text.startswith("/"):
        return

    mode = USER_MODE.get(message.from_user.id, "any")

    # Для "Помощь с дз" — отвечаем более структурировано, но без LaTeX
    if mode == "hw":
        prompt = (
            "Реши и объясни задачу. Пиши обычным текстом, без LaTeX и без слешей.\n"
            "Структура: Условие / Решение / Ответ.\n\n"
            f"Задача:\n{message.text}"
        )
        answer = await ask_deepseek(prompt)
        await message.answer(answer)
        return

    # Для "любой вопрос" — просто ответ
    answer = await ask_deepseek(message.text)
    await message.answer(answer)


# ----------------------------
# WEBHOOK
# ----------------------------
@app.on_event("startup")
async def on_startup():
    # Убирает накопленные /start и дубли после падений
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
