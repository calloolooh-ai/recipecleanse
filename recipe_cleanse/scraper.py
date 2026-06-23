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

import re
import requests
from bs4 import BeautifulSoup

try:
    from recipe_scrapers import scrape_html, WebsiteNotImplementedError
except ImportError:
    # Graceful degradation if recipe-scrapers isn't installed
    scrape_html = None
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

    We fetch the HTML ourselves (with our browser User-Agent) and pass it to
    recipe-scrapers via scrape_html(), which supports recipe-scrapers v15+
    where wild_mode was removed from scrape_me().

    Args:
        url: Absolute URL of a recipe blog post.

    Returns:
        ScraperResult — caller checks .needs_ai to decide next step.

    Raises:
        ConnectionError: if the remote server is unreachable or blocks us.
    """
    # ── Shared HTTP fetch (used by both layers) ───────────────────────────
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

    html = response.text

    # ── Layer 1: recipe-scrapers (schema.org / JSON-LD) ───────────────────
    if scrape_html is not None:
        structured = _try_schema_extraction(html, url)
        if structured is not None:
            return ScraperResult(data=structured, source="schema")

    # ── Layer 2: raw HTML + BeautifulSoup ─────────────────────────────────
    return _build_raw_fallback(html)


# ── Layer 1 Implementation ────────────────────────────────────────────────────

def _try_schema_extraction(html: str, url: str) -> dict | None:
    """
    Run recipe-scrapers against pre-fetched HTML. Returns a clean dict on
    success, None on failure.

    Uses scrape_html() (recipe-scrapers v15+) so we control the HTTP request
    (browser User-Agent, redirects) and avoid SSL issues on some hosts.
    """
    try:
        scraper = scrape_html(html, org_url=url)
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
        "prep_time":    f"{prep_mins} min"  if prep_mins  is not None else "",
        "cook_time":    f"{cook_mins} min"  if cook_mins  is not None else "",
        "total_time":   f"{total_mins} min" if total_mins is not None else "",
        "servings":     safe(lambda: str(y) if (y := scraper.yields()) is not None else "", ""),
        "ingredients":  safe(scraper.ingredients, []),
        "instructions": safe(scraper.instructions_list, []),
    }


# ── Layer 2 Implementation ────────────────────────────────────────────────────

def _build_raw_fallback(html: str) -> ScraperResult:
    """
    Strip structural noise from pre-fetched HTML with BS4 and return article
    body text for the AI engine to parse.

    Note: BBC Good Food and similar sites place an <article> tag around a
    related/featured recipe card rather than the main recipe, so we prefer
    <main> over <article> and try recipe-specific class patterns first.
    """
    # ── HTML cleaning ─────────────────────────────────────────────────────
    soup = BeautifulSoup(html, "html.parser")

    # Decompose tags that never contain recipe content
    _NOISE_TAGS = [
        "script", "style", "nav", "header", "footer",
        "aside", "form", "iframe", "noscript", "button",
        "svg", "figure > figcaption",
        "[class*='ad']",
        "[class*='related']",
        "[class*='newsletter']",
        "[class*='comment']",
        "[class*='social']",
        "[class*='sidebar']",
    ]
    for selector in _NOISE_TAGS:
        for tag in soup.select(selector):
            tag.decompose()

    # Try recipe-specific containers first, then fall back to broader semantic
    # elements. <main> is preferred over <article> because on sites like BBC
    # Good Food, <article> wraps a related-recipe card, not the main recipe.
    content = (
        soup.find(attrs={"class": lambda c: c and any(k in " ".join(c).lower() for k in ("recipe__", "recipe-", "wprm-recipe", "tasty-recipe"))})
        or soup.find("main")
        or soup.find(attrs={"class": lambda c: c and "recipe" in " ".join(c).lower()})
        or soup.find(id=lambda i: i and "recipe" in i.lower())
        or soup.find("article")
        or soup.find("body")
    )

    raw_text = content.get_text(separator="\n\n", strip=True) if content else ""

    # Collapse excessive blank lines and trim to model-friendly length
    raw_text = re.sub(r'\n{3,}', '\n\n', raw_text)
    raw_text = raw_text[:MAX_RAW_TEXT_CHARS]

    result          = ScraperResult(data={}, source="ai_fallback")
    result.raw_text = raw_text
    return result


# Keep _fetch_raw_fallback as an alias for backward compatibility
def _fetch_raw_fallback(url: str) -> ScraperResult:
    """Backward-compatible wrapper — fetches HTML then delegates to _build_raw_fallback."""
    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ConnectionError(f"Network error: {exc}")
    return _build_raw_fallback(response.text)
