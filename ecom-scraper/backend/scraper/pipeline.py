"""Orchestrates discovery → scrape → enrich → filter → analyse → CSV."""
from __future__ import annotations

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

from . import extract as ex
from . import llm
from . import location as loc
from .analysis import SiteSignals, audit, marketing_score
from .config import settings
from .discovery import discover, registrable_domain
from .enrich import domain_registered, hunter_founder, shopify_catalog, years_since
from .fetcher import Fetcher
from .models import NICHES, BrandResult, JobState, ScrapeRequest


class Rejected(Exception):
    """Candidate did not qualify (not a store, off-niche, filtered out)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def niche_matches(text: str, req: ScrapeRequest) -> bool:
    low = text.lower()
    return any(k.lower() in low for k in req.niche_keywords) if req.niche_keywords else True


async def scrape_brand(fetcher: Fetcher, domain: str, req: ScrapeRequest, use_ai: bool) -> BrandResult:
    home = None
    for url in (f"https://{domain}", f"https://www.{domain}", f"http://{domain}"):
        home = await fetcher.get(url)
        if home and home.ok:
            break
    if not home or not home.ok:
        raise Rejected("site unreachable or blocked by robots.txt")
    if not ex.is_ecommerce(home.text):
        raise Rejected("not an online store")

    base = re.match(r"https?://[^/]+", home.url).group(0)
    domain = registrable_domain(base)
    soup = ex.soupify(home.text)
    home_text = ex.visible_text(soup)
    if not use_ai and not niche_matches(home_text + " " + ex.description(soup), req):
        raise Rejected("doesn't look like the requested niche")

    # Secondary pages: about/our-story + contact
    links = ex.internal_links(soup, base)
    about_urls = links["about"][:2]
    contact_urls = [u for u in links["contact"] if u not in about_urls][:2]
    for guess in ("/pages/about", "/pages/about-us", "/pages/contact", "/about", "/contact"):
        if not about_urls and "about" in guess:
            about_urls.append(base + guess)
        if not contact_urls and "contact" in guess:
            contact_urls.append(base + guess)
    sub_pages = await asyncio.gather(*(fetcher.get(u) for u in about_urls + contact_urls))
    pages = [(u, p) for u, p in zip(about_urls + contact_urls, sub_pages) if p and p.ok]

    about_soup = next((ex.soupify(p.text) for u, p in pages if u in about_urls), None)
    about_text = ex.about_snippet(about_soup) if about_soup else ""
    all_text = " ".join([home_text] + [ex.visible_text(ex.soupify(p.text), 15000) for _, p in pages])

    # Emails: remember which page each came from
    email_source: dict[str, str] = {}
    for url, html in [(home.url, home.text)] + [(p.url, p.text) for _, p in pages]:
        for e in ex.extract_emails(html):
            email_source.setdefault(e, url)
    founders = ex.find_founders(all_text, about_soup or soup)

    # Location: where the brand says it's based vs. what was asked for
    soups = [soup] + [ex.soupify(p.text) for _, p in pages]
    based_in = loc.detect_location(all_text, soups)
    wants_place = bool(req.location_label)
    in_place = loc.matches(req.city, req.state, req.country, f"{based_in} {all_text}", domain) if wants_place else True
    if wants_place and not in_place and req.location_required and not use_ai:
        raise Rejected(f"location not confirmed as {req.location_label}" + (f" (site says {based_in})" if based_in else ""))
    ranked = ex.rank_emails(list(email_source), domain, founders)

    brand = ex.brand_name(soup, domain)
    platform = ex.detect_platform(home.text) or "Custom / unknown"

    catalog_task = shopify_catalog(fetcher, base) if platform == "Shopify" else asyncio.sleep(0, None)
    catalog, registered, hunter = await asyncio.gather(
        catalog_task,
        domain_registered(fetcher, domain),
        hunter_founder(fetcher, domain),
    )

    # Age: stated founding year > oldest product > domain registration
    year = ex.founded_year(all_text, about_soup)
    if year:
        age, age_source = years_since(year), "website ('founded/est.' text)"
    elif catalog and catalog.oldest_product:
        age, age_source = years_since(catalog.oldest_product), "oldest product listing"
        year = catalog.oldest_product.year
    elif registered:
        age, age_source = years_since(registered), "domain registration (RDAP)"
        year = registered.year
    else:
        age, age_source = None, "unknown"

    notes: list[str] = []
    if req.min_age_years is not None or req.max_age_years is not None:
        if age is None:
            if req.strict_filters:
                raise Rejected("brand age unknown")
            notes.append("age unknown – kept")
        elif (req.min_age_years is not None and age < req.min_age_years) or (
            req.max_age_years is not None and age > req.max_age_years
        ):
            raise Rejected(f"age {age:g} yrs outside range")

    stack = ex.marketing_stack(home.text)
    features = ex.site_features(soup, home.text, home.url)
    soc = ex.socials(soup)
    signals = SiteSignals(
        platform=platform, stack=stack, features=features, socials=soc, catalog=catalog,
        age_years=age, response_ms=home.elapsed_ms, html_kb=len(home.text) // 1024,
        has_about_page=about_soup is not None, about_text=about_text, founders=founders,
    )

    website_ideas, marketing_ideas, brand_ideas = audit(signals)
    summary = about_text or ex.description(soup)

    if use_ai:
        facts = "\n".join([
            f"Platform: {platform}",
            f"Marketing tools: {', '.join(l for l, _ in stack) or 'none detected'}",
            f"Socials: {', '.join(soc) or 'none linked'}",
            f"Products: {catalog.product_count if catalog else 'unknown'}; avg price: {catalog.avg_price if catalog else 'unknown'}",
            f"Founded/age: {year or 'unknown'} ({age_source})",
            f"Location detected: {based_in or 'unknown'}",
            "Rule-based gaps found: " + "; ".join(website_ideas + marketing_ideas + brand_ideas),
        ])
        insight = await llm.brand_insight(
            niche=req.niche_label, domain=domain, name=brand, page_text=all_text[:12000], facts=facts,
            location=req.location_label,
        )
        if insight:
            if not insight.is_ecommerce_brand:
                raise Rejected("AI review: not a brand selling its own products")
            if not insight.matches_niche:
                raise Rejected("AI review: outside the requested niche")
            summary = insight.what_they_do or summary
            based_in = based_in or insight.based_in
            if wants_place and not in_place:
                in_place = insight.in_requested_location or loc.matches(
                    req.city, req.state, req.country, insight.based_in, domain
                )
            website_ideas = insight.website_improvements or website_ideas
            marketing_ideas = insight.marketing_improvements or marketing_ideas
            brand_ideas = insight.brand_improvements or brand_ideas
        elif not niche_matches(all_text, req):
            raise Rejected("doesn't look like the requested niche")
        if wants_place and not in_place and req.location_required:
            raise Rejected(f"location not confirmed as {req.location_label}")
    if wants_place and not in_place:
        notes.append(f"couldn't confirm it's based in {req.location_label} – kept")

    founder_name = founders[0] if founders else ""
    founder_email, confidence, source = "", "none", ""
    if hunter:
        founder_email, confidence, source = hunter[0], "verified", f"Hunter.io ({hunter[2] or 'contact'})"
        founder_name = founder_name or hunter[1]
    elif ranked:
        founder_email, confidence = ranked[0]
        source = email_source[founder_email]

    price_range = ""
    if catalog and catalog.min_price is not None:
        price_range = f"${catalog.min_price:,.0f} – ${catalog.max_price:,.0f}"

    return BrandResult(
        brand_name=brand,
        domain=domain,
        website_url=base,
        niche=req.niche_label,
        what_they_do=summary[:600],
        platform=platform,
        founder_name=founder_name,
        founder_email=founder_email,
        email_confidence=confidence,
        email_source=source,
        other_emails=[e for e, _ in ranked if e != founder_email][:5],
        location=based_in,
        location_match=("confirmed" if in_place else "not confirmed") if wants_place else "",
        brand_age_years=age,
        founded_year=year,
        age_source=age_source,
        product_count=(f"{catalog.product_count}+" if catalog.capped else str(catalog.product_count)) if catalog else "",
        price_range=price_range,
        avg_price=catalog.avg_price if catalog else None,
        socials=soc,
        marketing_stack=[l for l, _ in stack],
        marketing_score=marketing_score(signals),
        website_improvements=website_ideas,
        marketing_improvements=marketing_ideas,
        brand_improvements=brand_ideas,
        filter_notes=notes,
        scraped_at=_now(),
    )


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    ("Brand", "brand_name"), ("Domain", "domain"), ("Website", "website_url"), ("Niche", "niche"),
    ("What they do", "what_they_do"), ("Platform", "platform"), ("Founder name", "founder_name"),
    ("Founder email", "founder_email"), ("Email confidence", "email_confidence"),
    ("Email source", "email_source"), ("Other emails", "other_emails"),
    ("Location", "location"), ("Location match", "location_match"),
    ("Brand age (yrs)", "brand_age_years"), ("Founded", "founded_year"), ("Age source", "age_source"),
    ("Products", "product_count"), ("Price range", "price_range"), ("Avg price", "avg_price"),
    ("Instagram", "socials.instagram"), ("TikTok", "socials.tiktok"), ("Facebook", "socials.facebook"),
    ("YouTube", "socials.youtube"), ("Pinterest", "socials.pinterest"), ("LinkedIn", "socials.linkedin"),
    ("Twitter/X", "socials.twitter"), ("Marketing stack", "marketing_stack"),
    ("Marketing score (0-100)", "marketing_score"), ("Website improvements", "website_improvements"),
    ("Marketing improvements", "marketing_improvements"), ("Brand improvements", "brand_improvements"),
    ("Notes", "filter_notes"), ("Scraped at", "scraped_at"),
]


def _cell(result: BrandResult, key: str) -> str:
    if key.startswith("socials."):
        return result.socials.get(key.split(".", 1)[1], "")
    value = getattr(result, key)
    if isinstance(value, list):
        sep = "\n" if key.endswith("improvements") else "; "
        return sep.join(f"• {v}" if key.endswith("improvements") else v for v in value)
    return "" if value is None else str(value)


def write_csv(results: list[BrandResult], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel reads UTF-8
        writer = csv.writer(fh)
        writer.writerow([label for label, _ in CSV_COLUMNS])
        for r in results:
            writer.writerow([_cell(r, key) for _, key in CSV_COLUMNS])
    return path


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------


async def run_job(job: JobState, fetcher: Fetcher | None = None, max_scan: int | None = None) -> JobState:
    req = job.request
    own_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()
    use_ai = req.use_ai and llm.enabled()
    max_scan = max_scan or max(req.count * 12, 40)
    job.status, job.created_at = "running", job.created_at or _now()

    def log(msg: str) -> None:
        job.logs.append(msg)
        del job.logs[:-300]
        job.message = msg

    log(
        f"Looking for {req.count} {req.niche_label} brands"
        + (f" in {req.location_label}" if req.location_label else "")
        + f" · search: {settings.search_provider}"
        f" · AI insights: {'on' if use_ai else 'off'}"
        f" · Hunter.io: {'on' if settings.hunter_api_key else 'off'}"
    )
    sem = asyncio.Semaphore(settings.concurrency)
    tasks: set[asyncio.Task] = set()

    async def worker(domain: str) -> None:
        async with sem:
            if job.found >= req.count or job.status == "cancelled":
                return
            try:
                result = await scrape_brand(fetcher, domain, req, use_ai)
            except Rejected as why:
                log(f"✗ {domain}: {why}")
            except Exception as exc:  # one bad site must not kill the job
                log(f"✗ {domain}: error ({type(exc).__name__})")
            else:
                if job.found < req.count:
                    job.results.append(result)
                    job.found = len(job.results)
                    log(f"✓ {result.brand_name} ({domain}) – {job.found}/{req.count}")
            finally:
                job.scanned += 1

    try:
        async for domain in discover(fetcher, req, log):
            if job.found >= req.count or job.status == "cancelled" or job.candidates >= max_scan:
                break
            job.candidates += 1
            task = asyncio.create_task(worker(domain))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            # Keep the queue short so we stop discovering once enough brands are found.
            while len(tasks) >= settings.concurrency * 2:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if job.status == "cancelled":
            for t in tasks:
                t.cancel()
            log(f"Cancelled – keeping the {job.found} brands found so far.")
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if job.status != "cancelled":
            job.status = "done"
            if job.found < req.count:
                log(
                    f"Finished with {job.found}/{req.count}: ran out of qualifying candidates. "
                    "Try loosening filters, adding keywords, or adding a search API key."
                )
            else:
                log(f"Done – found {job.found} brands.")
    except Exception as exc:
        job.status = "error"
        log(f"Job failed: {type(exc).__name__}: {exc}")
    finally:
        for t in tasks:
            t.cancel()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", req.niche_label.lower()).strip("-")
        job.csv_path = str(write_csv(job.results, settings.output_dir / f"{slug}-{stamp}-{job.id[:6]}.csv"))
        job.finished_at = _now()
        if own_fetcher:
            await fetcher.close()
    return job


__all__ = ["run_job", "scrape_brand", "write_csv", "CSV_COLUMNS", "NICHES"]
