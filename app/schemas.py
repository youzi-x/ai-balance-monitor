from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


SiteType = Literal["newapi", "sub2api"]
AuthMode = Literal["bearer", "api_key", "custom"]


class SitePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    site_type: SiteType
    base_url: HttpUrl
    api_token: str = Field(min_length=1, max_length=4096)
    endpoint_path: str | None = Field(default=None, max_length=300)
    auth_mode: AuthMode = "bearer"
    auth_header_name: str | None = Field(default=None, max_length=100)
    auth_prefix: str | None = Field(default=None, max_length=100)
    extra_headers: str = Field(default="", max_length=2000)
    balance_path: str = Field(default="", max_length=200)
    quota_divisor: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=1, max_length=12)
    low_balance_threshold: float = Field(default=0, ge=0)
    check_interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    enabled: bool = True

    @field_validator("endpoint_path")
    @classmethod
    def validate_endpoint_path(cls, value: str | None) -> str | None:
        if value and not value.startswith("/"):
            raise ValueError("endpoint_path must start with /")
        return value

    @field_validator("balance_path")
    @classmethod
    def validate_balance_path(cls, value: str) -> str:
        if value and any(part == ".." for part in value.split(".")):
            raise ValueError("balance_path is invalid")
        return value.strip()


class SiteUpdatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    site_type: SiteType
    base_url: HttpUrl
    api_token: str = Field(default="", max_length=4096)
    endpoint_path: str | None = Field(default=None, max_length=300)
    auth_mode: AuthMode = "bearer"
    auth_header_name: str | None = Field(default=None, max_length=100)
    auth_prefix: str | None = Field(default=None, max_length=100)
    extra_headers: str = Field(default="", max_length=2000)
    balance_path: str = Field(default="", max_length=200)
    quota_divisor: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=1, max_length=12)
    low_balance_threshold: float = Field(default=0, ge=0)
    check_interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    enabled: bool = True

    @field_validator("endpoint_path")
    @classmethod
    def validate_endpoint_path(cls, value: str | None) -> str | None:
        if value and not value.startswith("/"):
            raise ValueError("endpoint_path must start with /")
        return value


class SiteResponse(BaseModel):
    id: int
    name: str
    site_type: SiteType
    base_url: str
    api_token_masked: str
    endpoint_path: str
    auth_mode: AuthMode
    auth_header_name: str
    auth_prefix: str
    extra_headers: str
    balance_path: str
    quota_divisor: float
    currency: str
    low_balance_threshold: float
    check_interval_seconds: int | None
    enabled: bool
    last_balance: float | None
    last_checked_at: datetime | None
    last_status: str
    last_error: str | None
    consecutive_failures: int
    created_at: datetime


class CheckLogResponse(BaseModel):
    id: int
    site_id: int
    checked_at: datetime
    status: str
    balance: float | None
    message: str | None


class TelegramSettingsPayload(BaseModel):
    enabled: bool = False
    bot_token: str = Field(default="", max_length=512)
    chat_id: str = Field(default="", max_length=128)


class TelegramSettingsResponse(BaseModel):
    enabled: bool
    bot_token_masked: str
    chat_id: str
