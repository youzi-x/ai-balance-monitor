from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    site_type: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_token: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_path: Mapped[str] = mapped_column(String(300), nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="bearer")
    auth_header_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Authorization")
    auth_prefix: Mapped[str] = mapped_column(String(100), nullable=False, default="Bearer")
    extra_headers: Mapped[str] = mapped_column(Text, nullable=False, default="")
    balance_path: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    quota_divisor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    currency: Mapped[str] = mapped_column(String(12), nullable=False, default="USD")
    low_balance_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    check_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    low_balance_alerted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), nullable=False, default="never")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    checks: Mapped[list["CheckLog"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )


class CheckLog(Base):
    __tablename__ = "check_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped[Site] = relationship(back_populates="checks")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
