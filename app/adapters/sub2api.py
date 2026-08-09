from __future__ import annotations

from typing import Any

from app.adapters.base import BalanceAdapter, _as_number, _extract_path
from app.models import Site


class Sub2APIAdapter(BalanceAdapter):
    """Parses Sub2API API-key usage responses."""

    default_endpoint_path = "/v1/usage"
    default_auth_mode = "bearer"
    default_auth_header_name = "Authorization"
    default_auth_prefix = "Bearer"
    default_quota_divisor = 1.0

    def extract_balance(self, payload: dict[str, Any], site: Site) -> float:
        if site.balance_path:
            return _as_number(_extract_path(payload, site.balance_path)) / site.quota_divisor

        candidates = (
            "quota.remaining",
            "remaining",
            "balance",
            "subscription.remaining",
            "data.balance",
            "data.available_balance",
            "data.remaining_balance",
            "data.quota",
            "available_balance",
            "remaining_balance",
            "quota",
        )
        for path in candidates:
            try:
                value = _as_number(_extract_path(payload, path))
                return value / site.quota_divisor
            except ValueError:
                continue
        raise ValueError("Sub2API balance field was not found; set balance_path manually")
