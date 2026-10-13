"""Interactive terminal version: asks the questions, then writes the CSV.

    python cli.py
"""
from __future__ import annotations

import asyncio
import uuid

from scraper.models import NICHES, JobState, ScrapeRequest
from scraper.pipeline import run_job


def ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def pick(prompt: str, options: dict[str, str], default: str = "1") -> str:
    keys = list(options)
    print(f"\n{prompt}")
    for i, k in enumerate(keys, 1):
        print(f"  {i:>2}. {options[k]}")
    raw = ask("Choose a number", default)
    if raw.isdigit() and 1 <= int(raw) <= len(keys):
        return keys[int(raw) - 1]
    return raw  # free text (e.g. a custom niche)


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
    niche = pick("Which niche? (or type your own)", niche_opts)
    keywords = ask("Extra keywords (optional, comma-separated)")
    print("\nLocation (all optional – leave blank for anywhere)")
    country = ask("  Country, e.g. United States")
    state = ask("  State / province / region, e.g. California")
    city = ask("  City, e.g. Los Angeles")
    only_there = bool(country or state or city) and ask(
        "  Only keep brands whose website confirms that location? (y/n)", "n"
    ).lower().startswith("y")
    min_age = num("Minimum brand age in years (optional)")
    max_age = num("Maximum brand age in years (optional)")

    req = ScrapeRequest(
        count=max(1, min(count, 200)), niche=niche, keywords=keywords,
        country=country, state=state, city=city, location_required=only_there,
        min_age_years=min_age, max_age_years=max_age,
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
