"""Polite async HTTP fetching: shared client, robots.txt, per-host spacing."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .config import settings


@dataclass
class Page:
    url: str
    status: int
    text: str
    elapsed_ms: int
    headers: dict[str, str]

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and bool(self.text)


class Fetcher:
    def __init__(self, client: httpx.AsyncClient | None = None, min_host_interval: float = 0.75):
        self.client = client or httpx.AsyncClient(
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            limits=httpx.Limits(max_connections=settings.concurrency * 3),
        )
        self._robots: dict[str, RobotFileParser | None] = {}
        self._robots_lock = asyncio.Lock()
        self._host_last: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self.min_host_interval = min_host_interval

    async def close(self) -> None:
        await self.client.aclose()

    async def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        async with self._robots_lock:
            if origin in self._robots:
                return self._robots[origin]
            parser: RobotFileParser | None = None
            try:
                resp = await self.client.get(f"{origin}/robots.txt", timeout=8)
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError:
                parser = None
            self._robots[origin] = parser
            return parser

    async def allowed(self, url: str) -> bool:
        parser = await self._robots_for(url)
        return parser is None or parser.can_fetch(settings.user_agent, url)

    async def _wait_turn(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._host_last.get(host, 0) + self.min_host_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._host_last[host] = time.monotonic()

    async def get(self, url: str, *, respect_robots: bool = True, **kwargs) -> Page | None:
        """GET a page. Returns None on network errors or robots.txt disallow."""
        if respect_robots and not await self.allowed(url):
            return None
        await self._wait_turn(urlparse(url).netloc)
        start = time.monotonic()
        try:
            resp = await self.client.get(url, **kwargs)
        except (httpx.HTTPError, ValueError):
            return None
        ctype = resp.headers.get("content-type", "")
        text = resp.text if ("html" in ctype or "json" in ctype or "text" in ctype or not ctype) else ""
        return Page(
            url=str(resp.url),
            status=resp.status_code,
            text=text[:2_000_000],
            elapsed_ms=int((time.monotonic() - start) * 1000),
            headers={k.lower(): v for k, v in resp.headers.items()},
        )

    async def get_json(self, url: str, *, respect_robots: bool = True, **kwargs):
        page = await self.get(url, respect_robots=respect_robots, **kwargs)
        if not page or not page.ok:
            return None
        try:
            import json

            return json.loads(page.text)
        except ValueError:
            return None
