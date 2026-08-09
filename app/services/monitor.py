from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.adapters import get_adapter
from app.config import settings
from app.db import SessionLocal
from app.models import CheckLog, Site
from app.services.settings_store import get_telegram_settings
from app.services.telegram import send_telegram_message


logger = logging.getLogger(__name__)


def format_balance(value: float, currency: str) -> str:
    return f"{value:,.4f}".rstrip("0").rstrip(".") + f" {currency}"


async def check_site(site_id: int, *, forced: bool = False) -> dict:
    with SessionLocal() as session:
        site = session.get(Site, site_id)
        if site is None:
            raise ValueError("Site not found")
        if not site.enabled and not forced:
            return {"site_id": site_id, "skipped": True}

        adapter = get_adapter(site.site_type)
        try:
            result = await adapter.fetch_balance(site)
        except Exception as exc:
            message = str(exc)
            site.last_status = "error"
            site.last_error = message
            site.last_checked_at = datetime.utcnow()
            site.consecutive_failures += 1
            _add_log(session, site, "error", None, message)
            should_notify = site.consecutive_failures == 3
            session.commit()

            if should_notify:
                await _notify(
                    f"[AI Balance Monitor] Check failed\n"
                    f"Site: {site.name}\n"
                    f"Type: {site.site_type}\n"
                    f"Error: {message}"
                )
            return {"site_id": site.id, "status": "error", "error": message}

        site.last_balance = result.balance
        site.last_checked_at = datetime.utcnow()
        site.last_status = "ok"
        site.last_error = None
        site.consecutive_failures = 0
        _add_log(session, site, "ok", result.balance, None)

        below_threshold = (
            site.low_balance_threshold > 0 and result.balance <= site.low_balance_threshold
        )
        should_notify_low_balance = below_threshold and not site.low_balance_alerted
        site.low_balance_alerted = below_threshold
        session.commit()

        if should_notify_low_balance:
            await _notify(
                f"[AI Balance Monitor] Low balance alert\n"
                f"Site: {site.name}\n"
                f"Type: {site.site_type}\n"
                f"Balance: {format_balance(result.balance, result.currency)}\n"
                f"Threshold: {format_balance(site.low_balance_threshold, result.currency)}"
            )
        return {
            "site_id": site.id,
            "status": "ok",
            "balance": result.balance,
            "currency": result.currency,
        }


async def check_due_sites() -> list[dict]:
    with SessionLocal() as session:
        sites = session.scalars(select(Site).where(Site.enabled.is_(True))).all()
        now = datetime.utcnow()
        due_ids = [
            site.id
            for site in sites
            if site.last_checked_at is None
            or now - site.last_checked_at
            >= timedelta(
                seconds=site.check_interval_seconds or settings.default_check_interval_seconds
            )
        ]

    if not due_ids:
        return []
    return await asyncio.gather(*(check_site(site_id) for site_id in due_ids))


async def check_all_sites() -> list[dict]:
    with SessionLocal() as session:
        site_ids = session.scalars(select(Site.id).where(Site.enabled.is_(True))).all()
    if not site_ids:
        return []
    return await asyncio.gather(*(check_site(site_id, forced=True) for site_id in site_ids))


def _add_log(
    session, site: Site, status: str, balance: float | None, message: str | None
) -> None:
    session.add(
        CheckLog(
            site_id=site.id,
            checked_at=datetime.utcnow(),
            status=status,
            balance=balance,
            message=message,
        )
    )
    old_logs = session.scalars(
        select(CheckLog)
        .where(CheckLog.site_id == site.id)
        .order_by(CheckLog.id.desc())
        .offset(200)
    ).all()
    for log in old_logs:
        session.delete(log)


async def _notify(text: str) -> None:
    try:
        with SessionLocal() as session:
            telegram = get_telegram_settings(session)
        await send_telegram_message(telegram, text)
    except Exception:
        logger.exception("Failed to send Telegram notification")
