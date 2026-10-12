"""Web search providers: Brave Search API, SerpAPI, or DuckDuckGo HTML fallback."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from .config import settings
from .fetcher import Fetcher


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str


async def search(fetcher: Fetcher, query: str, limit: int = 20, page: int = 0) -> list[SearchHit]:
    provider = settings.search_provider
    if provider == "brave":
        return await _brave(fetcher, query, limit, page)
    if provider == "serpapi":
        return await _serpapi(fetcher, query, limit, page)
    return await _duckduckgo(fetcher, query, page)


async def _brave(fetcher: Fetcher, query: str, limit: int, page: int) -> list[SearchHit]:
    data = await fetcher.get_json(
        f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(query)}"
        f"&count={min(limit, 20)}&offset={min(page, 9)}",
        respect_robots=False,
        headers={"X-Subscription-Token": settings.brave_api_key, "Accept": "application/json"},
    )
    results = ((data or {}).get("web") or {}).get("results") or []
    return [SearchHit(r.get("url", ""), r.get("title", ""), r.get("description", "")) for r in results]


async def _serpapi(fetcher: Fetcher, query: str, limit: int, page: int) -> list[SearchHit]:
    data = await fetcher.get_json(
        f"https://serpapi.com/search.json?engine=google&q={quote_plus(query)}"
        f"&num={min(limit, 100)}&start={page * limit}&api_key={settings.serpapi_key}",
        respect_robots=False,
    )
    results = (data or {}).get("organic_results") or []
    return [SearchHit(r.get("link", ""), r.get("title", ""), r.get("snippet", "")) for r in results]


async def _duckduckgo(fetcher: Fetcher, query: str, page: int) -> list[SearchHit]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    if page:
        url += f"&s={page * 30}"
    resp = await fetcher.get(url, respect_robots=False)
    if not resp or not resp.ok:
        return []
    return parse_duckduckgo(resp.text)


def parse_duckduckgo(html: str) -> list[SearchHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[SearchHit] = []
    for result in soup.select(".result"):
        link = result.select_one("a.result__a")
        if not link or not link.get("href"):
            continue
        href = link["href"]
        # DDG wraps outbound links: //duckduckgo.com/l/?uddg=<encoded target>
        if "uddg=" in href:
            href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        if href.startswith("//"):
            href = "https:" + href
        snippet = result.select_one(".result__snippet")
        hits.append(
            SearchHit(href, link.get_text(" ", strip=True), snippet.get_text(" ", strip=True) if snippet else "")
        )
    return hits
