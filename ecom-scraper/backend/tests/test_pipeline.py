"""End-to-end run against mocked HTTP (no real network)."""
import csv
import json
from pathlib import Path

import httpx
import pytest
import respx

from scraper import pipeline
from scraper.analysis import SiteSignals, audit, estimate_revenue
from scraper.enrich import Catalog, Funding
from scraper.fetcher import Fetcher
from scraper.models import JobState, ScrapeRequest

FIX = Path(__file__).parent / "fixtures"


def mock_glowtheory(router: respx.MockRouter, funding_snippet: str = "") -> None:
    router.get("https://glowtheory.com/robots.txt").respond(200, text="User-agent: *\nDisallow: /checkout")
    html = {"content-type": "text/html; charset=utf-8"}
    router.get("https://glowtheory.com/pages/our-story").respond(200, text=(FIX / "about.html").read_text(), headers=html)
    router.get("https://glowtheory.com/pages/contact").respond(200, text=(FIX / "contact.html").read_text(), headers=html)
    router.get(url__startswith="https://glowtheory.com/products.json").respond(
        200, text=(FIX / "products.json").read_text(), headers={"content-type": "application/json"}
    )
    router.get("https://rdap.org/domain/glowtheory.com").respond(
        200, json={"events": [{"eventAction": "registration", "eventDate": "2018-05-01T00:00:00Z"}]}
    )
    ddg = "<html><body></body></html>"
    if funding_snippet:
        ddg = (
            '<div class="result"><a class="result__a" href="https://techcrunch.com/x">'
            f'{funding_snippet}</a><a class="result__snippet">{funding_snippet}</a></div>'
        )
    router.get(url__startswith="https://html.duckduckgo.com/").respond(200, text=ddg, headers=html)
    router.get(url__regex=r"^https://glowtheory\.com/?$").respond(200, text=(FIX / "home.html").read_text(), headers=html)
    router.get(url__regex=r"https://(www\.)?notastore\.com.*").respond(
        200, text="<html><body><h1>My blog</h1><p>Thoughts.</p></body></html>", headers=html
    )


def make_job(**kw) -> JobState:
    req = ScrapeRequest(count=1, niche="beauty-skincare", seed_urls=["https://notastore.com", "glowtheory.com"], use_ai=False, **kw)
    return JobState(id="test123456", request=req)


@pytest.fixture(autouse=True)
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.settings, "output_dir", tmp_path, raising=False)


async def run(job, router):
    fetcher = Fetcher(httpx.AsyncClient(follow_redirects=True), min_host_interval=0)
    return await pipeline.run_job(job, fetcher=fetcher, max_scan=5)


@respx.mock(assert_all_called=False)
async def test_full_run_produces_csv(respx_mock):
    mock_glowtheory(respx_mock)
    job = await run(make_job(), respx_mock)

    assert job.status == "done", job.logs
    assert job.found == 1
    r = job.results[0]
    assert r.brand_name == "Glow Theory"
    assert r.domain == "glowtheory.com"
    assert r.platform == "Shopify"
    assert r.founder_name == "Maya Chen"
    assert r.founder_email == "maya@glowtheory.com"
    assert r.email_confidence == "high"
    assert r.founded_year == 2019 and r.age_source.startswith("website")
    assert r.product_count == "42"
    assert r.funding_status == "No public funding found"
    assert "Glow Theory was founded in 2019" in r.what_they_do
    assert r.marketing_improvements and r.website_improvements and r.brand_improvements
    assert any("notastore.com: not an online store" in line for line in job.logs)

    rows = list(csv.DictReader(open(job.csv_path, encoding="utf-8-sig")))
    assert rows[0]["Founder email"] == "maya@glowtheory.com"
    assert rows[0]["Instagram"] == "https://www.instagram.com/glowtheory"
    assert rows[0]["Marketing improvements"].startswith("• ")


@respx.mock(assert_all_called=False)
async def test_age_filter_rejects(respx_mock):
    mock_glowtheory(respx_mock)
    job = await run(make_job(max_age_years=3), respx_mock)
    assert job.found == 0
    assert any("outside range" in line for line in job.logs)


@respx.mock(assert_all_called=False)
async def test_funding_filter(respx_mock):
    mock_glowtheory(respx_mock, funding_snippet="Glow Theory raises $4M seed round led by XYZ")
    job = await run(make_job(funding="bootstrapped"), respx_mock)
    assert job.found == 0

    job = await run(make_job(funding="pre_seed_seed"), respx_mock)
    assert job.found == 1
    assert job.results[0].funding_status == "Funded – Seed"
    assert job.results[0].funding_details.startswith("$4M")


@respx.mock(assert_all_called=False)
async def test_revenue_filter(respx_mock):
    mock_glowtheory(respx_mock)
    job = await run(make_job(revenue_bands=["20m_plus"]), respx_mock)
    assert job.found == 0
    assert any("estimated revenue" in line for line in job.logs)


def _signals(**kw):
    base = dict(platform="Shopify", stack=[], features={}, socials={}, catalog=None, funding=Funding(),
                age_years=None, response_ms=500, html_kb=100, has_about_page=False, about_text="", founders=[])
    base.update(kw)
    return SiteSignals(**base)


def test_revenue_band_scales_with_signals():
    assert estimate_revenue(_signals())[0] == "under_1m"
    big = _signals(
        stack=[(c, c) for c in ("ads", "email", "sms", "reviews", "loyalty", "subscriptions", "bnpl", "chat")],
        funding=Funding(stage="Series B", status="Funded – Series B"),
        age_years=10, features={"careers": True, "wholesale": True},
        catalog=Catalog(product_count=250, capped=True, avg_price=120),
    )
    assert estimate_revenue(big)[0] == "20m_plus"


def test_audit_flags_missing_basics():
    website, marketing, brand = audit(_signals())
    assert any("pixel" in m.lower() for m in marketing)
    assert any("email" in m.lower() for m in marketing)
    assert any("meta description" in w.lower() for w in website)
    assert any("story" in b.lower() for b in brand)


async def test_api_options():
    from scraper.api import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        data = (await client.get("/api/options")).json()
    assert {n["id"] for n in data["niches"]} >= {"beauty-skincare", "pets"}
    assert data["providers"]["search"] in {"brave", "serpapi", "duckduckgo"}
    assert json.dumps(data)
