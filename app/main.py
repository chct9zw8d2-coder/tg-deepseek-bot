from __future__ import annotations

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import PreCheckoutQuery

from io import BytesIO
from datetime import datetime

from app.config import settings
from app.keyboards import main_menu, subscription_kb, topup_kb
from app.deepseek import answer_any_question, solve_homework_text, solve_homework_image
from app.ocr import extract_text
from app.db import init_db, SessionLocal
from app.dao import (
    get_or_create_user, set_mode, ensure_daily_reset,
    available_requests, consume_one_request, apply_subscription, add_bonus,
    record_payment, payment_exists, grant_referral_bonus_if_needed, subscription_active
)
from app.payments import PLANS, TOPUPS, CURRENCY, make_payload, prices_for_stars

app = FastAPI()
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def _ref_link(code: str) -> str:
    uname = settings.BOT_USERNAME or ""
    if uname.startswith("@"):
        uname = uname[1:]
    if not uname:
        # fallback: user can still copy code
        return f"Ссылка появится после указания BOT_USERNAME. Твой код: {code}"
    return f"https://t.me/{uname}?start=ref_{code}"

async def _db_user(message: Message, start_payload: str | None = None):
    tg_id = message.from_user.id
    username = message.from_user.username
    referred_by = None
    if start_payload and start_payload.startswith("ref_"):
        # referred by referral_code
        ref_code = start_payload[len("ref_"):]
        async with SessionLocal() as s:
            # resolve inviter by code
            from sqlalchemy import select
            from app.models import User
            q = await s.execute(select(User).where(User.referral_code == ref_code))
            inviter = q.scalar_one_or_none()
            if inviter and inviter.tg_id != tg_id:
                referred_by = inviter.tg_id

    is_admin = tg_id in settings.admin_ids
    async with SessionLocal() as s:
        user = await get_or_create_user(s, tg_id, username, referred_by=referred_by, is_admin=is_admin)
        user = await ensure_daily_reset(s, user)
    return user

async def _get_user(tg_id: int):
    from sqlalchemy import select
    from app.models import User
    async with SessionLocal() as s:
        q = await s.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one()
        user = await ensure_daily_reset(s, user)
        return user

async def _consume(tg_id: int) -> bool:
    from sqlalchemy import select
    from app.models import User
    async with SessionLocal() as s:
        q = await s.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one()
        ok = await consume_one_request(s, user)
        return ok

async def _set_mode(tg_id: int, mode: str):
    async with SessionLocal() as s:
        await set_mode(s, tg_id, mode)

async def _apply_sub(tg_id: int, plan_key: str, *, grant_ref_bonus: bool):
    from sqlalchemy import select
    from app.models import User
    async with SessionLocal() as s:
        q = await s.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one()
        had_any_sub_before = user.plan is not None or (user.sub_end is not None)
        await apply_subscription(s, user, plan_key)
        # referral bonus: only when first subscription ever
        if grant_ref_bonus and user.referred_by_tg_id and not had_any_sub_before:
            await grant_referral_bonus_if_needed(s, user)

async def _add_bonus(tg_id: int, amount: int):
    from sqlalchemy import select
    from app.models import User
    async with SessionLocal() as s:
        q = await s.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one()
        await add_bonus(s, user, amount)

async def _record_payment(tg_id: int, kind: str, stars: int, payload: str):
    async with SessionLocal() as s:
        await record_payment(s, tg_id, kind, stars, payload)

async def _payment_exists(payload: str) -> bool:
    async with SessionLocal() as s:
        return await payment_exists(s, payload)

@dp.message(CommandStart(deep_link=True))
async def start_handler(message: Message, command: CommandStart):
    payload = command.args
    await _db_user(message, start_payload=payload)
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=main_menu())

@dp.message(CommandStart())
async def start_handler_plain(message: Message):
    await _db_user(message)
    await message.answer("Привет! Выбери пункт меню 👇", reply_markup=main_menu())

@dp.message(F.text == "📚 Помощь с дз")
async def hw_mode(message: Message):
    await _db_user(message)
    await _set_mode(message.from_user.id, "hw")
    await message.answer("Отправь текст задания (или вопрос по ДЗ).", reply_markup=main_menu())

@dp.message(F.text == "📷 Загрузить фото и решить дз")
async def photo_mode(message: Message):
    await _db_user(message)
    await _set_mode(message.from_user.id, "photo")
    await message.answer("Отправь фото задания (одно фото).", reply_markup=main_menu())

@dp.message(F.text == "❓ Ответить на любой вопрос")
async def any_mode(message: Message):
    await _db_user(message)
    await _set_mode(message.from_user.id, "any")
    await message.answer("Задай любой вопрос текстом.", reply_markup=main_menu())

@dp.message(F.text == "💳 Подписка")
async def subscription_menu(message: Message):
    await _db_user(message)
    await message.answer("Выбери тариф 👇", reply_markup=subscription_kb())

@dp.message(F.text == "➕ Докупить")
async def topup_menu(message: Message):
    await _db_user(message)
    await message.answer("Выбери пакет 👇", reply_markup=topup_kb())

@dp.message(F.text == "👥 Реферальная программа")
async def referral_menu(message: Message):
    user = await _db_user(message)
    link = _ref_link(user.referral_code)
    txt = (
        "Приглашай друзей по ссылке ниже.\n"
        f"Если приглашённый купит подписку — ты получишь +{settings.REF_BONUS_REQUESTS} запросов.\n\n"
        f"Твоя ссылка: {link}"
    )
    await message.answer(txt, reply_markup=main_menu())

