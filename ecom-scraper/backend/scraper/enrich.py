"""Enrichment from public online sources: RDAP (domain age), Shopify catalog,
and optionally Hunter.io (founder emails)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import settings
from .fetcher import Fetcher


# ---------------------------------------------------------------------------
# Domain age (RDAP: the free, public successor to WHOIS)
# ---------------------------------------------------------------------------


async def domain_registered(fetcher: Fetcher, domain: str) -> datetime | None:
    data = await fetcher.get_json(f"https://rdap.org/domain/{domain}", respect_robots=False)
    for event in (data or {}).get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            try:
                return datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# Shopify public catalog (/products.json)
# ---------------------------------------------------------------------------


@dataclass
class Catalog:
    product_count: int = 0
    capped: bool = False
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    currency_hint: str = "$"
    oldest_product: datetime | None = None


async def shopify_catalog(fetcher: Fetcher, base_url: str) -> Catalog | None:
    data = await fetcher.get_json(f"{base_url.rstrip('/')}/products.json?limit=250")
    products = (data or {}).get("products")
    if not isinstance(products, list) or not products:
        return None
    prices: list[float] = []
    oldest: datetime | None = None
    for p in products:
        for v in p.get("variants", [])[:1]:
            try:
                prices.append(float(v.get("price")))
            except (TypeError, ValueError):
                pass
        stamp = p.get("published_at") or p.get("created_at")
        if stamp:
            try:
                ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                oldest = ts if oldest is None or ts < oldest else oldest
            except ValueError:
                pass
    prices = [x for x in prices if x > 0]
    return Catalog(
        product_count=len(products),
        capped=len(products) >= 250,
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        avg_price=round(sum(prices) / len(prices), 2) if prices else None,
        oldest_product=oldest,
    )


# ---------------------------------------------------------------------------
# Hunter.io (optional, needs HUNTER_API_KEY)
# ---------------------------------------------------------------------------


async def hunter_founder(fetcher: Fetcher, domain: str) -> tuple[str, str, str] | None:
    """Return (email, full_name, position) for the most senior contact Hunter knows."""
    if not settings.hunter_api_key:
        return None
    data = await fetcher.get_json(
        f"https://api.hunter.io/v2/domain-search?domain={domain}&limit=10&api_key={settings.hunter_api_key}",
        respect_robots=False,
    )
    emails = ((data or {}).get("data") or {}).get("emails") or []
    senior = re.compile(r"founder|ceo|owner|chief executive|president|managing director", re.I)
    ranked = sorted(
        emails,
        key=lambda e: (
            not senior.search(e.get("position") or ""),
            e.get("seniority") != "executive",
            -(e.get("confidence") or 0),
        ),
    )
    for e in ranked:
        if e.get("value") and e.get("type") == "personal":
            name = " ".join(x for x in (e.get("first_name"), e.get("last_name")) if x)
            return e["value"].lower(), name, e.get("position") or ""
    return None


def years_since(when: datetime | int | None) -> float | None:
    if when is None:
        return None
    now = datetime.now(timezone.utc)
    if isinstance(when, int):
        return float(now.year - when)
    return round((now - when).days / 365.25, 1)
