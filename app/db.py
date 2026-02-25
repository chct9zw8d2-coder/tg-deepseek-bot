import asyncpg
from datetime import datetime, timedelta, date
from typing import Optional, Tuple


class DB:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        # Railway иногда даёт SQLAlchemy-style URL: postgresql+asyncpg://...
        dsn = (self.dsn or "").strip()
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        dsn = dsn.replace("postgres+asyncpg://", "postgres://")

        self.pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def init(self):
        assert self.pool
        async with self.pool.acquire() as con:
            await con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                referrer_id BIGINT
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id BIGINT PRIMARY KEY,
                plan TEXT NOT NULL,
                daily_limit INT NOT NULL,
                start_at TIMESTAMP NOT NULL,
                end_at TIMESTAMP NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usage_daily (
                user_id BIGINT NOT NULL,
                day DATE NOT NULL,
                used INT NOT NULL DEFAULT 0,
                PRIMARY KEY(user_id, day)
            );

            CREATE TABLE IF NOT EXISTS topups (
                user_id BIGINT PRIMARY KEY,
                remaining INT NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                kind TEXT NOT NULL,
                amount_xtr INT NOT NULL,
                tg_charge_id TEXT,
                provider_charge_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS ref_earnings (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                from_user_id BIGINT NOT NULL,
                amount_xtr INT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """)

    # ---------- users / referral ----------
    async def ensure_user(self, user_id: int, referrer_id: Optional[int] = None):
        assert self.pool
        async with self.pool.acquire() as con:
            row = await con.fetchrow("SELECT id, referrer_id FROM users WHERE id=$1", user_id)
            if row is None:
                await con.execute("INSERT INTO users(id, referrer_id) VALUES($1, $2)", user_id, referrer_id)
                await con.execute(
                    "INSERT INTO topups(user_id, remaining) VALUES($1, 0) ON CONFLICT DO NOTHING",
                    user_id
                )
            else:
                if referrer_id and row["referrer_id"] is None and referrer_id != user_id:
                    await con.execute("UPDATE users SET referrer_id=$2 WHERE id=$1", user_id, referrer_id)

    async def get_referrer(self, user_id: int) -> Optional[int]:
        assert self.pool
        async with self.pool.acquire() as con:
            row = await con.fetchrow("SELECT referrer_id FROM users WHERE id=$1", user_id)
            return row["referrer_id"] if row else None

    # ---------- subscriptions ----------
    async def set_subscription(self, user_id: int, plan: str, daily_limit: int, days: int = 30):
        assert self.pool
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO subscriptions(user_id, plan, daily_limit, start_at, end_at)
                VALUES($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE SET
                  plan=EXCLUDED.plan,
                  daily_limit=EXCLUDED.daily_limit,
                  start_at=EXCLUDED.start_at,
                  end_at=EXCLUDED.end_at
            """, user_id, plan, daily_limit, now, end)

    async def get_active_subscription(self, user_id: int) -> Optional[Tuple[str, int, datetime]]:
        assert self.pool
        async with self.pool.acquire() as con:
            row = await con.fetchrow("""
                SELECT plan, daily_limit, end_at
                FROM subscriptions
                WHERE user_id=$1 AND end_at > NOW()
            """, user_id)
            if not row:
                return None
            return row["plan"], row["daily_limit"], row["end_at"]

    # ---------- topups ----------
    async def add_topup(self, user_id: int, credits: int):
        assert self.pool
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO topups(user_id, remaining) VALUES($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET remaining = topups.remaining + $2
            """, user_id, credits)

    async def get_topup_remaining(self, user_id: int) -> int:
        assert self.pool
        async with self.pool.acquire() as con:
            row = await con.fetchrow("SELECT remaining FROM topups WHERE user_id=$1", user_id)
            return int(row["remaining"]) if row else 0

    # ---------- daily usage ----------
    async def _get_used_today(self, con, user_id: int, day: date) -> int:
        row = await con.fetchrow("SELECT used FROM usage_daily WHERE user_id=$1 AND day=$2", user_id, day)
        return int(row["used"]) if row else 0

    async def consume_request(self, user_id: int, is_admin: bool) -> Tuple[bool, str]:
        """
        Списывает 1 запрос. Возвращает (ok, message).

        Логика:
        - админ: всегда ok
        - если есть подписка: тратим дневной лимит
        - иначе/если лимит кончился: тратим topups.remaining
        """
        if is_admin:
            return True, "admin"

        assert self.pool
        today = datetime.utcnow().date()

        async with self.pool.acquire() as con:
            sub = await con.fetchrow("""
                SELECT daily_limit, end_at FROM subscriptions
                WHERE user_id=$1 AND end_at > NOW()
            """, user_id)

            used_today = await self._get_used_today(con, user_id, today)

            if sub:
                daily_limit = int(sub["daily_limit"])
                if used_today < daily_limit:
                    await con.execute("""
                        INSERT INTO usage_daily(user_id, day, used) VALUES($1, $2, 1)
                        ON CONFLICT (user_id, day) DO UPDATE SET used = usage_daily.used + 1
                    """, user_id, today)
                    return True, f"sub:{used_today+1}/{daily_limit}"

            # fallback to topups
            row = await con.fetchrow("SELECT remaining FROM topups WHERE user_id=$1", user_id)
            remaining = int(row["remaining"]) if row else 0
            if remaining > 0:
                await con.execute("UPDATE topups SET remaining = remaining - 1 WHERE user_id=$1", user_id)
                return True, f"topup:{remaining-1} left"

            return False, "no_quota"

    # ---------- payments + referral earnings ----------
    async def add_payment(
        self,
        user_id: int,
        kind: str,
        amount_xtr: int,
        tg_charge_id: str = None,
        provider_charge_id: str = None
    ):
        assert self.pool
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO payments(user_id, kind, amount_xtr, tg_charge_id, provider_charge_id)
                VALUES($1, $2, $3, $4, $5)
            """, user_id, kind, amount_xtr, tg_charge_id, provider_charge_id)

    async def add_ref_earning(self, referrer_id: int, from_user_id: int, amount_xtr: int):
        assert self.pool
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO ref_earnings(referrer_id, from_user_id, amount_xtr)
                VALUES($1, $2, $3)
            """, referrer_id, from_user_id, amount_xtr)

    async def admin_stats(self):
        assert self.pool
        async with self.pool.acquire() as con:
            users = await con.fetchval("SELECT COUNT(*) FROM users")
            active_subs = await con.fetchval("SELECT COUNT(*) FROM subscriptions WHERE end_at > NOW()")
            payments = await con.fetchval("SELECT COUNT(*) FROM payments")
            revenue = await con.fetchval("SELECT COALESCE(SUM(amount_xtr),0) FROM payments")
            return users, active_subs, payments, revenue