@dp.callback_query(F.data.startswith("buy:"))
async def buy_callback(cb: CallbackQuery):
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) != 3:
        return
    kind, item = parts[1], parts[2]
    tg_id = cb.from_user.id
    await _db_user(cb.message)  # ensure exists

    if kind == "sub":
        plan = PLANS[item]
        payload = make_payload(f"sub_{item}")
        await bot.send_invoice(
            chat_id=tg_id,
            title=plan.title,
            description=f"{plan.daily_limit} запросов в сутки на {plan.days} дней",
            payload=payload,
            currency=CURRENCY,
            prices=prices_for_stars(plan.stars),
            provider_token=""  # Stars
        )
    elif kind == "topup":
        pkg = TOPUPS[item]
        payload = make_payload(f"topup_{item}")
        await bot.send_invoice(
            chat_id=tg_id,
            title=pkg["title"],
            description=f"{pkg['amount']} дополнительных запросов",
            payload=payload,
            currency=CURRENCY,
            prices=prices_for_stars(pkg["stars"]),
            provider_token=""
        )

@dp.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    # Always approve. Telegram will handle correctness of prices/currency.
    await bot.answer_pre_checkout_query(pre.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    sp = message.successful_payment
    payload = sp.invoice_payload

    # idempotency
    if await _payment_exists(payload):
        await message.answer("Платёж уже обработан ✅", reply_markup=main_menu())
        return

    tg_id = message.from_user.id

    # Stars paid
    stars = sp.total_amount  # XTR -> stars units

    if payload.startswith("sub_"):
        plan_key = payload.split("_", 1)[1].split(":", 1)[0] if ":" in payload else payload.split("_", 1)[1]
        # payload is like sub_start:uuid
        plan_key = payload.split(":")[0].split("_", 1)[1]
        await _record_payment(tg_id, f"sub_{plan_key}", stars, payload)
        await _apply_sub(tg_id, plan_key, grant_ref_bonus=True)
        plan = PLANS[plan_key]
        await message.answer(
            f"Подписка активирована ✅\n\nТариф: {plan.key}\nЛимит: {plan.daily_limit}/день\nСрок: 30 дней",
            reply_markup=main_menu()
        )
        return

    if payload.startswith("topup_"):
        key = payload.split(":")[0].split("_", 1)[1]
        pkg = TOPUPS[key]
        await _record_payment(tg_id, f"topup_{key}", stars, payload)
        await _add_bonus(tg_id, pkg["amount"])
        await message.answer(
            f"Готово ✅ Добавлено {pkg['amount']} запросов.",
            reply_markup=main_menu()
        )
        return

    await _record_payment(tg_id, "unknown", stars, payload)
    await message.answer("Платёж получен ✅", reply_markup=main_menu())

def _quota_text(user) -> str:
    sub_active = subscription_active(user)
    sub_rem = max(user.daily_limit - user.used_today, 0) if sub_active else 0
    return (
        f"Доступно запросов: {available_requests(user)}\n"
        f"Подписка: {'активна' if sub_active else 'нет'}\n"
        f"Лимит по подписке сегодня: {sub_rem}\n"
        f"Бонус-запросы: {user.bonus_requests}"
    )

@dp.message(Command("admin"))
async def admin_help(message: Message):
    user = await _db_user(message)
    if not user.is_admin:
        return
    await message.answer(
        "Админ-команды:\n"
        "/quota <user_id> — квота пользователя\n"
        "/grant <user_id> <n> — начислить бонусы\n",
        reply_markup=main_menu()
    )

@dp.message(Command("quota"))
async def admin_quota(message: Message):
    me = await _db_user(message)
    if not me.is_admin:
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /quota <user_id>")
        return
    uid = int(parts[1])
    user = await _get_user(uid)
    await message.answer(_quota_text(user))

@dp.message(Command("grant"))
async def admin_grant(message: Message):
    me = await _db_user(message)
    if not me.is_admin:
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: /grant <user_id> <n>")
        return
    uid = int(parts[1])
    n = int(parts[2])
    await _add_bonus(uid, n)
    user = await _get_user(uid)
    await message.answer(f"Начислено ✅\n\n{_quota_text(user)}")

@dp.message(F.photo)
async def handle_photo(message: Message):
    user = await _db_user(message)
    if user.mode != "photo":
        await message.answer("Выбери режим: 📷 Загрузить фото и решить дз", reply_markup=main_menu())
        return

    if not await _consume(message.from_user.id):
        await message.answer("Лимит запросов закончился 😕\n\nОформи подписку или докупи запросы.", reply_markup=main_menu())
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    buf = BytesIO()
    await bot.download_file(file.file_path, buf)
    image_bytes = buf.getvalue()

    ocr_text = extract_text(image_bytes)
    if not ocr_text:
        await message.answer("Не смог распознать текст на фото. Попробуй сделать фото ближе/четче.", reply_markup=main_menu())
        return

    answer = await solve_homework_image(image_bytes, ocr_text)
    await message.answer(answer, reply_markup=main_menu())

@dp.message(F.text)
async def handle_text(message: Message):
    if not message.text or message.text.startswith("/"):
        return

    user = await _db_user(message)

    if not await _consume(message.from_user.id):
        await message.answer("Лимит запросов закончился 😕\n\nОформи подписку или докупи запросы.", reply_markup=main_menu())
        return

    if user.mode == "hw":
        answer = await solve_homework_text(message.text)
    else:
        # default any
        answer = await answer_any_question(message.text)

    await message.answer(answer, reply_markup=main_menu())

@app.on_event("startup")
async def startup():
    await init_db()
    await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
