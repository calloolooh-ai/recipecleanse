"""
api/index.py — Recipe Cleanse web interface for Vercel deployment.

Routes:
    GET  /        — Input form
    POST /parse   — Scrape + AI parse, render recipe card
    POST /scale   — Re-scale ingredients (JSON API)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, render_template_string

from recipe_cleanse.scraper        import fetch_recipe
from recipe_cleanse.dynamic_engine import parse_with_ai
from recipe_cleanse.scale          import scale_ingredients, scale_instructions

app = Flask(__name__)


_BASE_CSS = """
  :root {
    --bg:        #141210;
    --surface:   #1e1a17;
    --surface2:  #252119;
    --border:    #3a342d;
    --brand:     #e8a847;
    --text:      #e8e0d5;
    --text-dim:  #b5aa9e;
    --muted:     #8a7f74;
    --error:     #d4635a;
    --link:      #a8c4e0;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    --font:      'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    --radius:    8px;
    --radius-sm: 4px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 15px;
    line-height: 1.6;
    min-height: 100vh;
    padding: 2.5rem 1rem 4rem;
  }

  .page { max-width: 860px; margin: 0 auto; }

  /* ── Brand ── */
  .brand {
    font-family: var(--font-mono);
    color: var(--brand);
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-align: center;
    margin-bottom: 0.25rem;
  }
  .tagline {
    font-family: var(--font-mono);
    color: var(--muted);
    font-size: 0.75rem;
    letter-spacing: 0.04em;
    text-align: center;
    margin-bottom: 2rem;
  }

  /* ── Search card ── */
  .search-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
  }
  .search-row { display: flex; gap: 0.5rem; }

  .url-input {
    flex: 1;
    min-width: 0;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-family: var(--font);
    font-size: 0.95rem;
    padding: 0.6rem 0.9rem;
    outline: none;
    transition: border-color 0.15s;
  }
  .url-input:focus { border-color: var(--brand); }
  .url-input::placeholder { color: var(--muted); }

  .btn-primary {
    background: var(--brand);
    border: none;
    border-radius: var(--radius-sm);
    color: #141210;
    cursor: pointer;
    font-family: var(--font);
    font-size: 0.9rem;
    font-weight: 700;
    padding: 0.6rem 1.25rem;
    white-space: nowrap;
    transition: opacity 0.15s;
    position: relative;
  }
  .btn-primary:hover { opacity: 0.88; }
  .btn-primary:disabled { opacity: 0.55; cursor: wait; }
  .btn-primary.loading { color: transparent; }
  .btn-primary.loading::after {
    content: '';
    position: absolute;
    width: 14px; height: 14px;
    top: 50%; left: 50%;
    margin: -7px 0 0 -7px;
    border: 2px solid #141210;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .example-hint { margin-top: 0.65rem; font-size: 0.8rem; color: var(--muted); }
  .example-hint a { color: var(--link); text-decoration: none; }
  .example-hint a:hover { text-decoration: underline; }

  .error-msg {
    margin-top: 0.75rem;
    color: var(--error);
    font-size: 0.875rem;
  }

  /* ── Recipe card ── */
  .recipe-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
    margin-bottom: 1.5rem;
  }

  /* ── Recipe header ── */
  .recipe-header { margin-bottom: 1.25rem; }

  .recipe-title {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.2;
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
  }

  .source-badge {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.1rem 0.45rem;
    vertical-align: middle;
    letter-spacing: 0.03em;
  }
  .scale-badge {
    display: none;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    color: var(--brand);
    border: 1px solid var(--brand);
    border-radius: 3px;
    padding: 0.1rem 0.45rem;
    vertical-align: middle;
    margin-left: 0.35rem;
    letter-spacing: 0.03em;
  }

  /* ── Metadata chips ── */
  .meta-row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1.5rem;
  }
  .chip {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.35rem 0.75rem;
  }
  .chip-label {
    display: block;
    font-size: 0.6rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
  }
  .chip-value { font-size: 0.85rem; font-weight: 600; color: var(--text); }

  /* ── Action bar ── */
  .action-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.75rem;
    flex-wrap: wrap;
  }
  .scale-group { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
  .scale-label { font-size: 0.78rem; color: var(--muted); white-space: nowrap; }
  .scale-pills { display: flex; gap: 0.3rem; flex-wrap: wrap; }

  .pill {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 20px;
    color: var(--text-dim);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 500;
    padding: 0.22rem 0.6rem;
    transition: all 0.12s;
    white-space: nowrap;
  }
  .pill:hover { border-color: var(--brand); color: var(--brand); }
  .pill.active { background: var(--brand); border-color: var(--brand); color: #141210; font-weight: 700; }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--muted);
    cursor: pointer;
    font-family: var(--font);
    font-size: 0.78rem;
    padding: 0.28rem 0.8rem;
    margin-left: auto;
    transition: all 0.12s;
    white-space: nowrap;
  }
  .btn-ghost:hover { border-color: var(--text-dim); color: var(--text); }

  /* ── Recipe body (two-column on desktop) ── */
  .recipe-body {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
  }
  @media (min-width: 680px) {
    .recipe-body { grid-template-columns: 5fr 8fr; gap: 2.5rem; }
  }

  .section-title {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--muted);
    margin-bottom: 0.9rem;
  }

  /* ── Ingredients ── */
  .ingredient-list { list-style: none; }
  .ingredient-list li { padding: 0.05rem 0; }

  .ingredient-list label {
    display: flex;
    align-items: flex-start;
    gap: 0.55rem;
    cursor: pointer;
    font-size: 0.875rem;
    line-height: 1.55;
    color: var(--text);
    transition: opacity 0.15s;
    padding: 0.18rem 0;
    user-select: none;
  }
  .ingredient-list label:hover { opacity: 0.75; }

  .ingredient-list input[type=checkbox] {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    min-width: 14px;
    border: 1px solid var(--border);
    border-radius: 2px;
    background: var(--bg);
    cursor: pointer;
    margin-top: 3px;
    position: relative;
    transition: all 0.12s;
    flex-shrink: 0;
  }
  .ingredient-list input[type=checkbox]:checked {
    background: var(--brand);
    border-color: var(--brand);
  }
  .ingredient-list input[type=checkbox]:checked::after {
    content: '';
    position: absolute;
    left: 3px; top: 1px;
    width: 5px; height: 8px;
    border: 2px solid #141210;
    border-top: none;
    border-left: none;
    transform: rotate(40deg);
  }
  .ingredient-list label.done {
    opacity: 0.38;
    text-decoration: line-through;
    text-decoration-color: var(--muted);
  }

  /* ── Instructions ── */
  .steps-list { list-style: none; counter-reset: steps; }
  .steps-list li {
    counter-increment: steps;
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    margin-bottom: 1rem;
  }
  .steps-list li::before {
    content: counter(steps);
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 1.6rem;
    height: 1.6rem;
    border-radius: 50%;
    background: var(--surface2);
    color: var(--brand);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 0.25rem;
  }
  .steps-list li span {
    font-size: 0.875rem;
    line-height: 1.75;
    color: var(--text);
  }

  /* ── Footer ── */
  .footer {
    text-align: center;
    color: var(--muted);
    font-size: 0.7rem;
    font-family: var(--font-mono);
    letter-spacing: 0.04em;
    margin-top: 1.5rem;
  }

  /* ── Mobile ── */
  @media (max-width: 500px) {
    .recipe-card { padding: 1.25rem; }
    .recipe-title { font-size: 1.5rem; }
    .search-row { flex-direction: column; }
    .btn-primary { width: 100%; text-align: center; }
    .url-input { font-size: 16px; }
  }

  /* ── Print ── */
  @media print {
    .search-card, .action-bar, .footer,
    .source-badge, .scale-badge { display: none !important; }
    body { background: white; color: black; padding: 0; font-family: Georgia, serif; }
    .recipe-card { border: none; padding: 0; background: white; }
    .recipe-title { color: black; font-size: 1.6rem; }
    .chip { border-color: #ccc; background: #f5f5f5; }
    .chip-label, .chip-value { color: #333; }
    .section-title { color: #555; }
    .ingredient-list label { color: black; }
    .ingredient-list input[type=checkbox] { border-color: #999; background: white; }
    .steps-list li::before { background: #eee; color: #333; }
    .steps-list li span { color: black; }
    .recipe-body { grid-template-columns: 5fr 8fr; gap: 2rem; }
    @page { margin: 1.5cm; }
  }
"""

_HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Recipe Cleanse{% if recipe %} — {{ recipe.title }}{% endif %}</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>✿</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{{ css }}</style>
</head>
<body>
<div class="page">

  <div class="brand">✿  Recipe Cleanse  ✿</div>
  <div class="tagline">Strip the blog. Keep the recipe.</div>

  <div class="search-card">
    <form action="/parse" method="post" onsubmit="handleSubmit(this)">
      <div class="search-row">
        <input
          class="url-input"
          type="url"
          name="url"
          placeholder="Paste a recipe blog URL…"
          required
          autofocus
          value="{{ url or '' }}"
        />
        <button class="btn-primary" type="submit">Clean →</button>
      </div>
      {% if error %}
        <p class="error-msg">✖  {{ error }}</p>
      {% endif %}
    </form>
    <p class="example-hint">
      Try: <a href="#" onclick="document.querySelector('.url-input').value='https://www.bbcgoodfood.com/recipes/banana-bread';return false;">Banana Bread</a>
      &nbsp;·&nbsp;
      <a href="#" onclick="document.querySelector('.url-input').value='https://www.bbcgoodfood.com/recipes/best-ever-chocolate-brownies-recipe';return false;">Chocolate Brownies</a>
    </p>
  </div>

  {% if recipe %}
  <main id="recipe" class="recipe-card">

    <div class="recipe-header">
      <h1 class="recipe-title">{{ recipe.title }}</h1>
      <span class="source-badge">{{ source_label }}</span>
      <span class="scale-badge" id="scale-badge"></span>
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

    <div class="action-bar">
      <div class="scale-group">
        <span class="scale-label">Scale:</span>
        <div class="scale-pills">
          <button type="button" class="pill" onclick="applyPreset(0.5, this)">½×</button>
          <button type="button" class="pill active" onclick="applyPreset(1, this)">1×</button>
          <button type="button" class="pill" onclick="applyPreset(1.5, this)">1.5×</button>
          <button type="button" class="pill" onclick="applyPreset(2, this)">2×</button>
          <button type="button" class="pill" onclick="applyPreset(3, this)">3×</button>
        </div>
      </div>
      <button type="button" class="btn-ghost" onclick="window.print()">Print</button>
    </div>

    <div class="recipe-body">
      <section>
        <h2 class="section-title">Ingredients</h2>
        <ul class="ingredient-list" id="ingredients-list">
          {% for item in ingredients %}
          <li>
            <label>
              <input type="checkbox" onchange="this.parentElement.classList.toggle('done', this.checked)">
              {{ item }}
            </label>
          </li>
          {% endfor %}
        </ul>
      </section>

      <section>
        <h2 class="section-title">Instructions</h2>
        <ol class="steps-list" id="steps-list">
          {% for step in recipe.instructions %}
          <li><span>{{ step }}</span></li>
          {% endfor %}
        </ol>
      </section>
    </div>

  </main>

  <script>
    const BASE_INGREDIENTS  = {{ ingredients | tojson }};
    const BASE_INSTRUCTIONS = {{ recipe.instructions | tojson }};
    let currentMult = 1;

    async function applyPreset(mult, btn) {
      if (mult === currentMult) return;
      const prevActive = document.querySelector('.pill.active');

      document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');

      let resp;
      try {
        resp = await fetch('/scale', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ingredients:  BASE_INGREDIENTS,
            instructions: BASE_INSTRUCTIONS,
            multiplier:   mult,
          }),
        });
      } catch (err) {
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        if (prevActive) prevActive.classList.add('active');
        return;
      }
      if (!resp.ok) {
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        if (prevActive) prevActive.classList.add('active');
        return;
      }
      const data = await resp.json();
      currentMult = mult;

      const badge = document.getElementById('scale-badge');
      badge.textContent = mult + '×';
      badge.style.display = mult === 1 ? 'none' : 'inline';
      const list = document.getElementById('ingredients-list');
      list.innerHTML = '';
      data.ingredients.forEach(text => {
        const li  = document.createElement('li');
        const lbl = document.createElement('label');
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.onchange = function() { this.parentElement.classList.toggle('done', this.checked); };
        lbl.appendChild(chk);
        lbl.appendChild(document.createTextNode(' ' + text));
        li.appendChild(lbl);
        list.appendChild(li);
      });

      const steps = document.getElementById('steps-list');
      steps.innerHTML = '';
      data.instructions.forEach(text => {
        const li   = document.createElement('li');
        const span = document.createElement('span');
        span.textContent = text;
        li.appendChild(span);
        steps.appendChild(li);
      });
    }

    window.addEventListener('DOMContentLoaded', function() {
      document.getElementById('recipe').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  </script>
  {% endif %}

  <footer class="footer">Recipe Cleanse — open source · no trackers · no stories</footer>

</div>

<script>
function handleSubmit(form) {
  const btn = form.querySelector('.btn-primary');
  btn.disabled = true;
  btn.classList.add('loading');
}
</script>
</body>
</html>
"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return render_template_string(
        _HOME_TEMPLATE,
        css=_BASE_CSS,
        recipe=None,
        error=None,
        url=None,
        source_label=None,
        ingredients=[],

    )


@app.post("/parse")
def parse():
    url          = request.form.get("url", "").strip()
    error        = None
    recipe       = None
    source_label = None

    if not url:
        error = "Please enter a URL."
    else:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            result = fetch_recipe(url)
            if not result.needs_ai:
                recipe       = result.data
                source_label = "✓ instant"
            elif result.raw_text:
                recipe       = parse_with_ai(result.raw_text)
                source_label = "✦ AI parsed"
            else:
                error = (
                    "Couldn't extract text from that page. "
                    "Some sites require JavaScript — try another URL."
                )
        except ConnectionError as exc:
            error = str(exc)
        except (RuntimeError, ValueError) as exc:
            error = f"AI parsing failed: {exc}"
        except Exception as exc:
            error = f"Unexpected error: {exc}"

    ingredients = recipe.get("ingredients", []) if recipe else []

    return render_template_string(
        _HOME_TEMPLATE,
        css=_BASE_CSS,
        recipe=recipe,
        error=error,
        url=url,
        source_label=source_label,
        ingredients=ingredients,

    )


@app.post("/scale")
def scale():
    body         = request.get_json(silent=True) or {}
    ingredients  = body.get("ingredients", [])
    instructions = body.get("instructions", [])
    try:
        multiplier = float(body.get("multiplier", 1.0))
    except (TypeError, ValueError):
        return jsonify({"error": "multiplier must be a number"}), 400
    if multiplier <= 0:
        return jsonify({"error": "multiplier must be positive"}), 400
    return jsonify({
        "ingredients":  scale_ingredients(ingredients, multiplier),
        "instructions": scale_instructions(instructions, multiplier),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
