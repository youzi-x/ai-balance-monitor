from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx

from app.config import settings
from app.models import Site


@dataclass(frozen=True)
class BalanceResult:
    balance: float
    currency: str
    raw: dict[str, Any]


class BalanceAdapter:
    default_endpoint_path = "/"
    default_auth_mode = "bearer"
    default_auth_header_name = "Authorization"
    default_auth_prefix = "Bearer"
    default_quota_divisor = 1.0

    async def fetch_balance(self, site: Site) -> BalanceResult:
        url = self._build_url(site)
        headers = self._build_headers(site)
        timeout = httpx.Timeout(settings.http_timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            if response.is_error:
                detail = response.text.strip().replace("\n", " ")
                detail = detail[:500] if detail else response.reason_phrase
                raise ValueError(
                    f"HTTP {response.status_code} from upstream: {detail}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("Upstream did not return JSON") from exc

        balance = self.extract_balance(payload, site)
        return BalanceResult(balance=balance, currency=site.currency, raw=payload)

    def _build_url(self, site: Site) -> str:
        base_url = site.base_url.rstrip("/")
        endpoint_path = site.endpoint_path
        if base_url.endswith("/v1") and endpoint_path.startswith("/v1/"):
            base_url = base_url[:-3]
        return f"{base_url}{endpoint_path}"

    def _build_headers(self, site: Site) -> dict[str, str]:
        if site.auth_mode == "api_key":
            header_name = site.auth_header_name or "x-api-key"
            value = site.api_token
        else:
            header_name = site.auth_header_name or self.default_auth_header_name
            prefix = site.auth_prefix.strip()
            value = f"{prefix} {site.api_token}".strip() if prefix else site.api_token
        headers = {
            "Accept": "application/json",
            "User-Agent": "AI-Balance-Monitor/1.0",
            header_name: value,
        }
        if site.extra_headers.strip():
            try:
                extra_headers = json.loads(site.extra_headers)
            except json.JSONDecodeError as exc:
                raise ValueError("extra_headers must be a valid JSON object") from exc
            if not isinstance(extra_headers, dict):
                raise ValueError("extra_headers must be a valid JSON object")
            for key, extra_value in extra_headers.items():
                if not key or extra_value is None:
                    continue
                headers[str(key)] = str(extra_value)
        return headers

    def extract_balance(self, payload: dict[str, Any], site: Site) -> float:
        if site.balance_path:
            value = _extract_path(payload, site.balance_path)
            return _as_number(value)
        raise NotImplementedError


def _extract_path(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Balance field '{path}' was not found in upstream response")
        value = value[key]
    return value


def _as_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Balance value cannot be boolean")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Balance value '{value}' is not numeric") from exc
