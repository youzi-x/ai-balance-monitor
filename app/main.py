from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.config import settings
from app.db import SessionLocal, ensure_schema, get_session
from app.models import CheckLog, Site
from app.schemas import (
    CheckLogResponse,
    SitePayload,
    SiteResponse,
    SiteUpdatePayload,
    TelegramSettingsPayload,
    TelegramSettingsResponse,
)
from app.services.monitor import check_all_sites, check_due_sites, check_site
from app.services.settings_store import (
    ensure_settings,
    get_telegram_settings,
    update_telegram_settings,
)
from app.services.telegram import send_telegram_message


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
security = HTTPBasic()
scheduler = AsyncIOScheduler(timezone="UTC")


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username_ok = secrets.compare_digest(credentials.username, settings.admin_username)
    password_ok = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    with SessionLocal() as session:
        ensure_settings(session)
    scheduler.add_job(
        check_due_sites,
        trigger="interval",
        seconds=30,
        id="balance-checker",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("AI Balance Monitor started")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="AI Balance Monitor",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def serialize_site(site: Site) -> SiteResponse:
    return SiteResponse(
        id=site.id,
        name=site.name,
        site_type=site.site_type,
        base_url=site.base_url,
        api_token_masked=mask_secret(site.api_token),
        endpoint_path=site.endpoint_path,
        auth_mode=site.auth_mode,
        auth_header_name=site.auth_header_name,
        auth_prefix=site.auth_prefix,
        extra_headers=site.extra_headers,
        balance_path=site.balance_path,
        quota_divisor=site.quota_divisor,
        currency=site.currency,
        low_balance_threshold=site.low_balance_threshold,
        check_interval_seconds=site.check_interval_seconds,
        enabled=site.enabled,
        last_balance=site.last_balance,
        last_checked_at=site.last_checked_at,
        last_status=site.last_status,
        last_error=site.last_error,
        consecutive_failures=site.consecutive_failures,
        created_at=site.created_at,
    )


def site_defaults(payload: SitePayload | SiteUpdatePayload) -> dict:
    adapter = get_adapter(payload.site_type)
    if payload.auth_mode == "api_key":
        default_header = "x-api-key"
        default_prefix = ""
    elif payload.auth_mode == "bearer":
        default_header = "Authorization"
        default_prefix = "Bearer"
    else:
        default_header = adapter.default_auth_header_name
        default_prefix = ""

    auth_prefix = payload.auth_prefix.strip() if payload.auth_prefix is not None else ""
    return {
        "name": payload.name.strip(),
        "site_type": payload.site_type,
        "base_url": str(payload.base_url).rstrip("/"),
        "endpoint_path": payload.endpoint_path or adapter.default_endpoint_path,
        "auth_mode": payload.auth_mode or adapter.default_auth_mode,
        "auth_header_name": payload.auth_header_name or default_header,
        "auth_prefix": auth_prefix or default_prefix,
        "extra_headers": payload.extra_headers.strip(),
        "balance_path": payload.balance_path.strip(),
        "quota_divisor": payload.quota_divisor or adapter.default_quota_divisor,
        "currency": payload.currency.upper().strip(),
        "low_balance_threshold": payload.low_balance_threshold,
        "check_interval_seconds": payload.check_interval_seconds,
        "enabled": payload.enabled,
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _admin: str = Depends(require_admin)):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/summary")
async def summary(
    _admin: str = Depends(require_admin), session: Session = Depends(get_session)
) -> dict:
    sites = session.scalars(select(Site)).all()
    return {
        "total_sites": len(sites),
        "enabled_sites": sum(site.enabled for site in sites),
        "healthy_sites": sum(site.last_status == "ok" for site in sites),
        "alerting_sites": sum(site.low_balance_alerted for site in sites),
        "error_sites": sum(site.last_status == "error" for site in sites),
    }


@app.get("/api/sites", response_model=list[SiteResponse])
async def list_sites(
    _admin: str = Depends(require_admin), session: Session = Depends(get_session)
):
    sites = session.scalars(select(Site).order_by(Site.name.asc())).all()
    return [serialize_site(site) for site in sites]


@app.post("/api/sites", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site(
    payload: SitePayload,
    _admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    values = site_defaults(payload)
    site = Site(api_token=payload.api_token.strip(), **values)
    session.add(site)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="A site with this name already exists")
    session.refresh(site)
    return serialize_site(site)


@app.put("/api/sites/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: int,
    payload: SiteUpdatePayload,
    _admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    site = session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    values = site_defaults(payload)
    for key, value in values.items():
        setattr(site, key, value)
    if payload.api_token.strip():
        site.api_token = payload.api_token.strip()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="A site with this name already exists")
    session.refresh(site)
    return serialize_site(site)


@app.delete("/api/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: int,
    _admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    site = session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    session.delete(site)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/sites/{site_id}/check")
async def check_one_site(
    site_id: int, _admin: str = Depends(require_admin), session: Session = Depends(get_session)
) -> dict:
    if session.get(Site, site_id) is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return await check_site(site_id, forced=True)


@app.post("/api/check-all")
async def check_all(_admin: str = Depends(require_admin)) -> dict:
    results = await check_all_sites()
    return {"checked": len(results), "results": results}


@app.get("/api/sites/{site_id}/logs", response_model=list[CheckLogResponse])
async def list_check_logs(
    site_id: int,
    limit: int = 30,
    _admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    if session.get(Site, site_id) is None:
        raise HTTPException(status_code=404, detail="Site not found")
    limit = max(1, min(limit, 200))
    logs = session.scalars(
        select(CheckLog)
        .where(CheckLog.site_id == site_id)
        .order_by(CheckLog.checked_at.desc())
        .limit(limit)
    ).all()
    return logs


@app.get("/api/telegram", response_model=TelegramSettingsResponse)
async def telegram_settings(
    _admin: str = Depends(require_admin), session: Session = Depends(get_session)
):
    config = get_telegram_settings(session)
    return TelegramSettingsResponse(
        enabled=bool(config["enabled"]),
        bot_token_masked=mask_secret(str(config["bot_token"])),
        chat_id=str(config["chat_id"]),
    )


@app.put("/api/telegram", response_model=TelegramSettingsResponse)
async def save_telegram_settings(
    payload: TelegramSettingsPayload,
    _admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    if payload.enabled and (not payload.chat_id.strip()):
        raise HTTPException(status_code=422, detail="Telegram chat ID is required when enabled")
    config = update_telegram_settings(
        session,
        enabled=payload.enabled,
        bot_token=payload.bot_token,
        chat_id=payload.chat_id,
    )
    if config["enabled"] and not config["bot_token"]:
        raise HTTPException(status_code=422, detail="Telegram bot token is required when enabled")
    return TelegramSettingsResponse(
        enabled=bool(config["enabled"]),
        bot_token_masked=mask_secret(str(config["bot_token"])),
        chat_id=str(config["chat_id"]),
    )


@app.post("/api/telegram/test")
async def test_telegram(
    _admin: str = Depends(require_admin), session: Session = Depends(get_session)
) -> dict:
    config = get_telegram_settings(session)
    try:
        await send_telegram_message(config, "[AI Balance Monitor] Telegram connection test succeeded.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "sent"}
