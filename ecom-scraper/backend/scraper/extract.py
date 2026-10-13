"""Pure HTML parsing helpers (no network): easy to unit test."""
from __future__ import annotations

import html as htmllib
import json
import re
from datetime import date
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# E-commerce platform + store detection
# ---------------------------------------------------------------------------

PLATFORM_SIGNATURES: list[tuple[str, tuple[str, ...]]] = [
    ("Shopify", ("cdn.shopify.com", "shopify.theme", "myshopify.com", "shopify-section", "Shopify.shop")),
    ("WooCommerce", ("woocommerce", "wc-block", "wp-content/plugins/woocommerce")),
    ("BigCommerce", ("cdn11.bigcommerce.com", "bigcommerce.com/s-", "data-stencil")),
    ("Salesforce Commerce", ("demandware", "dwanalytics", "/on/demandware.store/")),
    ("Magento", ("mage/cookies", "magento", "Magento_")),
    ("Squarespace", ("static1.squarespace.com", "squarespace-commerce", "sqs-add-to-cart")),
    ("Wix", ("static.wixstatic.com", "wix-ecommerce", "_wixCssImports")),
    ("PrestaShop", ("prestashop",)),
]

STORE_SIGNALS = (
    "add to cart", "add to bag", "add to basket", "shop now", "shop all", "/cart", "/products/",
    "/collections/", "/product/", "/shop", "checkout", "free shipping", '"@type": "product"',
    '"@type":"product"', "product-card", "price", "in stock", "buy now",
)


def detect_platform(html: str) -> str:
    low = html.lower()
    for name, sigs in PLATFORM_SIGNATURES:
        if any(s.lower() in low for s in sigs):
            return name
    return ""


def ecommerce_score(html: str) -> int:
    low = html.lower()
    score = sum(1 for s in STORE_SIGNALS if s in low)
    if detect_platform(html):
        score += 4
    if re.search(r"[$£€]\s?\d{1,4}(?:[.,]\d{2})?", html):
        score += 2
    return score


def is_ecommerce(html: str) -> bool:
    return ecommerce_score(html) >= 6


# ---------------------------------------------------------------------------
# Text + metadata
# ---------------------------------------------------------------------------


