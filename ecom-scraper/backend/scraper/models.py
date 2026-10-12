from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Option catalogs (also served to the UI via /api/options)
# ---------------------------------------------------------------------------

NICHES: dict[str, dict] = {
    "beauty-skincare": {
        "label": "Beauty & Skincare",
        "keywords": ["skincare", "skin care", "serum", "moisturizer", "cleanser", "beauty", "cosmetics", "makeup"],
    },
    "fashion-apparel": {
        "label": "Fashion & Apparel",
        "keywords": ["apparel", "clothing", "dresses", "t-shirts", "tees", "hoodies", "fashion", "denim"],
    },
    "jewelry-accessories": {
        "label": "Jewelry & Accessories",
        "keywords": ["jewelry", "jewellery", "necklace", "earrings", "rings", "bracelet", "accessories"],
    },
    "health-supplements": {
        "label": "Health & Supplements",
        "keywords": ["supplement", "vitamins", "protein", "collagen", "gummies", "wellness", "nutrition"],
    },
    "fitness-activewear": {
        "label": "Fitness & Activewear",
        "keywords": ["activewear", "leggings", "gym", "workout", "fitness", "athleisure", "sports bra"],
    },
    "home-decor": {
        "label": "Home & Decor",
        "keywords": ["home decor", "furniture", "bedding", "rugs", "pillows", "wall art", "kitchen"],
    },
    "pets": {
        "label": "Pet Products",
        "keywords": ["dog", "cat", "pet", "treats", "collar", "leash", "pet food"],
    },
    "food-beverage": {
        "label": "Food & Beverage",
        "keywords": ["snacks", "sauce", "beverage", "drinks", "chocolate", "spices", "food"],
    },
    "coffee-tea": {
        "label": "Coffee & Tea",
        "keywords": ["coffee", "espresso", "beans", "tea", "matcha", "roast", "brew"],
    },
    "baby-kids": {
        "label": "Baby & Kids",
        "keywords": ["baby", "kids", "toddler", "toys", "nursery", "children"],
    },
    "outdoor-camping": {
        "label": "Outdoor & Camping",
        "keywords": ["outdoor", "camping", "hiking", "backpack", "tent", "gear", "adventure"],
    },
    "tech-accessories": {
        "label": "Tech Accessories",
        "keywords": ["phone case", "charger", "cable", "headphones", "tech accessories", "laptop sleeve"],
    },
    "sustainable-eco": {
        "label": "Sustainable & Eco-friendly",
        "keywords": ["sustainable", "eco-friendly", "zero waste", "organic", "recycled", "plastic-free"],
    },
    "candles-fragrance": {
        "label": "Candles & Fragrance",
        "keywords": ["candle", "candles", "fragrance", "perfume", "scent", "wax melts", "diffuser"],
    },
    "footwear": {
        "label": "Footwear",
        "keywords": ["shoes", "sneakers", "boots", "sandals", "footwear", "slippers"],
    },
    "mens-grooming": {
        "label": "Men's Grooming",
        "keywords": ["beard", "grooming", "shaving", "razor", "men's skincare", "pomade", "cologne"],
    },
}

RevenueBand = Literal["under_1m", "1m_5m", "5m_20m", "20m_plus"]
REVENUE_BANDS: dict[str, str] = {
    "under_1m": "Under $1M / yr",
    "1m_5m": "$1M – $5M / yr",
    "5m_20m": "$5M – $20M / yr",
    "20m_plus": "$20M+ / yr",
}

FundingFilter = Literal["any", "bootstrapped", "pre_seed_seed", "series_a_plus", "funded_any"]
FUNDING_FILTERS: dict[str, str] = {
    "any": "Any funding status",
    "bootstrapped": "Bootstrapped / no public funding",
    "pre_seed_seed": "Pre-seed or Seed",
    "series_a_plus": "Series A or later",
    "funded_any": "Any disclosed funding",
}


# ---------------------------------------------------------------------------
# Request / result models
# ---------------------------------------------------------------------------


class ScrapeRequest(BaseModel):
    count: int = Field(10, ge=1, le=200, description="How many matching brands to return")
    niche: str = Field("beauty-skincare", description="Preset niche id or free-text niche")
    keywords: str = Field("", description="Extra keywords to narrow the search, e.g. 'vegan, clean'")
    country: str = Field("", description="Optional country / market, e.g. 'US', 'UK', 'Australia'")
    revenue_bands: list[RevenueBand] = Field(default_factory=list, description="Empty = any revenue")
    min_age_years: float | None = Field(None, ge=0)
    max_age_years: float | None = Field(None, ge=0)
    funding: FundingFilter = "any"
    seed_urls: list[str] = Field(default_factory=list, description="Optional brand URLs to include")
    strict_filters: bool = Field(
        False, description="Drop brands whose age/funding can't be determined instead of keeping them"
    )
    use_ai: bool = Field(True, description="Use Claude for summaries + ideas when an API key is configured")

    @field_validator("seed_urls")
    @classmethod
    def _clean_urls(cls, v: list[str]) -> list[str]:
        return [u.strip() for u in v if u and u.strip()][:500]

    @property
    def niche_label(self) -> str:
        preset = NICHES.get(self.niche)
        return preset["label"] if preset else self.niche

    @property
    def niche_keywords(self) -> list[str]:
        preset = NICHES.get(self.niche)
        base = list(preset["keywords"]) if preset else [w.strip() for w in self.niche.split(",") if w.strip()]
        extra = [w.strip() for w in self.keywords.split(",") if w.strip()]
        return base + extra


class BrandResult(BaseModel):
    brand_name: str = ""
    domain: str = ""
    website_url: str = ""
    niche: str = ""
    what_they_do: str = ""
    platform: str = ""
    founder_name: str = ""
    founder_email: str = ""
    email_confidence: str = ""  # verified / high / medium / low / none
    email_source: str = ""
    other_emails: list[str] = Field(default_factory=list)
    est_revenue_band: str = ""
    revenue_basis: str = ""
    brand_age_years: float | None = None
    founded_year: int | None = None
    age_source: str = ""
    funding_status: str = ""
    funding_details: str = ""
    product_count: str = ""
    price_range: str = ""
    avg_price: float | None = None
    socials: dict[str, str] = Field(default_factory=dict)
    marketing_stack: list[str] = Field(default_factory=list)
    marketing_score: int = 0
    website_improvements: list[str] = Field(default_factory=list)
    marketing_improvements: list[str] = Field(default_factory=list)
    brand_improvements: list[str] = Field(default_factory=list)
    filter_notes: list[str] = Field(default_factory=list)
    scraped_at: str = ""


JobStatus = Literal["queued", "running", "done", "cancelled", "error"]


class JobState(BaseModel):
    id: str
    status: JobStatus = "queued"
    request: ScrapeRequest
    found: int = 0
    scanned: int = 0
    candidates: int = 0
    message: str = ""
    logs: list[str] = Field(default_factory=list)
    results: list[BrandResult] = Field(default_factory=list)
    csv_path: str = ""
    created_at: str = ""
    finished_at: str = ""
