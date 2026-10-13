"""Where is a brand based? Detection from its website + matching a chosen location."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .extract import json_ld

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
CA_PROVINCES = {
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Nova Scotia": "NS", "Ontario": "ON", "Prince Edward Island": "PE",
    "Quebec": "QC", "Saskatchewan": "SK",
}
AU_STATES = {
    "New South Wales": "NSW", "Victoria": "VIC", "Queensland": "QLD", "Western Australia": "WA",
    "South Australia": "SA", "Tasmania": "TAS", "Australian Capital Territory": "ACT", "Northern Territory": "NT",
}
REGION_CODES = {**US_STATES, **CA_PROVINCES, **AU_STATES}

COUNTRY_ALIASES = {
    "united states": ["united states", "usa", "u.s.a", "u.s.", "america"],
    "united kingdom": ["united kingdom", "uk", "u.k.", "england", "scotland", "wales", "northern ireland", "britain"],
    "united arab emirates": ["united arab emirates", "uae", "dubai", "abu dhabi"],
    "south korea": ["south korea", "korea"],
    "netherlands": ["netherlands", "holland"],
}
COUNTRY_TLDS = {
    "united kingdom": (".uk",), "canada": (".ca",), "australia": (".au",), "new zealand": (".nz",),
    "ireland": (".ie",), "germany": (".de",), "france": (".fr",), "italy": (".it",), "spain": (".es",),
    "netherlands": (".nl",), "sweden": (".se",), "denmark": (".dk",), "norway": (".no",),
    "finland": (".fi",), "belgium": (".be",), "switzerland": (".ch",), "austria": (".at",),
    "portugal": (".pt",), "poland": (".pl",), "japan": (".jp",), "south korea": (".kr",),
    "singapore": (".sg",), "india": (".in",), "philippines": (".ph",), "south africa": (".za",),
    "mexico": (".mx",), "brazil": (".br",), "united arab emirates": (".ae",),
}

_PLACE = r"[A-Z][a-zA-Z'.\-]+(?:\s[A-Z][a-zA-Z'.\-]+){0,2}"
_DETECT = [
    # "based in Austin, Texas" / "made in Portland, OR" / "handcrafted in Bali"
    re.compile(
        rf"\b(?:based|located|headquartered|made|designed|handmade|hand-made|handcrafted|crafted|"
        rf"produced|roasted|brewed|founded|born|proudly)\s+(?:right\s+)?(?:here\s+)?in\s+(?:the\s+)?"
        rf"({_PLACE}(?:,\s*{_PLACE})?)"
    ),
    # Postal-style address: "Austin, TX 78701"
    re.compile(r"\b([A-Z][a-zA-Z.\-]+(?:\s[A-Z][a-zA-Z.\-]+){0,2},\s*[A-Z]{2})\s+\d{5}\b"),
    # Any "in City, State" pair
    re.compile(rf"\bin\s+({_PLACE},\s*{_PLACE})"),
]
_NOT_PLACES = {"The", "Our", "We", "Small", "Batches", "House", "Store", "Stock", "Stores", "Love", "Style"}


def detect_location(text: str, soups: list[BeautifulSoup]) -> str:
    """Best guess of where the brand is based, e.g. 'Portland, Oregon'. '' if unknown."""
    for soup in soups:
        for block in json_ld(soup):
            addr = block.get("address")
            if isinstance(addr, list):
                addr = addr[0] if addr else None
            if isinstance(addr, dict):
                country = addr.get("addressCountry")
                if isinstance(country, dict):
                    country = country.get("name")
                parts = [addr.get("addressLocality"), addr.get("addressRegion"), country]
                label = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
                if label:
                    return label
    for pattern in _DETECT:
        for match in pattern.finditer(text):
            place = re.sub(r"\s+", " ", match.group(1)).strip(" ,.")
            if place.split()[0] in _NOT_PLACES or len(place) > 60:
                continue
            return place
    return ""


def _word(term: str, text: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", text, re.I))


def matches(city: str, state: str, country: str, text: str, domain: str) -> bool:
    """Does the site text (incl. detected location) mention the most specific place chosen?"""
    city, state, country = city.strip(), state.strip(), country.strip()
    if city:
        return _word(city, text)
    if state:
        code = REGION_CODES.get(state.title()) or REGION_CODES.get(state)
        if _word(state, text):
            return True
        # Abbreviation only in address form ("Austin, TX") to avoid false hits like "OR" / "IN"
        return bool(code and re.search(rf",\s*{code}\b", text))
    if country:
        key = country.lower()
        if domain.endswith(COUNTRY_TLDS.get(key, ("\0",))):
            return True
        aliases = COUNTRY_ALIASES.get(key, [country])
        if any(_word(a, text) for a in aliases):
            return True
        # A US / CA / AU state or province in the text also places the brand in that country
        regions = {"united states": US_STATES, "canada": CA_PROVINCES, "australia": AU_STATES}.get(key, {})
        return any(_word(name, text) for name in regions)
    return True
