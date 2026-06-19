"""
main.py — Recipe Cleanse CLI entry point.

Orchestrates the full pipeline:
    URL input → Scraper → AI engine (if needed) → Scaler → Rich terminal UI

Usage:
    python main.py
    python main.py --url https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/
    python main.py --url <url> --scale 2

The interactive loop re-renders the recipe card whenever the user enters
a new serving-size multiplier, creating a smooth, REPL-like experience.
"""

import sys
import argparse

from rich.console import Console
from rich.prompt  import Prompt

from recipe_cleanse.config       import THEME
from recipe_cleanse.scraper      import fetch_recipe
from recipe_cleanse.dynamic_engine import parse_with_ai
from recipe_cleanse.scale        import scale_ingredients
from recipe_cleanse              import formatter

console = Console()


# ── Pipeline Orchestration ────────────────────────────────────────────────────

def run_pipeline(url: str) -> dict | None:
    """
    Execute scraping + optional AI parsing for the given URL.

    Step 1 — Heuristic scrape (recipe-scrapers / schema.org)
    Step 2 — AI parse (only when Step 1 yields no structured data)

    Returns the recipe dict on success, None on any unrecoverable failure.
    """
    formatter.print_info(f"Fetching: {url}")

    # ── Step 1: structured schema extraction ──────────────────────────────
    try:
        result = fetch_recipe(url)
    except ConnectionError as exc:
        formatter.print_error(str(exc))
        return None

    if not result.needs_ai:
        formatter.print_success("Schema extraction succeeded — no AI tokens used.")
        return result.data

    # ── Step 2: AI fallback ───────────────────────────────────────────────
    formatter.print_info("No schema found — routing to AI engine for parsing...")

    if not result.raw_text:
        formatter.print_error(
            "Could not extract any text from the page. "
            "The site may require JavaScript (try a different URL)."
        )
        return None

    try:
        recipe_data = parse_with_ai(result.raw_text)
        formatter.print_success("AI parsing complete.")
        return recipe_data

    except (RuntimeError, ValueError) as exc:
        formatter.print_error(f"AI parsing failed: {exc}")
        return None


# ── Interactive Display Loop ──────────────────────────────────────────────────

def interactive_loop(recipe_data: dict, initial_multiplier: float = 1.0) -> None:
    """
    Render the recipe and repeatedly prompt for a new serving-size multiplier.

    The terminal is cleared and redrawn on every multiplier change,
    giving the illusion of an interactive "live" display.
    Accepts 'exit', 'quit', or 'q' to exit gracefully.
    """
    multiplier       = initial_multiplier
    base_ingredients = recipe_data.get("ingredients", [])

    while True:
        # Re-render with the current multiplier on every loop iteration
        scaled = scale_ingredients(base_ingredients, multiplier)
        formatter.render_recipe(recipe_data, multiplier, scaled)

        raw = Prompt.ask(
            f"\n[{THEME['prompt']}]"
            "Enter scaling multiplier (e.g. 1, 1.5, 2) or type 'exit'"
            f"[/{THEME['prompt']}]",
            default=str(multiplier),
        )

        raw = raw.strip().lower()

        if raw in ("exit", "quit", "q", ""):
            console.print(
                "\n[dim]Thanks for using Recipe Cleanse.  Happy cooking! 👨‍🍳[/dim]\n"
            )
            break

        try:
            new_mult = float(raw)
            if new_mult <= 0:
                raise ValueError("Multiplier must be a positive number.")
            multiplier = new_mult

        except ValueError:
            console.print(
                f"[{THEME['error']}]"
                f"  '{raw}' is not a valid multiplier. "
                "Enter a positive number like 0.5, 1, 1.5, or 2."
                f"[/{THEME['error']}]"
            )
            # Don't update multiplier — loop again with the same value


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main() -> None:
    """Parse CLI arguments and launch the application."""
    parser = argparse.ArgumentParser(
        prog="recipe-cleanse",
        description="Recipe Cleanse — strip the blog noise, serve the recipe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py\n"
            "  python main.py --url https://example.com/chocolate-chip-cookies\n"
            "  python main.py --url https://example.com/pasta --scale 1.5\n"
        ),
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="Recipe blog URL to parse (prompted interactively if omitted)",
    )
    parser.add_argument(
        "--scale",
        metavar="MULTIPLIER",
        type=float,
        default=1.0,
        help="Initial serving-size multiplier (default: 1)",
    )
    args = parser.parse_args()

    # Splash header
    console.print()
    console.print("[bold dark_green]  ✿  Recipe Cleanse  ✿  [/bold dark_green]  [dim]v1.0[/dim]")
    console.print("[dim]  Cuts the clutter — keeps the cooking.[/dim]\n")

    # ── Get URL ───────────────────────────────────────────────────────────
    url = args.url
    if not url:
        url = Prompt.ask(f"[{THEME['prompt']}]Paste a recipe blog URL[/{THEME['prompt']}]")

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # ── Validate scale arg ────────────────────────────────────────────────
    if args.scale <= 0:
        formatter.print_error("--scale must be a positive number.")
        sys.exit(1)

    # ── Run pipeline ──────────────────────────────────────────────────────
    recipe_data = run_pipeline(url)

    if recipe_data is None:
        console.print(
            f"\n[{THEME['error']}]Could not extract a recipe from that URL.[/{THEME['error']}]\n"
            "[dim]Tips:\n"
            "  • Make sure the URL points directly to a recipe post, not a category page\n"
            "  • Some sites block automated requests — try another recipe site\n"
            "  • If using Ollama, ensure the server is running: ollama serve[/dim]\n"
        )
        sys.exit(1)

    # ── Enter interactive display ─────────────────────────────────────────
    interactive_loop(recipe_data, initial_multiplier=args.scale)


if __name__ == "__main__":
    main()
