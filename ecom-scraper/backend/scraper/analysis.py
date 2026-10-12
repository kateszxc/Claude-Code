"""Revenue estimation + rule-based marketing / website / brand audit."""
from __future__ import annotations

from dataclasses import dataclass

from .enrich import Catalog, Funding

BAND_ORDER = ["under_1m", "1m_5m", "5m_20m", "20m_plus"]


@dataclass
class SiteSignals:
    platform: str
    stack: list[tuple[str, str]]  # (label, category)
    features: dict[str, bool]
    socials: dict[str, str]
    catalog: Catalog | None
    funding: Funding
    age_years: float | None
    response_ms: int
    html_kb: int
    has_about_page: bool
    about_text: str
    founders: list[str]

    @property
    def categories(self) -> set[str]:
        return {c for _, c in self.stack}


def estimate_revenue(s: SiteSignals) -> tuple[str, str]:
    """Heuristic revenue band from public signals. Returns (band, basis)."""
    points = 0
    basis: list[str] = []
    if s.catalog:
        n = s.catalog.product_count
        if s.catalog.capped or n >= 250:
            points += 3
            basis.append("250+ products")
        elif n >= 100:
            points += 2
            basis.append(f"{n} products")
        elif n >= 30:
            points += 1
            basis.append(f"{n} products")
        if s.catalog.avg_price and s.catalog.avg_price >= 100:
            points += 1
            basis.append(f"avg price ${s.catalog.avg_price:.0f}")
    paid = {"ads", "email", "sms", "reviews", "loyalty", "subscriptions", "bnpl", "chat", "upsell", "affiliate"}
    depth = len(s.categories & paid)
    if depth >= 7:
        points += 4
    elif depth >= 5:
        points += 3
    elif depth >= 3:
        points += 2
    elif depth >= 1:
        points += 1
    if depth:
        basis.append(f"{depth} paid marketing tool categories")
    if s.funding.stage in ("Series A", "Series B", "Series C", "Series D+", "Acquired"):
        points += 4
        basis.append(s.funding.stage)
    elif s.funding.disclosed:
        points += 1
        basis.append(s.funding.stage)
    if s.age_years is not None:
        if s.age_years >= 8:
            points += 2
        elif s.age_years >= 4:
            points += 1
        basis.append(f"~{s.age_years:g} yrs old")
    for key, label in (("careers", "hiring"), ("wholesale", "wholesale/stockists")):
        if s.features.get(key):
            points += 1
            basis.append(label)
    if "international" in s.categories:
        points += 1
        basis.append("sells internationally")
    if len(s.socials) >= 4:
        points += 1
    band = BAND_ORDER[0] if points <= 4 else BAND_ORDER[1] if points <= 8 else BAND_ORDER[2] if points <= 12 else BAND_ORDER[3]
    return band, "Estimate from: " + (", ".join(basis) if basis else "few public signals")


def marketing_score(s: SiteSignals) -> int:
    cats = s.categories
    checks = [
        "ads" in cats,
        "analytics" in cats,
        "email" in cats,
        "sms" in cats,
        "reviews" in cats or s.features.get("reviews_visible", False),
        "loyalty" in cats,
        s.features.get("newsletter_form", False),
        s.features.get("popup_offer", False),
        s.features.get("blog", False),
        len(s.socials) >= 3,
        "tiktok" in s.socials,
        s.features.get("meta_description", False),
        s.features.get("og_image", False),
        s.features.get("product_schema", False),
        s.response_ms < 2500,
        s.features.get("affiliate_page", False) or "affiliate" in cats,
        "upsell" in cats or s.features.get("bundles", False),
        "bnpl" in cats,
    ]
    return round(100 * sum(checks) / len(checks))


