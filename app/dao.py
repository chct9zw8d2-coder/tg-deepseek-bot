from __future__ import annotations
from datetime import datetime, timedelta, date
import secrets
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Payment
from app.config import settings

def _today_utc_date() -> date:
    return datetime.utcnow().date()

def _date_to_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)

async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, *, referred_by: int | None = None, is_admin: bool = False) -> User:
    q = await session.execute(select(User).where(User.tg_id == tg_id))
    user = q.scalar_one_or_none()
    if user:
        # update username/admin flag
        user.username = username
        if is_admin:
            user.is_admin = True
        user.updated_at = datetime.utcnow()
        await session.commit()
        return user

    referral_code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    user = User(
        tg_id=tg_id,
        username=username,
        referral_code=referral_code,
        referred_by_tg_id=referred_by,
        is_admin=is_admin,
        mode="any",
        used_today=0,
        used_date=_date_to_dt(_today_utc_date()),
        bonus_requests=0,
        daily_limit=0
    )
    session.add(user)
    await session.commit()
    return user

async def set_mode(session: AsyncSession, tg_id: int, mode: str) -> None:
    q = await session.execute(select(User).where(User.tg_id == tg_id))
    user = q.scalar_one()
    user.mode = mode
    user.updated_at = datetime.utcnow()
    await session.commit()

async def ensure_daily_reset(session: AsyncSession, user: User) -> User:
    today = _today_utc_date()
    stored = (user.used_date.date() if user.used_date else None)
    if stored != today:
        user.used_today = 0
        user.used_date = _date_to_dt(today)
        user.updated_at = datetime.utcnow()
        await session.commit()
    return user

def subscription_active(user: User) -> bool:
    return bool(user.sub_end and user.sub_end >= datetime.utcnow())

def available_requests(user: User) -> int:
    if user.is_admin:
        return 10**9
    remaining_sub = 0
    if subscription_active(user):
        remaining_sub = max(user.daily_limit - user.used_today, 0)
    return remaining_sub + max(user.bonus_requests, 0)

async def consume_one_request(session: AsyncSession, user: User) -> bool:
    if user.is_admin:
        return True

    await ensure_daily_reset(session, user)

    if subscription_active(user) and user.used_today < user.daily_limit:
        user.used_today += 1
        user.updated_at = datetime.utcnow()
        await session.commit()
        return True

    if user.bonus_requests > 0:
        user.bonus_requests -= 1
        user.updated_at = datetime.utcnow()
        await session.commit()
        return True

    return False

async def apply_subscription(session: AsyncSession, user: User, plan_key: str) -> None:
    from app.payments import PLANS
    plan = PLANS[plan_key]
    now = datetime.utcnow()
    # If user already has active subscription, extend from current end; else from now
    start_from = user.sub_end if user.sub_end and user.sub_end > now else now
    user.plan = plan.key
    user.daily_limit = plan.daily_limit
    user.sub_end = start_from + timedelta(days=plan.days)
    user.updated_at = now
    await session.commit()

async def add_bonus(session: AsyncSession, user: User, amount: int) -> None:
    user.bonus_requests += amount
    user.updated_at = datetime.utcnow()
    await session.commit()

async def record_payment(session: AsyncSession, tg_id: int, kind: str, stars: int, payload: str) -> None:
    session.add(Payment(tg_id=tg_id, kind=kind, stars=stars, payload=payload))
    await session.commit()

async def payment_exists(session: AsyncSession, payload: str) -> bool:
    q = await session.execute(select(Payment).where(Payment.payload == payload))
    return q.scalar_one_or_none() is not None

async def grant_referral_bonus_if_needed(session: AsyncSession, buyer: User) -> None:
    if not buyer.referred_by_tg_id:
        return
    # bonus only once per buyer: when they first purchase any subscription
    # We'll check if buyer already had a plan before purchase is recorded (handled in main logic by calling once)
    q = await session.execute(select(User).where(User.tg_id == buyer.referred_by_tg_id))
    inviter = q.scalar_one_or_none()
    if not inviter:
        return
    inviter.bonus_requests += settings.REF_BONUS_REQUESTS
    inviter.updated_at = datetime.utcnow()
    await session.commit()
