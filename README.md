# ✿ Recipe Cleanse

> Strip the blog noise. Keep the cooking.

RecipeCleanse takes any recipe blog URL and returns just the recipe. No life stories, no ads, no pop-ups. Paste a URL, get clean ingredients and steps with optional serving-size scaling.

**Live demo:** recipecleanser.vercel.app

---

## Features

- **Two-layer extraction** — tries schema.org/JSON-LD first (zero AI cost); falls back to Gemini AI only when needed
- **Ingredient scaling** — type a multiplier (0.5×, 2×, 3×) and quantities update instantly, including fractions like ½ and ⅓
- **Works almost everywhere** — `recipe-scrapers` covers 500+ sites; AI fallback handles the rest
- **Two interfaces** — beautiful Rich terminal CLI and a dark-themed web UI
- **Vercel-ready** — single `vercel.json`, deploys in one command

---

## Quickstart (CLI)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env file and add your Gemini key (free at aistudio.google.com)
cp .env.example .env

# Run interactively
python main.py

# Or pass a URL directly
python main.py --url https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/

# Scale to double servings from the start
python main.py --url <url> --scale 2
```

---

## Quickstart (Web)

```bash
pip install -r requirements.txt
cp .env.example .env   # add GOOGLE_API_KEY
python api/index.py    # runs on http://localhost:5000
```

---

## Deploy to Vercel

```bash
npm i -g vercel
vercel --prod
```

Set `GOOGLE_API_KEY` in your Vercel project environment variables.

---

## How It Works

```
URL
 └─► scraper.py        Layer 1: recipe-scrapers (schema.org / JSON-LD)
      └─► [success] ──► scale.py ──► formatter.py / web UI
      └─► [fallback] ──► dynamic_engine.py (Gemini AI parse)
                          └─► scale.py ──► formatter.py / web UI
```

1. **scraper.py** fetches the page and tries structured schema extraction (`wild_mode=True` for unlisted sites)
2. If schema extraction fails, BeautifulSoup strips noise tags and extracts article text
3. **dynamic_engine.py** sends that text to Gemini with a strict JSON-only system prompt
4. **scale.py** applies a float multiplier to quantities, handling whole numbers, slash fractions (`1/2`), mixed numbers (`1 1/2`), and unicode fractions (`½ ⅓ ¾`)
5. **formatter.py** renders the result with Rich (CLI) or inline CSS (web)

---

## Project Structure

```
main.py                  CLI entry point
recipe_cleanse/
  config.py              Theme, AI settings, system prompt
  scraper.py             Dual-layer fetch pipeline
  dynamic_engine.py      Gemini AI backend
  scale.py               Fraction-aware ingredient scaling
  formatter.py           Rich terminal rendering
api/
  index.py               Flask web app (Vercel WSGI handler)
requirements.txt
vercel.json
.env.example
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | — | Gemini API key (free tier available) |
| `GOOGLE_MODEL` | No | `gemini-2.0-flash` | Gemini model ID |
| `AI_BACKEND` | No | `google` | `google` or `ollama` |

---

## Built With

- [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) — schema.org extraction
- [google-genai](https://pypi.org/project/google-genai/) — Gemini AI SDK
- [Rich](https://github.com/Textualize/rich) — terminal UI
- [Flask](https://flask.palletsprojects.com/) — web framework
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing

---

## License

MIT
