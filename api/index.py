"""
api/index.py — Recipe Cleanse web interface for Vercel deployment.

Exposes a single-page Flask application that mirrors the CLI pipeline
in a browser-friendly format.  The terminal Rich formatting is replaced
with an inline CSS design that replicates the dark-terminal aesthetic.

Routes:
    GET  /              — Input form
    POST /parse         — Scrape + AI parse, render recipe card
    POST /scale         — Re-render recipe with a new multiplier (JSON API)

Vercel entry: this file is the WSGI handler referenced in vercel.json.
"""

import sys
import os
import json

# Allow importing the recipe_cleanse package from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, render_template_string

from recipe_cleanse.scraper        import fetch_recipe
from recipe_cleanse.dynamic_engine import parse_with_ai
from recipe_cleanse.scale          import scale_ingredients

app = Flask(__name__)


# ── HTML Templates ────────────────────────────────────────────────────────────
# Inline templates keep the deployment self-contained (no /templates dir needed
# in a serverless environment).

_BASE_CSS = """
  :root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --green:    #3fb950;
    --cyan:     #58a6ff;
    --magenta:  #d2a8ff;
    --yellow:   #e3b341;
    --red:      #f85149;
    --text:     #c9d1d9;
    --muted:    #8b949e;
    --font:     'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem 1rem;
  }
  .brand {
    color: var(--green);
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 0.15em;
    margin-bottom: 0.25rem;
    text-align: center;
  }
  .tagline { color: var(--muted); font-size: 0.8rem; margin-bottom: 2rem; text-align: center; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem 2rem;
    width: 100%;
    max-width: 780px;
    margin-bottom: 1.5rem;
  }
  .title { color: var(--magenta); font-size: 1.4rem; font-weight: 700; margin-bottom: 1rem; }
  .meta-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .chip {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.4rem 0.8rem;
    font-size: 0.8rem;
  }
  .chip-label { color: var(--muted); font-size: 0.7rem; display: block; }
  .chip-value { color: var(--yellow); font-weight: 600; }
  .section-rule {
    border: none;
    border-top: 1px solid var(--cyan);
    margin: 1rem 0;
    opacity: 0.4;
  }
  .section-title { color: var(--cyan); font-weight: 700; font-size: 0.9rem; margin-bottom: 0.8rem; }
  .ingredient-list { list-style: none; }
  .ingredient-list li {
    color: var(--green);
    padding: 0.2rem 0;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }
  .ingredient-list li::before {
    content: "[ ]";
    color: var(--muted);
    font-size: 0.75rem;
    flex-shrink: 0;
  }
  .steps-list { list-style: none; counter-reset: steps; }
  .steps-list li {
    counter-increment: steps;
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.8rem;
    align-items: flex-start;
  }
  .steps-list li::before {
    content: counter(steps, decimal-leading-zero) ".";
    color: #58a6ff;
    font-weight: 700;
    flex-shrink: 0;
    min-width: 2.2rem;
  }
  .form-row { display: flex; gap: 0.75rem; flex-wrap: wrap; }
  input[type=url], input[type=number], input[type=text] {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-family: var(--font);
    font-size: 0.9rem;
    padding: 0.55rem 0.9rem;
    outline: none;
    flex: 1;
    min-width: 200px;
  }
  input:focus { border-color: var(--cyan); }
  button {
    background: var(--green);
    border: none;
    border-radius: 6px;
    color: #0d1117;
    cursor: pointer;
    font-family: var(--font);
    font-size: 0.9rem;
    font-weight: 700;
    padding: 0.55rem 1.4rem;
    white-space: nowrap;
  }
  button:hover { opacity: 0.85; }
  button.secondary {
    background: transparent;
    border: 1px solid var(--cyan);
    color: var(--cyan);
  }
  .error { color: var(--red); margin-top: 0.75rem; }
  .source-badge {
    font-size: 0.7rem;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.1rem 0.5rem;
    margin-left: 0.5rem;
  }
  .footer { color: var(--muted); font-size: 0.75rem; margin-top: 1rem; text-align: center; }
  @media (max-width: 500px) { .card { padding: 1rem; } }
"""

_HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Recipe Cleanse</title>
  <style>{{ css }}</style>
