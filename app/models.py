from __future__ import annotations
from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    referred_by_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # usage
    used_today: Mapped[int] = mapped_column(Integer, default=0)
    used_date: Mapped[date | None] = mapped_column(DateTime(timezone=False), nullable=True)  # store date as dt at midnight
    bonus_requests: Mapped[int] = mapped_column(Integer, default=0)

    # subscription
    plan: Mapped[str | None] = mapped_column(String(32), nullable=True)  # start/pro/premium
    sub_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    daily_limit: Mapped[int] = mapped_column(Integer, default=0)

    # UX
    mode: Mapped[str] = mapped_column(String(16), default="any")  # any/hw/photo

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(32))   # sub_start/sub_pro/sub_premium/topup_10/topup_50
    stars: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
