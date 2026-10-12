"""Interactive terminal version: asks the questions, then writes the CSV.

    python cli.py
"""
from __future__ import annotations

import asyncio
import uuid

from scraper.models import FUNDING_FILTERS, NICHES, REVENUE_BANDS, JobState, ScrapeRequest
from scraper.pipeline import run_job


def ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def pick(prompt: str, options: dict[str, str], multi: bool = False, default: str = "1") -> list[str]:
    keys = list(options)
    print(f"\n{prompt}")
    for i, k in enumerate(keys, 1):
        print(f"  {i:>2}. {options[k]}")
    raw = ask("Choose " + ("one or more numbers (comma-separated, blank = any)" if multi else "a number"), default)
    chosen = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(keys):
            chosen.append(keys[int(part) - 1])
        elif part and not multi:
            return [part]  # free-text (e.g. a custom niche)
    return chosen


def num(prompt: str) -> float | None:
    raw = ask(prompt)
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def main() -> None:
    print("=== E-commerce Brand Scraper ===")
    count = int(ask("How many brands do you want to scrape", "10") or 10)
    niche_opts = {k: v["label"] for k, v in NICHES.items()}
    niche = pick("Which niche? (or type your own)", niche_opts)[0]
    keywords = ask("Extra keywords (optional, comma-separated)")
    country = ask("Target country / market (optional)")
    revenue = pick("Target revenue (estimated)", REVENUE_BANDS, multi=True, default="")
    min_age = num("Minimum brand age in years (optional)")
    max_age = num("Maximum brand age in years (optional)")
    funding = pick("Funding status", FUNDING_FILTERS)[0]

    req = ScrapeRequest(
        count=max(1, min(count, 200)), niche=niche, keywords=keywords, country=country,
        revenue_bands=revenue, min_age_years=min_age, max_age_years=max_age,
        funding=funding if funding in FUNDING_FILTERS else "any",
    )
    job = JobState(id=uuid.uuid4().hex, request=req)

    async def go():
        task = asyncio.create_task(run_job(job))
        printed = 0
        while not task.done():
            await asyncio.sleep(0.5)
            for line in job.logs[printed:]:
                print(line)
            printed = len(job.logs)
        await task
        for line in job.logs[printed:]:
            print(line)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        job.status = "cancelled"
    print(f"\nSaved {len(job.results)} brands to {job.csv_path}")


if __name__ == "__main__":
    main()
