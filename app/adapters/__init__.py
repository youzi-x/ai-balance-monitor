from app.adapters.base import BalanceAdapter, BalanceResult
from app.adapters.newapi import NewAPIAdapter
from app.adapters.sub2api import Sub2APIAdapter


def get_adapter(site_type: str) -> BalanceAdapter:
    adapters = {
        "newapi": NewAPIAdapter(),
        "sub2api": Sub2APIAdapter(),
    }
    try:
        return adapters[site_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported site type: {site_type}") from exc
