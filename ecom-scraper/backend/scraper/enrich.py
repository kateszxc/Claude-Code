"""Enrichment from public online sources: RDAP (domain age), Shopify catalog,
web search (funding news), and optionally Hunter.io (founder emails)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import settings
from .fetcher import Fetcher
from .search import search


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
# Funding (public news / press via web search)
# ---------------------------------------------------------------------------

STAGES = [
    ("Series D+", re.compile(r"series\s+[d-h]\b", re.I)),
    ("Series C", re.compile(r"series\s+c\b", re.I)),
    ("Series B", re.compile(r"series\s+b\b", re.I)),
    ("Series A", re.compile(r"series\s+a\b", re.I)),
    ("Seed", re.compile(r"\bseed\s+(round|funding|investment)|\braises?\s+.{0,30}\bseed\b", re.I)),
    ("Pre-seed", re.compile(r"pre-?seed", re.I)),
]
AMOUNT = re.compile(r"(?:raise[sd]?|secures?|secured|closes?|closed|lands?|announce[sd]?)\s+(?:a\s+)?"
                    r"([$£€]\s?\d+(?:\.\d+)?\s?(?:million|m|mn|billion|bn|k)\b)", re.I)
ACQUIRED = re.compile(r"\b(acquired by|acquires|acquisition of)\b", re.I)


@dataclass
class Funding:
    status: str = "No public funding found"
    stage: str = ""  # "", Pre-seed, Seed, Series A..., Acquired
    details: str = ""
    sources: list[str] = field(default_factory=list)

    @property
    def disclosed(self) -> bool:
        return bool(self.stage)


async def funding_lookup(fetcher: Fetcher, brand: str, domain: str) -> Funding:
    query = f'"{brand}" {domain.split(".")[0]} raises funding OR "seed round" OR "series a" OR investors'
    hits = await search(fetcher, query, limit=10)
    result = Funding()
    brand_low = brand.lower()
    best_rank = len(STAGES)
    for hit in hits:
        blob = f"{hit.title}. {hit.snippet}"
        if brand_low not in blob.lower() and domain.split(".")[0] not in blob.lower():
            continue
        amount = AMOUNT.search(blob)
        if ACQUIRED.search(blob) and not result.stage:
            result.stage, result.status = "Acquired", "Acquired (per press)"
            result.details = hit.title[:160]
            result.sources.append(hit.url)
        for rank, (label, pattern) in enumerate(STAGES):
            if pattern.search(blob) and rank < best_rank:
                best_rank = rank
                result.stage = label
                result.status = f"Funded – {label}"
                result.details = (f"{amount.group(1)} – " if amount else "") + hit.title[:160]
                result.sources.append(hit.url)
        if amount and not result.stage:
            result.stage, result.status = "Funded (stage unknown)", "Funded – stage unknown"
            result.details = f"{amount.group(1)} – {hit.title[:160]}"
            result.sources.append(hit.url)
    return result


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
