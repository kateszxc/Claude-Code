from pathlib import Path

from scraper import extract as ex
from scraper.discovery import harvest_outbound_links, is_blocked, registrable_domain
from scraper.search import parse_duckduckgo

FIX = Path(__file__).parent / "fixtures"
HOME = (FIX / "home.html").read_text()
ABOUT = (FIX / "about.html").read_text()
CONTACT = (FIX / "contact.html").read_text()


def test_detects_shopify_store():
    assert ex.detect_platform(HOME) == "Shopify"
    assert ex.is_ecommerce(HOME)
    assert not ex.is_ecommerce(ABOUT)


def test_brand_name_and_description():
    soup = ex.soupify(HOME)
    assert ex.brand_name(soup, "glowtheory.com") == "Glow Theory"
    assert "vegan skincare" in ex.description(soup)


def test_internal_links_find_about_and_contact():
    links = ex.internal_links(ex.soupify(HOME), "https://glowtheory.com")
    assert links["about"] == ["https://glowtheory.com/pages/our-story"]
    assert "https://glowtheory.com/pages/contact" in links["contact"]


def test_emails_including_obfuscated_and_junk_filtered():
    emails = ex.extract_emails(HOME + ABOUT + CONTACT)
    assert "maya@glowtheory.com" in emails
    assert "hello@glowtheory.com" in emails
    assert "support@glowtheory.com" in emails
    assert not any(e.endswith(".png") for e in emails)


def test_founder_found_and_email_ranked_first():
    text = ex.visible_text(ex.soupify(ABOUT))
    founders = ex.find_founders(text)
    assert founders[0] == "Maya Chen"
    ranked = ex.rank_emails(
        ["hello@glowtheory.com", "support@glowtheory.com", "maya@glowtheory.com"], "glowtheory.com", founders
    )
    assert ranked[0] == ("maya@glowtheory.com", "high")
    assert dict(ranked)["hello@glowtheory.com"] == "low"


def test_personal_looking_email_is_medium_without_founder_name():
    ranked = ex.rank_emails(["info@brand.com", "jordan@brand.com"], "brand.com", [])
    assert ranked[0] == ("jordan@brand.com", "medium")


def test_founder_patterns():
    assert ex.find_founders("Meet our founder, Priya Patel, who started it all.") == ["Priya Patel"]
    assert ex.find_founders("Hi, I'm Sam and I make candles.") == ["Sam"]
    assert ex.find_founders("Shop Now and Learn More") == []


def test_founded_year():
    assert ex.founded_year("Glow Theory was founded in 2019 by Maya Chen") == 2019
    assert ex.founded_year("Est. 2015 · handmade in Ohio") == 2015
    assert ex.founded_year("Copyright 2026") is None


def test_socials_skip_share_links():
    soc = ex.socials(ex.soupify(HOME))
    assert soc == {
        "instagram": "https://www.instagram.com/glowtheory",
        "tiktok": "https://www.tiktok.com/@glowtheory",
    }


def test_marketing_stack():
    labels = {label for label, _ in ex.marketing_stack(HOME)}
    assert {"Meta Pixel", "Klaviyo", "Google Analytics"} <= labels
    assert "TikTok Pixel" not in labels


def test_site_features():
    f = ex.site_features(ex.soupify(HOME), HOME, "https://glowtheory.com")
    assert f["meta_description"] and f["viewport"] and f["blog"] and f["newsletter_form"]
    assert f["popup_offer"] and f["free_shipping_msg"]
    assert not f["og_image"]


def test_discovery_helpers():
    assert registrable_domain("https://www.Glowtheory.com/x?y") == "glowtheory.com"
    assert is_blocked("amazon.com") and is_blocked("amazon.co.uk") and is_blocked("byrdie.com")
    assert not is_blocked("glowtheory.com")
    links = harvest_outbound_links((FIX / "roundup.html").read_text(), "https://www.byrdie.com/best")
    assert links == ["glowtheory.com", "dewyco.co.uk"]


def test_parse_duckduckgo():
    hits = parse_duckduckgo((FIX / "ddg.html").read_text())
    assert hits[0].url == "https://glowtheory.com/"
    assert hits[1].title.startswith("15 Best")


def test_detect_location():
    from scraper.location import detect_location

    soup = ex.soupify(ABOUT)
    assert detect_location(ex.visible_text(soup), [soup]) == "Portland, Oregon"
    assert detect_location("Proudly based in Austin, Texas since 2015.", []) == "Austin, Texas"
    assert detect_location("Visit us: 12 Main St, Boulder, CO 80302", []) == "Boulder, CO"
    ld = ex.soupify('<script type="application/ld+json">{"@type":"Organization","address":'
                    '{"@type":"PostalAddress","addressLocality":"Toronto","addressRegion":"ON","addressCountry":"CA"}}</script>')
    assert detect_location("", [ld]) == "Toronto, ON, CA"
    assert detect_location("Free shipping on all orders.", []) == ""


def test_location_matches():
    from scraper.location import matches

    text = "Portland, Oregon"
    assert matches("Portland", "Oregon", "United States", text, "x.com")
    assert not matches("Austin", "", "", text, "x.com")
    assert matches("", "Oregon", "", text, "x.com")
    assert matches("", "Texas", "", "Austin, TX 78701", "x.com")
    assert not matches("", "Oregon", "", "Shop OR browse", "x.com")  # "OR" alone isn't Oregon
    assert matches("", "", "United States", text, "x.com")  # a US state implies the US
    assert matches("", "", "United Kingdom", "Free UK delivery", "x.com")
    assert matches("", "", "Australia", "", "brand.com.au")  # country TLD
    assert not matches("", "", "Canada", text, "x.com")
