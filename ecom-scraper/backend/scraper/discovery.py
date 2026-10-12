"""Find candidate e-commerce brand websites for a niche.

Two sources feed the candidate queue:
  1. Search results that already look like a brand's own store.
  2. "Best <niche> brands" roundup articles, whose outbound links are harvested
     (this is where most independent DTC brands get found).
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .fetcher import Fetcher
from .models import ScrapeRequest
from .search import search

# Marketplaces, social networks, media, and directories: never a brand's own store.
BLOCKED_DOMAINS = {
    "amazon", "etsy", "ebay", "walmart", "target", "aliexpress", "alibaba", "temu", "shein", "wish",
    "bestbuy", "costco", "kohls", "macys", "nordstrom", "sephora", "ulta", "zappos", "asos",
    "wayfair", "chewy", "iherb", "vitacost", "faire", "poshmark", "depop", "mercari", "rakuten",
    "google", "youtube", "facebook", "instagram", "tiktok", "pinterest", "linkedin", "twitter", "x",
    "reddit", "quora", "medium", "substack", "wikipedia", "wikihow", "yelp", "trustpilot",
    "bbb", "glassdoor", "indeed", "crunchbase", "pitchbook", "zoominfo", "apollo", "owler",
    "shopify", "bigcommerce", "wix", "squarespace", "woocommerce", "wordpress", "godaddy",
    "forbes", "nytimes", "buzzfeed", "vogue", "elle", "allure", "byrdie", "cosmopolitan", "harpersbazaar",
    "glamour", "refinery29", "businessinsider", "insider", "cnn", "bbc", "theguardian", "huffpost",
    "techcrunch", "fastcompany", "inc", "entrepreneur", "bustle", "goodhousekeeping", "wired",
    "theverge", "nbcnews", "today", "usatoday", "wsj", "bloomberg", "cnbc", "yahoo", "msn",
    "apple", "microsoft", "bing", "duckduckgo", "brave", "github", "nymag", "thecut", "gq",
    "esquire", "menshealth", "womenshealthmag", "health", "healthline", "verywellhealth",
    "people", "popsugar", "thestrategist", "wirecutter", "cntraveler", "realsimple",
    "marieclaire", "instyle", "whowhatwear", "thezoereport", "mindbodygreen", "shape",
    "self", "prevention", "eatthis", "bonappetit", "foodandwine", "seriouseats",
    "producthunt", "kickstarter", "indiegogo", "gofundme", "storeleads", "builtwith",
    "similarweb", "semrush", "ahrefs", "statista", "ecommerce-platforms", "oberlo", "dsers",
}
BLOCKED_SUFFIXES = (".gov", ".edu", ".mil")
ROUNDUP_HINT = re.compile(r"\b(best|top|brands? (to|you)|favorite|guide|list|roundup|\d{1,3}\s)\b", re.I)


def registrable_domain(url_or_host: str) -> str:
    host = urlparse(url_or_host if "//" in url_or_host else f"https://{url_or_host}").netloc.lower()
    host = host.split("@")[-1].removesuffix(":443").removesuffix(":80")
    return host[4:] if host.startswith("www.") else host


def _domain_label(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net"} and len(parts[-1]) == 2:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else domain


def is_blocked(domain: str) -> bool:
    if not domain or "." not in domain:
        return True
    if domain.endswith(BLOCKED_SUFFIXES) or domain.count(".") > 3:
        return True
    return _domain_label(domain) in BLOCKED_DOMAINS


def build_queries(req: ScrapeRequest) -> tuple[list[str], list[str]]:
    """Return (store_queries, roundup_queries)."""
    niche = req.niche_label if req.niche_label != req.niche else req.niche
    extra = " ".join(w.strip() for w in req.keywords.split(",") if w.strip())
    where = f" {req.country}" if req.country else ""
    topic = f"{extra} {niche}".strip()
    store = [
        f"{topic} brand official online store{where}",
        f'{topic} shop "free shipping" "add to cart"{where}',
        f'{topic} "powered by shopify"{where}',
        f"independent {topic} brand shop online{where}",
        f"small {topic} business online shop{where}",
    ]
    roundup = [
        f"best {topic} DTC brands{where}",
        f"best independent {topic} brands to shop{where}",
        f"{topic} brands you should know{where}",
        f"small {topic} brands to support{where}",
        f"emerging {topic} brands{where} 2026",
        f"black-owned OR women-owned {topic} brands{where}",
    ]
    return store, roundup


def harvest_outbound_links(html: str, base_url: str) -> list[str]:
    """Pull external links from a roundup article (skipping nav/footer chrome)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    own = registrable_domain(base_url)
    seen: list[str] = []
    for a in container.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if not href.startswith("http"):
            continue
        dom = registrable_domain(href)
        if dom == own or is_blocked(dom) or dom in seen:
            continue
        seen.append(dom)
    return seen


async def discover(fetcher: Fetcher, req: ScrapeRequest, log) -> AsyncIterator[str]:
    """Yield unique candidate domains, seeds first, then search-derived ones."""
    seen: set[str] = set()

    def fresh(domain: str) -> bool:
        if not domain or domain in seen or is_blocked(domain):
            return False
        seen.add(domain)
        return True

    for url in req.seed_urls:
        dom = registrable_domain(url)
        if dom and dom not in seen:
            seen.add(dom)
            yield dom

    store_queries, roundup_queries = build_queries(req)
    # Interleave store searches and roundup harvesting so results arrive early.
    for page in range(3):
        for i in range(max(len(store_queries), len(roundup_queries))):
            if i < len(store_queries):
                q = store_queries[i]
                hits = await search(fetcher, q, page=page)
                log(f"Search: “{q}” (page {page + 1}) → {len(hits)} results")
                for hit in hits:
                    dom = registrable_domain(hit.url)
                    if fresh(dom):
                        yield dom
            if i < len(roundup_queries):
                q = roundup_queries[i]
                hits = await search(fetcher, q, page=page)
                log(f"Roundup search: “{q}” (page {page + 1}) → {len(hits)} articles")
                for hit in hits[:6]:
                    if not ROUNDUP_HINT.search(hit.title):
                        dom = registrable_domain(hit.url)
                        if fresh(dom):
                            yield dom
                        continue
                    article = await fetcher.get(hit.url)
                    if not article or not article.ok:
                        continue
                    links = harvest_outbound_links(article.text, article.url)
                    log(f"  ↳ harvested {len(links)} brand links from {registrable_domain(hit.url)}")
                    for dom in links:
                        if fresh(dom):
                            yield dom