</head>
<body>
  <div class="brand">✿  Recipe Cleanse  ✿</div>
  <div class="tagline">Cuts the clutter — keeps the cooking.</div>

  <div class="card">
    <form action="/parse" method="post">
      <div class="form-row">
        <input
          type="url"
          name="url"
          placeholder="Paste a recipe blog URL…"
          required
          autofocus
          value="{{ url or '' }}"
        />
        <button type="submit">Clean Recipe →</button>
      </div>
      {% if error %}
        <p class="error">✖  {{ error }}</p>
      {% endif %}
    </form>
  </div>

  {% if recipe %}
  <div class="card">
    <div class="title">
      {{ recipe.title }}
      <span class="source-badge">{{ source }}</span>
    </div>

    {% if recipe.prep_time or recipe.cook_time or recipe.total_time or recipe.servings %}
    <div class="meta-row">
      {% if recipe.prep_time %}
      <div class="chip">
        <span class="chip-label">Prep</span>
        <span class="chip-value">{{ recipe.prep_time }}</span>
      </div>
      {% endif %}
      {% if recipe.cook_time %}
      <div class="chip">
        <span class="chip-label">Cook</span>
        <span class="chip-value">{{ recipe.cook_time }}</span>
      </div>
      {% endif %}
      {% if recipe.total_time %}
      <div class="chip">
        <span class="chip-label">Total</span>
        <span class="chip-value">{{ recipe.total_time }}</span>
      </div>
      {% endif %}
      {% if recipe.servings %}
      <div class="chip">
        <span class="chip-label">Serves</span>
        <span class="chip-value">{{ recipe.servings }}</span>
      </div>
      {% endif %}
    </div>
    {% endif %}

    <!-- Scale control -->
    <form style="margin-bottom:1rem;" onsubmit="applyScale(event)">
      <div class="form-row" style="align-items:center;">
        <label style="color:var(--muted);font-size:0.85rem;white-space:nowrap;">
          Serving scale:
        </label>
        <input
          type="number"
          id="scale-input"
          value="{{ multiplier }}"
          min="0.1"
          step="0.5"
          style="max-width:100px;"
        />
        <button type="submit" class="secondary">Apply ×</button>
      </div>
    </form>

    <!-- Ingredients -->
    <hr class="section-rule">
    <div class="section-title">Ingredients</div>
    <ul class="ingredient-list" id="ingredients-list">
      {% for item in ingredients %}
      <li>{{ item }}</li>
      {% endfor %}
    </ul>

    <!-- Instructions -->
    <hr class="section-rule">
    <div class="section-title">Instructions</div>
    <ol class="steps-list">
      {% for step in recipe.instructions %}
      <li>{{ step }}</li>
      {% endfor %}
    </ol>
  </div>

  <!-- Hidden data for client-side scaling -->
  <script>
    const BASE_INGREDIENTS = {{ base_ingredients_json }};
    const BASE_MULTIPLIER  = {{ multiplier }};

    async function applyScale(evt) {
      evt.preventDefault();
      const mult = parseFloat(document.getElementById('scale-input').value);
      if (isNaN(mult) || mult <= 0) { alert('Enter a positive number.'); return; }

      const resp = await fetch('/scale', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ingredients: BASE_INGREDIENTS, multiplier: mult }),
      });
      const data = await resp.json();
      const list = document.getElementById('ingredients-list');
      list.innerHTML = data.ingredients.map(i => `<li>${i}</li>`).join('');
    }
  </script>
  {% endif %}

  <div class="footer">Recipe Cleanse — open source, no trackers, no stories.</div>
</body>
</html>
"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    """Render the landing page with the URL input form."""
    return render_template_string(
        _HOME_TEMPLATE,
        css=_BASE_CSS,
        recipe=None,
        error=None,
        url=None,
        source=None,
        ingredients=[],
        base_ingredients_json="[]",
        multiplier=1,
    )


@app.post("/parse")
def parse():
    """
    Accept a recipe URL via HTML form POST, run the pipeline, and render
    the recipe card inline on the same page.
    """
    url        = request.form.get("url", "").strip()
    error      = None
    recipe     = None
    source     = None
    multiplier = 1.0

    if not url:
        error = "Please enter a URL."
    else:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            result = fetch_recipe(url)

            if not result.needs_ai:
                recipe = result.data
                source = "schema"
            else:
                if result.raw_text:
                    recipe = parse_with_ai(result.raw_text)
                    source = "ai"
                else:
                    error = (
                        "Couldn't extract text from that page. "
                        "Some sites require JavaScript — try another URL."
                    )

        except ConnectionError as exc:
            error = str(exc)
        except (RuntimeError, ValueError) as exc:
            error = f"AI parsing failed: {exc}"

    ingredients = recipe.get("ingredients", []) if recipe else []

    return render_template_string(
        _HOME_TEMPLATE,
        css=_BASE_CSS,
        recipe=recipe,
        error=error,
        url=url,
        source=source,
        ingredients=ingredients,
        base_ingredients_json=json.dumps(ingredients),
        multiplier=multiplier,
    )


@app.post("/scale")
def scale():
    """
    JSON API endpoint for client-side scaling.

    Request body:  { "ingredients": [...], "multiplier": 1.5 }
    Response body: { "ingredients": [...] }   (scaled list)
    """
    body        = request.get_json(silent=True) or {}
    ingredients = body.get("ingredients", [])
    multiplier  = float(body.get("multiplier", 1.0))

    if multiplier <= 0:
        return jsonify({"error": "multiplier must be positive"}), 400

    scaled = scale_ingredients(ingredients, multiplier)
    return jsonify({"ingredients": scaled})


# ── Vercel / Local dev entry point ────────────────────────────────────────────
# Vercel looks for an `app` (WSGI) object in this file.
# For local testing: `python api/index.py`

if __name__ == "__main__":
    app.run(debug=True, port=5000)
