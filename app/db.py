
import os
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

_pool: Optional[asyncpg.Pool] = None

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

async def init_db() -> asyncpg.Pool:
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set (Railway Postgres).")
    if _pool:
        return _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              user_id BIGINT PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              referrer_id BIGINT NULL,

              subscription_plan TEXT NULL,
              sub_start DATE NULL,
              sub_end DATE NULL,
              daily_limit INT NOT NULL DEFAULT 0,
              used_today INT NOT NULL DEFAULT 0,
              last_reset DATE NULL,

              extra_credits INT NOT NULL DEFAULT 0,

              ref_balance_stars INT NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS payments (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              currency TEXT NOT NULL,
              amount INT NOT NULL,
              payload TEXT NOT NULL,
              telegram_charge_id TEXT NULL,
              provider_charge_id TEXT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);
            CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
            """
        )
    return _pool

async def get_user(user_id: int) -> Optional[asyncpg.Record]:
    assert _pool
    return await _pool.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def upsert_user(user_id: int, referrer_id: Optional[int] = None) -> None:
    assert _pool
    # Only set referrer_id at first insert (or if it's NULL)
    await _pool.execute(
        """
        INSERT INTO users(user_id, referrer_id, last_reset)
        VALUES($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE
        SET referrer_id = COALESCE(users.referrer_id, EXCLUDED.referrer_id)
        """,
        user_id,
        referrer_id,
        date.today(),
    )

def _subscription_active(row: asyncpg.Record) -> bool:
    if not row:
        return False
    end = row["sub_end"]
    return bool(end and end >= date.today())

async def ensure_daily_reset(user_id: int) -> None:
    """Resets used_today if day changed."""
    assert _pool
    row = await get_user(user_id)
    if not row:
        return
    today = date.today()
    last = row["last_reset"]
    if last != today:
        await _pool.execute(
            "UPDATE users SET used_today=0, last_reset=$2 WHERE user_id=$1",
            user_id,
            today,
        )

async def get_limits(user_id: int) -> Dict[str, Any]:
    """Returns current available requests and flags."""
    assert _pool
    await ensure_daily_reset(user_id)
    row = await get_user(user_id)
    if not row:
        return {"active": False, "daily_limit": 0, "used_today": 0, "extra_credits": 0}

    active = _subscription_active(row)
    daily_limit = row["daily_limit"] if active else 0
    used_today = row["used_today"] or 0
    extra_credits = row["extra_credits"] or 0
    daily_remaining = max(daily_limit - used_today, 0)
    total_available = daily_remaining + extra_credits
    return {
        "active": active,
        "daily_limit": daily_limit,
        "used_today": used_today,
        "daily_remaining": daily_remaining,
        "extra_credits": extra_credits,
        "total_available": total_available,
        "sub_end": row["sub_end"],
        "plan": row["subscription_plan"],
        "referrer_id": row["referrer_id"],
        "ref_balance_stars": row["ref_balance_stars"],
    }

async def consume_request(user_id: int) -> bool:
    """Consumes 1 request from daily_remaining first, then extra_credits. Returns True if consumed."""
    assert _pool
    await ensure_daily_reset(user_id)
    row = await get_user(user_id)
    if not row:
        return False
    active = _subscription_active(row)
    today_used = row["used_today"] or 0
    extra = row["extra_credits"] or 0
    daily_limit = row["daily_limit"] if active else 0

    if active and today_used < daily_limit:
        await _pool.execute(
            "UPDATE users SET used_today=used_today+1 WHERE user_id=$1",
            user_id,
        )
        return True
    if extra > 0:
        await _pool.execute(
            "UPDATE users SET extra_credits=extra_credits-1 WHERE user_id=$1",
            user_id,
        )
        return True
    return False

async def activate_subscription(user_id: int, plan: str, daily_limit: int, days: int = 30) -> None:
    assert _pool
    start = date.today()
    end = start + timedelta(days=days)
    await _pool.execute(
        """
        UPDATE users
        SET subscription_plan=$2, sub_start=$3, sub_end=$4,
            daily_limit=$5, used_today=0, last_reset=$3
        WHERE user_id=$1
        """,
        user_id, plan, start, end, daily_limit
    )

async def add_credits(user_id: int, credits: int) -> None:
    assert _pool
    await _pool.execute(
        "UPDATE users SET extra_credits=extra_credits+$2 WHERE user_id=$1",
        user_id, credits
    )

async def add_ref_balance(referrer_id: int, stars: int) -> None:
    assert _pool
    await _pool.execute(
        "UPDATE users SET ref_balance_stars=ref_balance_stars+$2 WHERE user_id=$1",
        referrer_id, stars
    )

async def count_referrals(referrer_id: int) -> int:
    assert _pool
    return await _pool.fetchval("SELECT COUNT(*) FROM users WHERE referrer_id=$1", referrer_id)

async def log_payment(
    user_id: int, currency: str, amount: int, payload: str,
    telegram_charge_id: str | None, provider_charge_id: str | None
) -> None:
    assert _pool
    await _pool.execute(
        """
        INSERT INTO payments(user_id, currency, amount, payload, telegram_charge_id, provider_charge_id)
        VALUES($1,$2,$3,$4,$5,$6)
        """,
        user_id, currency, amount, payload, telegram_charge_id, provider_charge_id
    )

async def admin_stats() -> Dict[str, Any]:
    assert _pool
    users = await _pool.fetchval("SELECT COUNT(*) FROM users")
    active = await _pool.fetchval("SELECT COUNT(*) FROM users WHERE sub_end IS NOT NULL AND sub_end >= CURRENT_DATE")
    revenue = await _pool.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE currency='XTR'")
    payments = await _pool.fetchval("SELECT COUNT(*) FROM payments")
    return {"users": users, "active_subscriptions": active, "revenue_xtr": revenue, "payments": payments}