def soupify(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def visible_text(soup: BeautifulSoup, limit: int = 20000) -> str:
    clone = BeautifulSoup(str(soup), "html.parser")
    for tag in clone(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", clone.get_text(" ", strip=True))
    return text[:limit]


def meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return htmllib.unescape(tag["content"]).strip()
    return ""


def brand_name(soup: BeautifulSoup, domain: str) -> str:
    name = meta(soup, "og:site_name", "application-name")
    if not name:
        for block in json_ld(soup):
            if block.get("@type") in ("Organization", "Brand", "OnlineStore", "Store") and block.get("name"):
                name = str(block["name"])
                break
    if not name and soup.title and soup.title.string:
        title = soup.title.string.strip()
        parts = re.split(r"\s+[|–—\-:·]\s+", title)
        # Brand is usually the shortest piece of "Home | Brand" / "Brand – Tagline"
        name = min(parts, key=len) if parts else title
    if not name:
        name = domain.split(".")[0].replace("-", " ").title()
    return name.strip()[:80]


def description(soup: BeautifulSoup) -> str:
    return meta(soup, "description", "og:description", "twitter:description")


def json_ld(soup: BeautifulSoup) -> list[dict]:
    blocks: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        blocks.extend(i for i in items if isinstance(i, dict))
    return blocks


def about_snippet(soup: BeautifulSoup, max_chars: int = 600) -> str:
    """First few substantial paragraphs of an About / Our Story page."""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    paras: list[str] = []
    for p in main.find_all(["p", "h2", "h3"]):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        if len(txt) >= 60 and not re.search(r"cookie|subscribe|newsletter|©|all rights reserved", txt, re.I):
            paras.append(txt)
        if sum(len(x) for x in paras) > max_chars:
            break
    text = " ".join(paras)
    return (text[: max_chars - 1] + "…") if len(text) > max_chars else text


# ---------------------------------------------------------------------------
# Links worth following
# ---------------------------------------------------------------------------

PAGE_PATTERNS = {
    "about": re.compile(r"about|our[-_ ]?story|who[-_ ]?we[-_ ]?are|founder|mission|our[-_ ]?team|meet", re.I),
    "contact": re.compile(r"contact|get[-_ ]?in[-_ ]?touch|support|help|press|wholesale", re.I),
}


def internal_links(soup: BeautifulSoup, base_url: str) -> dict[str, list[str]]:
    host = urlparse(base_url).netloc.removeprefix("www.")
    found: dict[str, list[str]] = {"about": [], "contact": []}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        parts = urlparse(href)
        if parts.scheme not in ("http", "https") or parts.netloc.removeprefix("www.") != host:
            continue
        label = f"{parts.path} {a.get_text(' ', strip=True)}"
        for kind, pattern in PAGE_PATTERNS.items():
            if pattern.search(label) and href not in found[kind] and "/products/" not in parts.path:
                found[kind].append(href)
    return found


# ---------------------------------------------------------------------------
# Emails + founders
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
OBFUSCATED_RE = re.compile(
    r"([A-Za-z0-9._%+\-]+)\s*(?:\[at\]|\(at\)|\{at\}|\s+at\s+)\s*([A-Za-z0-9\-]+)\s*"
    r"(?:\[dot\]|\(dot\)|\{dot\}|\s+dot\s+)\s*([A-Za-z]{2,24})",
    re.I,
)
JUNK_EMAIL = re.compile(
    r"(example\.|sentry|wixpress|\.png|\.jpg|\.jpeg|\.gif|\.webp|\.svg|@2x|domain\.com|email\.com|"
    r"yourname|name@|user@|test@|noreply|no-reply|donotreply|privacy@|abuse@|postmaster@|"
    r"shopify\.com|squarespace\.com|godaddy|cloudflare)",
    re.I,
)
GENERIC_PREFIXES = {
    "info", "hello", "hi", "hey", "contact", "support", "help", "care", "customercare", "service",
    "customerservice", "sales", "orders", "order", "shop", "store", "team", "admin", "office",
    "press", "media", "pr", "marketing", "wholesale", "partnerships", "partners", "collab",
    "collabs", "affiliates", "affiliate", "returns", "billing", "accounts", "jobs", "careers",
    "hr", "general", "enquiries", "inquiries", "mail", "studio", "community", "ambassadors",
}
FOUNDER_PREFIXES = {"founder", "founders", "ceo", "owner", "cofounder", "co-founder"}


def extract_emails(html: str) -> list[str]:
    text = htmllib.unescape(unquote(html))
    found = EMAIL_RE.findall(text)
    found += [f"{a}@{b}.{c}" for a, b, c in OBFUSCATED_RE.findall(text)]
    clean: list[str] = []
    for email in found:
        email = email.strip(".").lower()
        if email.startswith("mailto:"):
            email = email[7:]
        if JUNK_EMAIL.search(email) or len(email) > 80 or email in clean:
            continue
        clean.append(email)
    return clean


NAME = r"([A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+){1,2})"
NOT_NAMES = {
    "Our Story", "Our Founder", "The Founder", "Shop Now", "Learn More", "Read More", "About Us",
    "Our Mission", "Meet The", "Free Shipping", "Customer Service", "Contact Us", "New York",
    "Los Angeles", "United States", "United Kingdom", "San Francisco", "Gift Card", "Meet",
}
FOUNDER_PATTERNS = [
    re.compile(rf"(?:co-?)?founded\s+(?:in\s+\d{{4}}\s+)?by\s+{NAME}"),
    re.compile(rf"{NAME},?\s+(?:is\s+)?(?:our\s+|the\s+)?(?:[Cc]o-?)?[Ff]ounder"),
    re.compile(rf"(?:co-?)?founder\s*(?:&|and)?\s*(?:CEO)?\s*[,:\-–—]?\s+{NAME}"),
    re.compile(rf"\b(?:CEO|Owner)\s*[,:\-–—]\s*{NAME}"),
    re.compile(rf"\b(?:Hi|Hello|Hey),?\s+I['’]m\s+([A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+)?)"),
    re.compile(rf"\bMy name is\s+{NAME}"),
]


def find_founders(text: str, soup: BeautifulSoup | None = None) -> list[str]:
    names: list[str] = []
    if soup is not None:
        for block in json_ld(soup):
            founders = block.get("founder") or block.get("founders")
            for f in founders if isinstance(founders, list) else [founders] if founders else []:
                n = f.get("name") if isinstance(f, dict) else f
                if isinstance(n, str) and n.strip() and n not in names:
                    names.append(n.strip())
    for pattern in FOUNDER_PATTERNS:
        for match in pattern.finditer(text):
            name = re.sub(r"\s+", " ", match.group(1)).strip(" ,.'’")
            # Drop trailing role words the greedy match may have eaten.
            name = re.sub(r"\s+(Founder|Co-Founder|CEO|Owner|And|The|Is|Our)$", "", name, flags=re.I)
            words = name.split()
            if 1 <= len(words) <= 3 and name not in NOT_NAMES and name not in names and not any(
                w.lower() in {"founder", "ceo", "our", "the", "we", "brand", "company", "team", "shop"} for w in words
            ):
                names.append(name)
    return names[:3]


def rank_emails(emails: list[str], domain: str, founders: list[str]) -> list[tuple[str, str]]:
    """Return [(email, confidence)] best-first. Confidence: high / medium / low."""
    first_names = {f.split()[0].lower() for f in founders if f}
    last_names = {f.split()[-1].lower() for f in founders if len(f.split()) > 1}
    scored: list[tuple[int, str, str]] = []
    for email in emails:
        local, _, host = email.partition("@")
        on_domain = host.removeprefix("www.") == domain or host.endswith("." + domain)
        local_key = re.sub(r"[^a-z]", "", local)
        if any(n and n in local_key for n in first_names | last_names):
            score, conf = 100, "high"
        elif local_key in FOUNDER_PREFIXES or local.startswith(("founder", "ceo")):
            score, conf = 90, "high"
        elif local_key not in GENERIC_PREFIXES and on_domain and re.fullmatch(r"[a-z]+([._-][a-z]+)?", local):
            score, conf = 70, "medium"  # looks like a person's address on the brand domain
        elif local_key in {"hello", "hi", "hey", "info", "contact", "team"}:
            score, conf = 40, "low"
        else:
            score, conf = 20, "low"
        if not on_domain:
            score -= 15
        scored.append((score, email, conf))
    scored.sort(key=lambda s: -s[0])
    return [(e, c) for _, e, c in scored]


# ---------------------------------------------------------------------------
# Founding year
# ---------------------------------------------------------------------------

YEAR_PATTERNS = [
    re.compile(r"\b(?:founded|established|launched|started|born|created|est\.?|since)\s+(?:in\s+)?(?:\w+\s+)?((?:19|20)\d{2})\b", re.I),
    re.compile(r"\bin\s+((?:19|20)\d{2}),?\s+(?:we|she|he|they|our founder|i)\s+(?:founded|started|launched|created)", re.I),
]


def founded_year(text: str, soup: BeautifulSoup | None = None) -> int | None:
    this_year = date.today().year
    if soup is not None:
        for block in json_ld(soup):
            fd = str(block.get("foundingDate", ""))
            if re.match(r"(19|20)\d{2}", fd):
                return int(fd[:4])
    years = []
    for pattern in YEAR_PATTERNS:
        years += [int(y) for y in pattern.findall(text)]
    years = [y for y in years if 1900 <= y <= this_year]
    return min(years) if years else None


# ---------------------------------------------------------------------------
# Socials + marketing stack
# ---------------------------------------------------------------------------

SOCIAL_HOSTS = {
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    "facebook": "facebook.com",
    "youtube": "youtube.com",
    "pinterest": "pinterest.",
    "twitter": ("twitter.com", "x.com"),
    "linkedin": "linkedin.com",
}


def socials(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        host = urlparse(href).netloc.lower()
        path = urlparse(href).path.strip("/")
        if not path or any(x in href for x in ("/share", "sharer", "intent/tweet", "/pin/create", "/p/", "/reel/")):
            continue
        for name, needle in SOCIAL_HOSTS.items():
            needles = needle if isinstance(needle, tuple) else (needle,)
            if name not in out and any(n in host for n in needles):
                out[name] = href.split("?")[0]
    return out


# (label, category, signatures)
MARKETING_TOOLS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Meta Pixel", "ads", ("connect.facebook.net", "fbq(")),
    ("TikTok Pixel", "ads", ("analytics.tiktok.com", "ttq.load")),
    ("Pinterest Tag", "ads", ("s.pinimg.com/ct", "pintrk(")),
    ("Snap Pixel", "ads", ("sc-static.net/scevent", "snaptr(")),
    ("Google Analytics", "analytics", ("googletagmanager.com/gtag", "google-analytics.com", "gtag(")),
    ("Google Tag Manager", "analytics", ("googletagmanager.com/gtm.js",)),
    ("Google Ads", "ads", ("googleadservices.com", "AW-")),
    ("Hotjar / Clarity", "analytics", ("static.hotjar.com", "clarity.ms")),
    ("Klaviyo", "email", ("klaviyo",)),
    ("Mailchimp", "email", ("chimpstatic.com", "list-manage.com")),
    ("Omnisend", "email", ("omnisend",)),
    ("Attentive (SMS)", "sms", ("attentivemobile", "attn.tv")),
    ("Postscript (SMS)", "sms", ("postscript.io",)),
    ("Judge.me reviews", "reviews", ("judge.me",)),
    ("Yotpo", "reviews", ("yotpo",)),
    ("Okendo reviews", "reviews", ("okendo",)),
    ("Stamped reviews", "reviews", ("stamped.io",)),
    ("Loox reviews", "reviews", ("loox.io",)),
    ("Reviews.io", "reviews", ("reviews.io", "reviews.co.uk")),
    ("Trustpilot widget", "reviews", ("widget.trustpilot.com",)),
    ("Smile.io loyalty", "loyalty", ("smile.io",)),
    ("LoyaltyLion", "loyalty", ("loyaltylion",)),
    ("Rise.ai / gift cards", "loyalty", ("rise-ai",)),
    ("ReCharge subscriptions", "subscriptions", ("rechargepayments", "rechargecdn")),
    ("Skio subscriptions", "subscriptions", ("skio",)),
    ("Loop subscriptions", "subscriptions", ("loopsubscriptions",)),
    ("Afterpay", "bnpl", ("afterpay",)),
    ("Klarna", "bnpl", ("klarna",)),
    ("Affirm", "bnpl", ("affirm.com", "affirm-",)),
    ("Shop Pay Installments", "bnpl", ("shop-pay-installments", "shopify-installments")),
    ("Gorgias chat", "chat", ("gorgias",)),
    ("Tidio chat", "chat", ("tidio",)),
    ("Zendesk", "chat", ("zdassets.com", "zendesk")),
    ("Intercom", "chat", ("intercom",)),
    ("Shopify Inbox", "chat", ("shopify-chat", "shopifychat")),
    ("Rebuy / upsells", "upsell", ("rebuyengine", "rebuy")),
    ("Bold upsell", "upsell", ("boldapps", "boldcommerce")),
    ("Instagram feed / UGC", "ugc", ("instafeed", "foursixty", "taggbox", "elfsight")),
    ("Geo / multi-currency", "international", ("geolocation-app", "currency-converter", "shopify-markets", "globale")),
    ("Affiliate program", "affiliate", ("refersion", "impact.com", "shareasale", "goaffpro", "uppromote")),
]


def marketing_stack(html: str) -> list[tuple[str, str]]:
    low = html.lower()
    return [(label, cat) for label, cat, sigs in MARKETING_TOOLS if any(s.lower() in low for s in sigs)]


def site_features(soup: BeautifulSoup, html: str, base_url: str) -> dict[str, bool]:
    low = html.lower()
    links = " ".join(a.get("href", "").lower() + " " + a.get_text(" ", strip=True).lower() for a in soup.find_all("a"))
    imgs = soup.find_all("img")
    missing_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
    return {
        "https": base_url.startswith("https://"),
        "viewport": bool(soup.find("meta", attrs={"name": "viewport"})),
        "meta_description": bool(meta(soup, "description")),
        "og_image": bool(meta(soup, "og:image")),
        "h1": bool(soup.find("h1")),
        "product_schema": '"product"' in low and "ld+json" in low,
        "org_schema": '"organization"' in low and "ld+json" in low,
        "newsletter_form": bool(soup.find("input", attrs={"type": "email"})) or "newsletter" in low,
        "popup_offer": bool(re.search(r"\b(\d{1,2}% off|first order|welcome offer|join .{0,20} get)\b", low)),
        "blog": bool(re.search(r"/blogs?/|/journal|/stories|/magazine", links)),
        "faq": "faq" in links,
        "reviews_visible": bool(re.search(r"\b(reviews?|stars?|rated)\b", low)),
        "wholesale": "wholesale" in links or "stockist" in links,
        "careers": "careers" in links or "/jobs" in links,
        "press": "press" in links or "as seen in" in low or "featured in" in low,
        "affiliate_page": bool(re.search(r"affiliate|ambassador|creator program|influencer", links)),
        "free_shipping_msg": "free shipping" in low,
        "gift_cards": "gift card" in links,
        "bundles": "bundle" in links,
        "quiz": "quiz" in links,
        "many_missing_alts": len(imgs) >= 6 and missing_alt / max(len(imgs), 1) > 0.4,
    }
