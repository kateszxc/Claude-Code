"""Optional Claude-powered summary + tailored improvement ideas."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from .config import settings

log = logging.getLogger(__name__)


class BrandInsight(BaseModel):
    what_they_do: str = Field(description="1-2 sentence plain-English summary of the brand and what it sells")
    is_ecommerce_brand: bool = Field(description="True only if this is a brand selling its own products online")
    matches_niche: bool = Field(description="True if the brand fits the requested niche")
    website_improvements: list[str] = Field(description="3-5 specific website / conversion improvements")
    marketing_improvements: list[str] = Field(description="3-5 specific marketing / growth improvements")
    brand_improvements: list[str] = Field(description="2-4 specific brand / company improvements")


SYSTEM = (
    "You are a senior DTC e-commerce growth consultant. You receive scraped data about one brand's "
    "website and the marketing tools detected on it. Write concise, specific advice that refers to what "
    "this brand actually sells and what is missing from its site; avoid generic filler. Each idea is one "
    "sentence that starts with a verb. Only rely on the data provided."
)

_client = None


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def brand_insight(*, niche: str, domain: str, name: str, page_text: str, facts: str) -> BrandInsight | None:
    if not enabled():
        return None
    import anthropic

    prompt = (
        f"Requested niche: {niche}\nBrand: {name} ({domain})\n\n"
        f"Detected facts:\n{facts}\n\n"
        f"Website text (homepage + about/contact pages):\n<site>\n{page_text}\n</site>"
    )
    try:
        response = await _get_client().beta.messages.parse(
            model=settings.anthropic_model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=BrandInsight,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError:
        log.warning("Claude rate limit hit for %s; using rule-based insights", domain)
        return None
    except anthropic.APIStatusError as exc:
        log.warning("Claude API error %s for %s: %s", exc.status_code, domain, exc.message)
        return None
    except anthropic.APIConnectionError:
        log.warning("Could not reach Claude API for %s", domain)
        return None
    if response.stop_reason == "refusal":
        return None
    return response.parsed_output
