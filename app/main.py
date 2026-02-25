import os
import tempfile
from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Update, LabeledPrice
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.deepseek import ask_deepseek, SYSTEM_HOMEWORK, SYSTEM_GENERAL, SYSTEM_PHOTO
from app.keyboards import main_menu, back_menu, sub_inline, topup_inline
from app.states import Mode
from app.db import DB
from app.ocr import image_to_text

app = FastAPI()
api = app

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db = DB(settings.DATABASE_URL)

# планы подписки
PLANS = {
    "start": {"price": 199, "daily": 50, "title": "Подписка Старт (30 дней)"},
    "pro": {"price": 350, "daily": 100, "title": "Подписка Про (30 дней)"},
    "premium": {"price": 700, "daily": 200, "title": "Подписка Премиум (30 дней)"},
}

TOPUPS = {
    "10": {"price": 99, "credits": 10, "title": "Докупить +10 запросов"},
    "50": {"price": 150, "credits": 50, "title": "Докупить +50 запросов"},
}

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids_list()

def make_ref_link(user_id: int) -> str:
    if not settings.BOT_USERNAME:
        return "❗ BOT_USERNAME не задан в переменных окружения Railway."
    return f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}"

async def consume_or_block(message: types.Message) -> bool:
    ok, status = await db.consume_request(message.from_user.id, is_admin(message.from_user.id))
    if ok:
        return True
    await message.answer(
        "❌ Лимит запросов закончился.\n\n"
        "Выбери:\n"
        "💳 Подписка — чтобы получить дневные лимиты на 30 дней\n"
        "➕ Докупить — чтобы добавить запросы",
        reply_markup=main_menu()
    )
    return False


@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    # referral parsing
    referrer_id = None
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            referrer_id = int(parts[1].replace("ref_", "").strip())
        except:
            referrer_id = None

    await db.ensure_user(message.from_user.id, referrer_id=referrer_id)
    await state.clear()

    await message.answer(
        "Привет! Выбери пункт меню 👇",
        reply_markup=main_menu()
    )


@dp.message(F.text == "⬅️ Назад в меню")
async def back_to_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню 👇", reply_markup=main_menu())


# -------- Menu actions -> set state --------

@dp.message(F.text == "📚 Помощь с дз")
async def menu_homework(message: types.Message, state: FSMContext):
    await state.set_state(Mode.homework)
    await message.answer("Ок! Напиши задачу/вопрос по дз 👇", reply_markup=back_menu())

@dp.message(F.text == "📷 Загрузить фото и решить дз")
async def menu_photo(message: types.Message, state: FSMContext):
    await state.set_state(Mode.photo)
    await message.answer("Отправь фото с заданием (как ФОТО, не документ) 👇", reply_markup=back_menu())

@dp.message(F.text == "❓ Ответить на любой вопрос")
async def menu_any(message: types.Message, state: FSMContext):
    await state.set_state(Mode.any_question)
    await message.answer("Задай любой вопрос 👇", reply_markup=back_menu())

@dp.message(F.text == "💳 Подписка")
async def menu_sub(message: types.Message):
    await message.answer("Выбери тариф подписки:", reply_markup=sub_inline())

@dp.message(F.text == "➕ Докупить")
async def menu_topup(message: types.Message):
    await message.answer("Выбери пакет докупки:", reply_markup=topup_inline())

@dp.message(F.text == "🎁 Реферальная программа")
async def menu_ref(message: types.Message):
    await db.ensure_user(message.from_user.id)
    link = make_ref_link(message.from_user.id)
    await message.answer(
        f"Твоя реферальная ссылка:\n{link}\n\n"
        f"При оплате подписки/докупки приглашенным пользователем ты получаешь {settings.REF_PERCENT}% в ⭐ (учёт в базе).",
        reply_markup=main_menu()
    )


# -------- Callback -> invoice --------

@dp.callback_query(F.data.startswith("sub:"))
async def cb_sub(call: types.CallbackQuery):
    plan_key = call.data.split(":")[1]
    if plan_key not in PLANS:
        await call.answer("Неизвестный тариф", show_alert=True)
        return

    plan = PLANS[plan_key]
    prices = [LabeledPrice(label=plan["title"], amount=plan["price"])]

    # Stars invoices: currency="XTR"
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=plan["title"],
        description=f"{plan['daily']} запросов в сутки на 30 дней",
        payload=f"sub:{plan_key}",
        currency="XTR",
        prices=prices,
        provider_token="",  # для Stars можно пустой
    )
    await call.answer()

@dp.callback_query(F.data.startswith("topup:"))
async def cb_topup(call: types.CallbackQuery):
    key = call.data.split(":")[1]
    if key not in TOPUPS:
        await call.answer("Неизвестный пакет", show_alert=True)
        return

    pack = TOPUPS[key]
    prices = [LabeledPrice(label=pack["title"], amount=pack["price"])]

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=pack["title"],
        description=f"+{pack['credits']} запросов к нейросети",
        payload=f"topup:{key}",
        currency="XTR",
        prices=prices,
        provider_token="",
    )
    await call.answer()