def audit(s: SiteSignals) -> tuple[list[str], list[str], list[str]]:
    """Return (website, marketing, brand) improvement ideas, most impactful first."""
    cats, f = s.categories, s.features
    website: list[str] = []
    marketing: list[str] = []
    brand: list[str] = []

    # --- Website / conversion ---
    if s.response_ms > 3000 or s.html_kb > 1500:
        website.append(
            f"Speed up the homepage (took {s.response_ms / 1000:.1f}s / {s.html_kb} KB HTML): compress images, "
            "lazy-load below-the-fold media and trim unused apps – every extra second costs conversions."
        )
    if not f.get("meta_description"):
        website.append("Add a keyword-rich meta description so Google shows a compelling snippet instead of random page text.")
    if not f.get("product_schema"):
        website.append("Add Product structured data (price, availability, reviews) to win rich results and star ratings in search.")
    if not f.get("og_image"):
        website.append("Set an Open Graph image so links shared on social/DMs show a branded preview.")
    if not f.get("viewport"):
        website.append("Add a mobile viewport tag – most e-commerce traffic is mobile and the site may render zoomed-out.")
    if not f.get("https"):
        website.append("Serve the whole site over HTTPS; browsers flag HTTP checkouts as 'Not secure'.")
    if not f.get("h1"):
        website.append("Give the homepage a clear H1 headline that states what you sell and for whom.")
    if f.get("many_missing_alts"):
        website.append("Write alt text for product images – improves accessibility and image-search traffic.")
    if not ("reviews" in cats or f.get("reviews_visible")):
        website.append("Show customer reviews on product pages (Judge.me, Okendo, Yotpo) – social proof is the cheapest conversion lift.")
    if not f.get("faq"):
        website.append("Add an FAQ (shipping, returns, sizing/ingredients) to answer objections before checkout.")
    if "chat" not in cats:
        website.append("Add live chat / helpdesk (Gorgias, Tidio, Shopify Inbox) to catch pre-purchase questions.")
    if "bnpl" not in cats and s.catalog and (s.catalog.avg_price or 0) >= 60:
        website.append(f"Offer Buy-Now-Pay-Later (Shop Pay Installments, Klarna, Afterpay) – average price ~${s.catalog.avg_price:.0f} is a good fit.")
    if "upsell" not in cats and not f.get("bundles"):
        website.append("Add bundles, 'frequently bought together' and post-purchase upsells to raise average order value.")
    if not f.get("free_shipping_msg"):
        website.append("Advertise a free-shipping threshold in the announcement bar to lift basket size.")

    # --- Marketing ---
    if "ads" not in cats:
        marketing.append("No ad pixels detected (Meta/TikTok/Google). Install them now so you can retarget visitors and build lookalike audiences.")
    else:
        missing_ads = [n for n, k in (("TikTok Pixel", "TikTok"), ("Meta Pixel", "Meta"), ("Pinterest Tag", "Pinterest")) if n not in {l for l, _ in s.stack}]
        if missing_ads:
            marketing.append(f"Expand paid channels: add {', '.join(missing_ads)} to test cheaper audiences beyond the current pixels.")
    if "analytics" not in cats:
        marketing.append("Set up GA4 + Google Tag Manager to measure traffic sources and conversion funnels.")
    if "email" not in cats:
        marketing.append("Start email marketing (Klaviyo/Omnisend) with welcome, abandoned-cart and post-purchase flows – typically 20-30% of DTC revenue.")
    if not f.get("popup_offer"):
        marketing.append("Add a welcome-offer popup (e.g. 10% off for email/SMS) to capture first-time visitors.")
    if "sms" not in cats:
        marketing.append("Add SMS marketing (Attentive/Postscript) for launches and cart recovery – high open rates.")
    if "loyalty" not in cats:
        marketing.append("Launch a loyalty / referral program (Smile.io, LoyaltyLion) to increase repeat purchases.")
    if "subscriptions" not in cats and s.catalog and s.catalog.product_count and s.catalog.product_count < 80:
        marketing.append("If products are replenishable, offer subscribe-and-save (ReCharge, Skio) for predictable recurring revenue.")
    if not (f.get("affiliate_page") or "affiliate" in cats):
        marketing.append("Create a creator/affiliate program (UpPromote, GoAffPro, Impact) to scale UGC and influencer sales.")
    if not f.get("blog"):
        marketing.append("Start a content hub/blog targeting buyer questions in your niche for compounding SEO traffic.")
    if "tiktok" not in s.socials:
        marketing.append("No TikTok linked – short-form video is the top discovery channel for DTC brands; post founder + product content.")
    if "instagram" not in s.socials:
        marketing.append("No Instagram linked on the site – add it and feature UGC to build trust.")
    if "ugc" not in cats:
        marketing.append("Embed shoppable UGC (Instagram/TikTok feed) on the homepage and product pages.")

    # --- Brand / company ---
    if not s.has_about_page or len(s.about_text) < 200:
        brand.append("Build out an 'Our Story' page: founder photo, why the brand exists and what makes it different – people buy from people.")
    if not s.founders:
        brand.append("Put a face to the brand: name and feature the founder(s) on the About page and in social content.")
    if len(s.socials) < 3:
        brand.append("Grow a consistent presence across at least 3 social channels with the same handle, tone and visuals.")
    if not f.get("wholesale"):
        brand.append("Open a wholesale/stockist page to reach retail buyers and add a second revenue channel.")
    if not f.get("gift_cards"):
        brand.append("Sell gift cards – easy holiday revenue and new-customer acquisition through gifting.")
    if not f.get("quiz") and s.catalog and s.catalog.product_count >= 15:
        brand.append("Add a product-finder quiz to guide shoppers through a large catalog and collect zero-party data.")
    if s.funding.stage == "":
        brand.append("Collect press mentions and awards ('As seen in…') to add credibility while bootstrapped.")
    if s.age_years is not None and s.age_years < 2:
        brand.append("Young brand: focus on a hero product and a sharp positioning statement before expanding the range.")

    return website[:6], marketing[:6], brand[:4]
