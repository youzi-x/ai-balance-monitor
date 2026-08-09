from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppSetting


TELEGRAM_ENABLED = "telegram_enabled"
TELEGRAM_BOT_TOKEN = "telegram_bot_token"
TELEGRAM_CHAT_ID = "telegram_chat_id"


def ensure_settings(session: Session) -> None:
    defaults = {
        TELEGRAM_ENABLED: "true" if settings.telegram_enabled else "false",
        TELEGRAM_BOT_TOKEN: settings.telegram_bot_token,
        TELEGRAM_CHAT_ID: settings.telegram_chat_id,
    }
    for key, value in defaults.items():
        if session.get(AppSetting, key) is None:
            session.add(AppSetting(key=key, value=value))
    session.commit()


def get_telegram_settings(session: Session) -> dict[str, str | bool]:
    values = {
        item.key: item.value
        for item in session.query(AppSetting)
        .filter(AppSetting.key.in_([TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]))
        .all()
    }
    return {
        "enabled": values.get(TELEGRAM_ENABLED, "false").lower() == "true",
        "bot_token": values.get(TELEGRAM_BOT_TOKEN, ""),
        "chat_id": values.get(TELEGRAM_CHAT_ID, ""),
    }


def update_telegram_settings(
    session: Session, *, enabled: bool, bot_token: str, chat_id: str
) -> dict[str, str | bool]:
    current = get_telegram_settings(session)
    updates = {
        TELEGRAM_ENABLED: "true" if enabled else "false",
        TELEGRAM_BOT_TOKEN: bot_token.strip() or str(current["bot_token"]),
        TELEGRAM_CHAT_ID: chat_id.strip(),
    }
    for key, value in updates.items():
        item = session.get(AppSetting, key)
        if item is None:
            session.add(AppSetting(key=key, value=value))
        else:
            item.value = value
    session.commit()
    return get_telegram_settings(session)