# -------- Payments handlers --------

@dp.pre_checkout_query()
async def pre_checkout(pre: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    sp = message.successful_payment
    payload = sp.invoice_payload  # "sub:start" / "topup:10"
    amount = sp.total_amount      # Stars amount in XTR

    await db.ensure_user(message.from_user.id)

    tg_charge_id = getattr(sp, "telegram_payment_charge_id", None)
    provider_charge_id = getattr(sp, "provider_payment_charge_id", None)

    if payload.startswith("sub:"):
        plan_key = payload.split(":")[1]
        plan = PLANS.get(plan_key)
        if not plan:
            await message.answer("Оплата получена, но тариф не найден. Напиши администратору.")
            return

        await db.add_payment(message.from_user.id, f"sub_{plan_key}", amount, tg_charge_id, provider_charge_id)
        await db.set_subscription(message.from_user.id, plan_key, plan["daily"], days=30)

        # referral earning
        ref = await db.get_referrer(message.from_user.id)
        if ref and ref != message.from_user.id:
            bonus = int(amount * settings.REF_PERCENT / 100)
            if bonus > 0:
                await db.add_ref_earning(ref, message.from_user.id, bonus)

        await message.answer(
            f"✅ Подписка активирована: {plan['title']}\n"
            f"Лимит: {plan['daily']} запросов/день на 30 дней.",
            reply_markup=main_menu()
        )
        return

    if payload.startswith("topup:"):
        key = payload.split(":")[1]
        pack = TOPUPS.get(key)
        if not pack:
            await message.answer("Оплата получена, но пакет не найден. Напиши администратору.")
            return

        await db.add_payment(message.from_user.id, f"topup_{key}", amount, tg_charge_id, provider_charge_id)
        await db.add_topup(message.from_user.id, pack["credits"])

        ref = await db.get_referrer(message.from_user.id)
        if ref and ref != message.from_user.id:
            bonus = int(amount * settings.REF_PERCENT / 100)
            if bonus > 0:
                await db.add_ref_earning(ref, message.from_user.id, bonus)

        await message.answer(
            f"✅ Докупка прошла: +{pack['credits']} запросов добавлено.",
            reply_markup=main_menu()
        )
        return

    await message.answer("✅ Оплата получена.", reply_markup=main_menu())


# -------- Text handlers by state --------

@dp.message(Mode.homework)
async def homework_handler(message: types.Message):
    if not message.text:
        return
    if not await consume_or_block(message):
        return
    answer = await ask_deepseek(message.text, SYSTEM_HOMEWORK)
    await message.answer(answer)

@dp.message(Mode.any_question)
async def any_handler(message: types.Message):
    if not message.text:
        return
    if not await consume_or_block(message):
        return
    answer = await ask_deepseek(message.text, SYSTEM_GENERAL)
    await message.answer(answer)

@dp.message(Mode.photo, F.photo)
async def photo_handler(message: types.Message):
    if not await consume_or_block(message):
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    await bot.download_file(file.file_path, destination=tmp_path)

    text = image_to_text(tmp_path)
    try:
        os.remove(tmp_path)
    except:
        pass

    if not text:
        await message.answer("Не смог распознать текст. Попробуй фото четче/ближе.")
        return

    prompt = f"Текст с фото:\n\n{text}\n\nРеши задачу и объясни пошагово."
    answer = await ask_deepseek(prompt, SYSTEM_PHOTO)
    await message.answer(answer)

@dp.message(Mode.photo)
async def photo_need_photo(message: types.Message):
    await message.answer("Отправь именно фото (картинку) с заданием 👇")


# -------- Admin --------

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    users, active_subs, payments, revenue = await db.admin_stats()
    await message.answer(
        f"👑 Админка\n\n"
        f"Пользователей: {users}\n"
        f"Активных подписок: {active_subs}\n"
        f"Платежей: {payments}\n"
        f"Выручка (⭐): {revenue}\n\n"
        f"Команды:\n"
        f"/grant <user_id> <credits>",
        reply_markup=main_menu()
    )

@dp.message(Command("grant"))
async def admin_grant(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: /grant <user_id> <credits>")
        return
    try:
        uid = int(parts[1])
        credits = int(parts[2])
    except:
        await message.answer("Ошибка: user_id и credits должны быть числами.")
        return

    await db.ensure_user(uid)
    await db.add_topup(uid, credits)
    await message.answer(f"✅ Выдал пользователю {uid} +{credits} запросов.")


# -------- FastAPI lifecycle --------

@app.on_event("startup")
async def on_startup():
    await db.connect()
    await db.init()
    await bot.set_webhook(settings.WEBHOOK_URL)

@app.on_event("shutdown")
async def on_shutdown():
    await db.close()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "ok"}
