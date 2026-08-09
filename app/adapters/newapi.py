from __future__ import annotations

from typing import Any

from app.adapters.base import BalanceAdapter, _as_number, _extract_path
from app.models import Site


class NewAPIAdapter(BalanceAdapter):
    """Reads NewAPI's authenticated dashboard user response."""

    default_endpoint_path = "/api/user/self"
    default_auth_mode = "bearer"
    default_auth_header_name = "Authorization"
    default_auth_prefix = "Bearer"
    default_quota_divisor = 500000.0

    def extract_balance(self, payload: dict[str, Any], site: Site) -> float:
        if site.balance_path:
            return _as_number(_extract_path(payload, site.balance_path)) / site.quota_divisor

        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ValueError("NewAPI response data is not an object")

        for key in ("quota", "remain_quota", "remainQuota", "balance"):
            if key in data:
                value = _as_number(data[key])
                return value / site.quota_divisor if key != "balance" else value
        raise ValueError("NewAPI balance field was not found; set balance_path manually")
