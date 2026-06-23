"""
scraper.py — Dual-layer hybrid recipe fetching pipeline.

Layer 1 (Fast / Free): recipe-scrapers
  Leverages schema.org JSON-LD / Microdata embedded in thousands of food
  blog templates. Zero AI token usage when this succeeds.

Layer 2 (Fallback): requests + BeautifulSoup4
  Downloads raw HTML, strips noise tags, and extracts article body text.
  This raw text blob is handed to dynamic_engine.py for AI parsing.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

try:
    from recipe_scrapers import scrape_me, WebsiteNotImplementedError
except ImportError:
    # Graceful degradation if recipe-scrapers isn't installed
    scrape_me = None
    WebsiteNotImplementedError = Exception

from recipe_cleanse.config import REQUEST_HEADERS, REQUEST_TIMEOUT, MAX_RAW_TEXT_CHARS


# ── Public Data Container ─────────────────────────────────────────────────────

class ScraperResult:
    """
    Value object returned by fetch_recipe().

    Attributes:
        data     — structured recipe dict (populated on schema success)
        source   — "schema" | "ai_fallback"
        raw_text — unstructured page text (populated on fallback, for AI)
    """

    def __init__(self, data: dict, source: str):
        self.data     = data
        self.source   = source
        self.raw_text = ""

    @property
    def needs_ai(self) -> bool:
        """True when structured extraction failed and AI must parse raw_text."""
        return self.source == "ai_fallback"


# ── Public Entry Point ────────────────────────────────────────────────────────

def fetch_recipe(url: str) -> ScraperResult:
    """
    Attempt structured schema extraction; fall back to raw HTML scraping.

    Args:
        url: Absolute URL of a recipe blog post.

    Returns:
        ScraperResult — caller checks .needs_ai to decide next step.

    Raises:
        ConnectionError: if the remote server is unreachable or blocks us.
    """
    # ── Layer 1: recipe-scrapers (schema.org / JSON-LD) ───────────────────
    if scrape_me is not None:
        structured = _try_schema_extraction(url)
        if structured is not None:
            return ScraperResult(data=structured, source="schema")

    # ── Layer 2: raw HTML + BeautifulSoup ─────────────────────────────────
    return _fetch_raw_fallback(url)


# ── Layer 1 Implementation ────────────────────────────────────────────────────

def _try_schema_extraction(url: str) -> dict | None:
    """
    Run recipe-scrapers. Returns a clean dict on success, None on failure.
    Uses wild_mode=True so it attempts extraction even on unlisted sites.
    """
    try:
        scraper = scrape_me(url, wild_mode=True)
        data    = _extract_fields(scraper)

        # Require at least a title AND one ingredient to count as success
        if data.get("title") and data.get("ingredients"):
            return data

    except WebsiteNotImplementedError:
        pass  # Site not in recipe-scrapers database → fall through
    except Exception:
        pass  # Schema malformed, network blip, etc. → fall through

    return None


def _extract_fields(scraper) -> dict:
    """
    Pull each field from the recipe-scrapers object with individual error
    guards — one broken field should never kill the whole extraction.
    """

    def safe(fn, default=None):
        """Call fn(); return default on any exception."""
        try:
            value = fn()
            return value if value is not None else default
        except Exception:
            return default

    # recipe-scrapers returns times in minutes as integers
    prep_mins  = safe(scraper.prep_time)
    cook_mins  = safe(scraper.cook_time)
    total_mins = safe(scraper.total_time)

    return {
        "title":        safe(scraper.title, ""),
        "prep_time":    f"{prep_mins} min"  if prep_mins  else "",
        "cook_time":    f"{cook_mins} min"  if cook_mins  else "",
        "total_time":   f"{total_mins} min" if total_mins else "",
        "servings":     safe(lambda: str(scraper.yields()), ""),
        "ingredients":  safe(scraper.ingredients, []),
        "instructions": safe(scraper.instructions_list, []),
    }


# ── Layer 2 Implementation ────────────────────────────────────────────────────

def _fetch_raw_fallback(url: str) -> ScraperResult:
    """
    Download the page with requests, strip structural noise with BS4,
    and return article body text for the AI engine to parse.
    """
    # ── HTTP fetch ────────────────────────────────────────────────────────
    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise ConnectionError(
            f"Request timed out after {REQUEST_TIMEOUT}s. "
            "The site may be slow or blocking automated requests."
        )
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code
        if code == 403:
            raise ConnectionError(
                "That site is blocking automated requests (HTTP 403). "
                "BBC Good Food (bbcgoodfood.com) works well — try pasting a URL from there."
            )
        raise ConnectionError(
            f"HTTP {code} error fetching {url}. "
            "The site may require login or be blocking scrapers."
        )
    except requests.exceptions.RequestException as exc:
        raise ConnectionError(f"Network error: {exc}")

    # ── HTML cleaning ─────────────────────────────────────────────────────
    soup = BeautifulSoup(response.text, "html.parser")

    # Decompose tags that never contain recipe content
    _NOISE_TAGS = [
        "script", "style", "nav", "header", "footer",
        "aside", "form", "iframe", "noscript", "button",
        "svg", "figure > figcaption",
    ]
    for selector in _NOISE_TAGS:
        for tag in soup.select(selector):
            tag.decompose()

    # Prefer semantic content containers over the entire <body>
    content = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"class": lambda c: c and "recipe" in " ".join(c).lower()})
        or soup.find("body")
    )

    raw_text = content.get_text(separator="\n", strip=True) if content else ""

    # Trim to model-friendly length
    raw_text = raw_text[:MAX_RAW_TEXT_CHARS]

    result          = ScraperResult(data={}, source="ai_fallback")
    result.raw_text = raw_text
    return result
