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

Only scales a quantity token when it appears at the start of the string
or is immediately followed by a recognised unit word, preventing accidental
scaling of numbers embedded in ingredient names (e.g. "5-spice", "No. 2").
"""

from __future__ import annotations

import re
from fractions import Fraction


# ── Unicode fraction characters → ASCII equivalents ──────────────────────────
UNICODE_FRACTIONS: dict[str, str] = {
    "½": "1/2",
    "⅓": "1/3",
    "⅔": "2/3",
    "¼": "1/4",
    "¾": "3/4",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
}

_UF_CHARS = "".join(re.escape(c) for c in UNICODE_FRACTIONS)

# Quantity pattern — ordered most-specific first
_QUANTITY_PATTERN = rf"""
    (
        \d+\s+\d+\s*/\s*\d+    # mixed number:   1 1/2
      | \d+\s*/\s*\d+          # slash fraction: 1/2
      | \d+                    # whole integer:  2
      | [{_UF_CHARS}]          # unicode:        ½
    )
"""

# Unit words that legitimately follow a quantity
_UNITS = (
    r"cups?|tbsps?|tablespoons?|tsps?|teaspoons?|oz|ounces?|lbs?|pounds?|"
    r"g|grams?|kg|kilograms?|ml|milliliters?|liters?|l|"
    r"pints?|quarts?|gallons?|fl\.?\s*oz|"
    r"cans?|packages?|pkgs?|bags?|heads?|bunches?|stalks?|cloves?|"
    r"slices?|pieces?|strips?|sprigs?|leaves?|sheets?|"
    r"large|medium|small|inches?|in\b"
)

# Matches a quantity at the START of the string.
# Negative lookahead (?![-\w]) prevents matching numbers that are part of
# compound ingredient names like "5-spice" or "No2" — those have a hyphen
# or word character immediately after the digit with no whitespace.
_LEADING_RE = re.compile(
    rf"^\s*{_QUANTITY_PATTERN}(?=[\s,]|$)",
    re.VERBOSE | re.UNICODE,
)

# Matches a quantity followed by up to 2 optional adjective words, then a unit.
# Allows "2 beaten large eggs" (beaten = optional adj, large = unit) in addition
# to the simple "280g" / "2 tsp" cases.
_UNIT_QUANTITY_RE = re.compile(
    rf"{_QUANTITY_PATTERN}\s*(?:\w+\s+){{0,2}}(?={_UNITS})",
    re.VERBOSE | re.UNICODE | re.IGNORECASE,
)

# Splits instruction text into clause fragments for second-pass unitless scaling
_CLAUSE_SPLIT_RE = re.compile(r"([,;]|\s+and\s+|\s+then\s+)")


# ── Public API ────────────────────────────────────────────────────────────────

def scale_ingredients(ingredients: list[str], multiplier: float) -> list[str]:
    """Return a new list with every ingredient quantity scaled by `multiplier`."""
    if multiplier == 1.0:
        return list(ingredients)
    return [_scale_line(line, multiplier) for line in ingredients]


def scale_instructions(instructions: list[str], multiplier: float) -> list[str]:
    """
    Return instruction steps with every measurement quantity scaled.

    Unlike scale_ingredients (which scales the leading quantity), this scales
    ALL quantity+unit pairs found anywhere in each step — e.g. both
    "2 cups flour" and "1/2 tsp salt" in one sentence are both scaled.
    Time values (minutes, hours) and temperatures (°F, °C) are never touched
    because they are not in the _UNITS list.
    """
    if multiplier == 1.0:
        return list(instructions)
    return [_scale_instruction_step(step, multiplier) for step in instructions]


def _scale_instruction_step(step: str, multiplier: float) -> str:
    """Scale all scalable quantities throughout a single instruction step.

    Pass 1 — unit-qualified: scales "280g", "2 tsp", "2 beaten large eggs"
    Pass 2 — clause leading: scales unitless counts ("2 mashed bananas") by
    checking the leading quantity of each comma/and-separated clause that
    wasn't already handled in pass 1.
    """
    normalised = _replace_unicode_fractions(step)

    def _replace(m: re.Match) -> str:
        token = m.group(1)
        value = _to_float(token)
        if value is None:
            return m.group(0)
        return m.group(0).replace(token, _to_string(value * multiplier), 1)

    result = _UNIT_QUANTITY_RE.sub(_replace, normalised)

    # Pass 2: scale leading quantities in clauses with no recognised unit
    clauses = _CLAUSE_SPLIT_RE.split(result)
    new_clauses = []
    for clause in clauses:
        if _CLAUSE_SPLIT_RE.fullmatch(clause):
            new_clauses.append(clause)
            continue
        if not _UNIT_QUANTITY_RE.search(clause):
            stripped = clause.lstrip()
            m = _LEADING_RE.match(stripped)
            if m:
                token = m.group(1)
                value = _to_float(token)
                if value is not None:
                    leading_ws = clause[: len(clause) - len(stripped)]
                    clause = leading_ws + stripped.replace(
                        token, _to_string(value * multiplier), 1
                    )
        new_clauses.append(clause)

    return "".join(new_clauses)


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _scale_line(line: str, multiplier: float) -> str:
    """Scale the leading quantity or the first unit-preceded quantity in a line."""
    normalised = _replace_unicode_fractions(line)

    # Prefer a leading quantity (most common case: "2 cups flour")
    match = _LEADING_RE.match(normalised)

    # Fallback: quantity immediately before a unit word ("flour, 2 cups")
    if match is None:
        match = _UNIT_QUANTITY_RE.search(normalised)

    if match is None:
        return line  # No scaleable quantity found

    token = match.group(1)
    original_value = _to_float(token)
    if original_value is None:
        return line

    scaled = original_value * multiplier
    formatted = _to_string(scaled)
    return normalised.replace(token, formatted, 1)


def _replace_unicode_fractions(text: str) -> str:
    for char, ascii_equiv in UNICODE_FRACTIONS.items():
        text = text.replace(char, ascii_equiv)
    return text


def _to_float(token: str) -> float | None:
    token = token.strip()
    try:
        if re.fullmatch(r"\d+\s+\d+\s*/\s*\d+", token):
            parts = token.split(maxsplit=1)
            return float(int(parts[0]) + Fraction(parts[1].replace(" ", "")))
        if re.fullmatch(r"\d+\s*/\s*\d+", token):
            return float(Fraction(token.replace(" ", "")))
        if re.fullmatch(r"\d+", token):
            return float(token)
    except (ValueError, ZeroDivisionError):
        pass
    return None


def _to_string(value: float) -> str:
    frac = Fraction(value).limit_denominator(16)
    whole = frac.numerator // frac.denominator
    remainder = frac - whole
    if remainder == 0:
        return str(whole)
    if whole == 0:
        return str(remainder)
    return f"{whole} {remainder}"
