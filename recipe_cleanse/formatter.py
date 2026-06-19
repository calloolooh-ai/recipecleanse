"""
formatter.py — Terminal rendering engine powered by the Rich library.

Produces a beautifully styled, full-screen recipe display featuring:
  • Branded title banner
  • Metadata chips (prep / cook / total time, servings)
  • Checkbox-style ingredient checklist
  • Numbered, paragraph-spaced cooking steps
  • Scaling multiplier indicator

All style tokens are centralised in config.THEME for easy reskinning.
"""

from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.columns import Columns
from rich.rule    import Rule
from rich.padding import Padding
from rich         import box

from recipe_cleanse.config import THEME

# Single shared console instance — import and call formatter functions anywhere
console = Console()


# ── Public API ────────────────────────────────────────────────────────────────

def render_recipe(
    data:               dict,
    multiplier:         float     = 1.0,
    scaled_ingredients: list[str] | None = None,
) -> None:
    """
    Full-screen recipe render.  Clears the terminal first so each call
    produces a clean, flicker-free refresh.

    Args:
        data:               Structured recipe dict from scraper / AI engine.
        multiplier:         Current serving scale (shown in title banner).
        scaled_ingredients: Pre-scaled list to render; falls back to data["ingredients"].
    """
    console.clear()

    ingredients = (
        scaled_ingredients
        if scaled_ingredients is not None
        else data.get("ingredients", [])
    )

    _render_header(data, multiplier)
    _render_metadata(data)
    _render_ingredients(ingredients)
    _render_instructions(data.get("instructions", []))
    _render_footer()


def print_error(message: str) -> None:
    """Styled error message printed to stderr."""
    console.print(f"\n[{THEME['error']}]✖  Error:[/{THEME['error']}] {message}\n")


def print_success(message: str) -> None:
    """Styled success confirmation."""
    console.print(f"[{THEME['success']}]✔  {message}[/{THEME['success']}]")


def print_info(message: str) -> None:
    """Muted informational status line."""
    console.print(f"[{THEME['muted']}]→  {message}[/{THEME['muted']}]")


# ── Section Renderers ─────────────────────────────────────────────────────────

def _render_header(data: dict, multiplier: float) -> None:
    """Brand bar + recipe title panel, with optional scaling badge."""
    title     = data.get("title", "Untitled Recipe")
    scale_tag = f"  ✦ {multiplier}×" if multiplier != 1.0 else ""

    # App brand bar
    brand = Text("  ✿  Recipe Cleanse  ✿  ", style=THEME["brand"], justify="center")
    console.print()
    console.print(brand, justify="center")

    # Recipe title card
    console.print(
        Panel(
            Text(f"{title}{scale_tag}", style=THEME["title"], justify="center"),
            border_style="magenta",
            padding=(0, 4),
        )
    )


def _render_metadata(data: dict) -> None:
    """Row of compact info chips for time and serving info."""
    chips = []

    for label, key in [
        ("Prep",   "prep_time"),
        ("Cook",   "cook_time"),
        ("Total",  "total_time"),
        ("Serves", "servings"),
    ]:
        value = data.get(key, "").strip()
        if value:
            chips.append(_make_chip(label, value))

    if chips:
        console.print(Columns(chips, equal=True, expand=True))
        console.print()


def _make_chip(label: str, value: str) -> Panel:
    """Single metadata chip panel."""
    content = Text(justify="center")
    content.append(f"{label}\n", style="dim cyan")
    content.append(value,        style=THEME["time"])
    return Panel(content, border_style="dim cyan", padding=(0, 1))


def _render_ingredients(ingredients: list[str]) -> None:
    """Checkbox-style ingredient list."""
    console.print(
        Rule(f"[{THEME['header']}] Ingredients [/{THEME['header']}]", style="cyan")
    )
    console.print()

    if not ingredients:
        console.print("  [dim]No ingredients found.[/dim]\n")
        return

    table = Table(box=None, show_header=False, padding=(0, 1), expand=False)
    table.add_column("check", style="dim green",       no_wrap=True, width=4)
    table.add_column("item",  style=THEME["ingredient"])

    for item in ingredients:
        table.add_row("[ ]", item)

    console.print(Padding(table, (0, 2)))
    console.print()


def _render_instructions(steps: list[str]) -> None:
    """Numbered cooking steps with comfortable vertical spacing."""
    console.print(
        Rule(f"[{THEME['header']}] Instructions [/{THEME['header']}]", style="cyan")
    )
    console.print()

    if not steps:
        console.print("  [dim]No instructions found.[/dim]\n")
        return

    for i, step in enumerate(steps, start=1):
        line = Text()
        line.append(f"  {i:02d}. ", style=THEME["step_num"])
        line.append(step,          style=THEME["step_text"])
        # Padding: (top, right, bottom, left) — bottom=1 adds blank line between steps
        console.print(Padding(line, (0, 2, 1, 0)))

    console.print()


def _render_footer() -> None:
    """Subtle footer tagline."""
    console.print(Rule(style="dim"))
    console.print(
        "[dim]Recipe Cleanse — cut the clutter, keep the cooking[/dim]",
        justify="center",
    )
    console.print()
