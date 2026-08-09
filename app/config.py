from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    admin_username: str
    admin_password: str
    default_check_interval_seconds: int
    http_timeout_seconds: int
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'balance_monitor.db'}"


def load_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", "./data")).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        data_dir=data_dir,
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "change-me"),
        default_check_interval_seconds=max(
            30, int(os.getenv("DEFAULT_CHECK_INTERVAL_SECONDS", "300"))
        ),
        http_timeout_seconds=max(3, int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))),
        telegram_enabled=_as_bool(os.getenv("TELEGRAM_ENABLED")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    )


settings = load_settings()
