"""
scale.py — Heuristic ingredient scaling engine.

Parses numeric quantities embedded in natural-language ingredient strings
and applies a float multiplier, reconstructing the original string with the
updated quantity formatted in clean, human-readable form.

Handles:
  • Whole integers          "2 eggs"          → "4 eggs"
  • Simple fractions        "1/2 cup flour"   → "1 cup flour"
  • Mixed numbers           "1 1/2 cups milk" → "3 cups milk"
  • Unicode fractions       "½ tsp salt"      → "1 tsp salt"
  • Fractional results      0.75 → "3/4",  1.333 → "1 1/3"
"""

from __future__ import annotations

import re
from fractions import Fraction


# ── Unicode fraction characters → ASCII equivalents ──────────────────────────
# Listed from most common to least common for documentation clarity.
UNICODE_FRACTIONS: dict[str, str] = {
    "½": "1/2",   # ½
    "⅓": "1/3",   # ⅓
    "⅔": "2/3",   # ⅔
    "¼": "1/4",   # ¼
    "¾": "3/4",   # ¾
    "⅛": "1/8",   # ⅛
    "⅜": "3/8",   # ⅜
    "⅝": "5/8",   # ⅝
    "⅞": "7/8",   # ⅞
    "⅙": "1/6",   # ⅙
    "⅚": "5/6",   # ⅚
    "⅕": "1/5",   # ⅕
    "⅖": "2/5",   # ⅖
    "⅗": "3/5",   # ⅗
    "⅘": "4/5",   # ⅘
}

# Build a regex character class from all unicode fraction chars
_UF_CHARS = "".join(re.escape(c) for c in UNICODE_FRACTIONS)

# Ordered from most specific to least specific so the regex engine matches
# the longest possible token first (mixed "1 1/2" before plain "1").
_QUANTITY_RE = re.compile(
    rf"""
    (
        \d+\s+\d+\s*/\s*\d+    # mixed number:      1 1/2
      | \d+\s*/\s*\d+          # slash fraction:    1/2  or  3 / 4
      | \d+                    # whole integer:     2
      | [{_UF_CHARS}]          # unicode fraction:  ½
    )
    """,
    re.VERBOSE | re.UNICODE,
)


# ── Public API ────────────────────────────────────────────────────────────────

def scale_ingredients(ingredients: list[str], multiplier: float) -> list[str]:
    """
    Return a new list with every ingredient quantity scaled by `multiplier`.

    Args:
        ingredients: Original ingredient strings from the recipe.
        multiplier:  Positive float. 1.0 is a no-op; 2.0 doubles; 0.5 halves.

    Returns:
        New list of ingredient strings with updated quantities.
    """
    if multiplier == 1.0:
        return list(ingredients)   # Fast path — nothing to do

    return [_scale_line(line, multiplier) for line in ingredients]


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _scale_line(line: str, multiplier: float) -> str:
    """
    Scale the first numeric quantity in a single ingredient string.

    Only the LEADING quantity is scaled.  Numbers embedded inside ingredient
    names (e.g. "5-spice powder", "No. 1 grade") are intentionally left alone
    because they appear after the first match and we replace only once.
    """
    # Normalise unicode fractions to ASCII so the regex always matches
    normalised = _replace_unicode_fractions(line)

    match = _QUANTITY_RE.search(normalised)
    if not match:
        return line   # No numeric quantity found — string is unchanged

    token          = match.group(0)
    original_value = _to_float(token)

    if original_value is None:
        return line   # Couldn't parse the number (shouldn't happen, but safe)

    scaled    = original_value * multiplier
    formatted = _to_string(scaled)

    # Replace only the FIRST occurrence of this token
    return normalised.replace(token, formatted, 1)


def _replace_unicode_fractions(text: str) -> str:
    """Substitute every Unicode fraction character with its ASCII form."""
    for char, ascii_equiv in UNICODE_FRACTIONS.items():
        text = text.replace(char, ascii_equiv)
    return text


def _to_float(token: str) -> float | None:
    """
    Convert a quantity token string to a Python float.

    Handles:
        "2"       → 2.0
        "1/2"     → 0.5
        "3 / 4"   → 0.75
        "1 1/2"   → 1.5
        "2 2/3"   → 2.666...
    """
    token = token.strip()

    try:
        # Mixed number: whole part + fraction (e.g. "1 1/2")
        if re.fullmatch(r"\d+\s+\d+\s*/\s*\d+", token):
            parts    = token.split(maxsplit=1)
            whole    = int(parts[0])
            fraction = Fraction(parts[1].replace(" ", ""))
            return float(whole + fraction)

        # Slash fraction (e.g. "1/2" or "3 / 4")
        if re.fullmatch(r"\d+\s*/\s*\d+", token):
            return float(Fraction(token.replace(" ", "")))

        # Whole integer
        if re.fullmatch(r"\d+", token):
            return float(token)

    except (ValueError, ZeroDivisionError):
        pass

    return None


def _to_string(value: float) -> str:
    """
    Format a float as a clean, human-readable kitchen quantity.

    Uses Python's Fraction class with a denominator cap of 16 to produce
    common cooking fractions rather than unwieldy decimals.

    Examples:
        1.0    → "1"
        0.5    → "1/2"
        1.5    → "1 1/2"
        0.75   → "3/4"
        2.333… → "2 1/3"
        0.25   → "1/4"
    """
    # limit_denominator(16) gives us 1/2, 1/3, 1/4, 1/8, 3/4 etc.
    frac      = Fraction(value).limit_denominator(16)
    whole     = frac.numerator // frac.denominator
    remainder = frac - whole    # The fractional part only

    if remainder == 0:
        return str(whole)             # Clean integer: "2"

    if whole == 0:
        return str(remainder)         # Pure fraction: "1/2"

    return f"{whole} {remainder}"     # Mixed number: "1 1/2"
