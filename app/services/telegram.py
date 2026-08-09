from __future__ import annotations

import httpx

from app.config import settings


async def send_telegram_message(config: dict[str, str | bool], text: str) -> None:
    if not config["enabled"]:
        return

    token = str(config["bot_token"]).strip()
    chat_id = str(config["chat_id"]).strip()
    if not token or not chat_id:
        raise ValueError("Telegram is enabled but bot token or chat ID is missing")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        response = await client.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        )
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Telegram API rejected message: {payload}")
