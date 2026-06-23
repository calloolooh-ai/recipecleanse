"""
config.py — Application-wide configuration and constants.

All runtime settings are loaded from environment variables so the app
can be deployed to Vercel (production) or run locally without changing
a single line of source code.
"""

import os
from dotenv import load_dotenv

# Load .env file for local development (no-op in production)
load_dotenv()

# ── AI Backend ────────────────────────────────────────────────────────────────
# Set AI_BACKEND=groq    (default — generous free tier, very fast)
# Set AI_BACKEND=openai  (OpenAI GPT models)
# Set AI_BACKEND=google  (Gemini)
AI_BACKEND = os.getenv("AI_BACKEND", "groq")

# Groq — free tier at console.groq.com  (~14,400 req/day free)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# OpenAI — platform.openai.com/api-keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Google Gemini — aistudio.google.com/app/apikey
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL   = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash-lite")  # lite = higher free quota

# ── HTTP Fetching ─────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 20  # seconds before giving up on a slow blog

# A real browser UA avoids most bot-detection blocks
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Maximum characters fed into the AI (keeps costs + latency low)
MAX_RAW_TEXT_CHARS = 20_000

# ── AI System Prompt ──────────────────────────────────────────────────────────
# This strict prompt is the heart of the AI layer: it locks the model into
# returning ONLY machine-parseable JSON with no decorative text.
AI_SYSTEM_PROMPT = """You are a recipe data extraction engine.
Your ONLY job is to extract structured recipe data from raw webpage text.

Return ONLY a valid JSON object with EXACTLY these fields:
{
  "title":        "Recipe name as a plain string",
  "prep_time":    "Preparation time as a plain string e.g. '15 minutes', or empty string",
  "cook_time":    "Cook/bake time as a plain string e.g. '30 minutes', or empty string",
  "total_time":   "Total time as a plain string, or empty string",
  "servings":     "Number of servings as a plain string e.g. '4 servings', or empty string",
  "ingredients":  ["Full ingredient string 1 with quantity", "Full ingredient string 2"],
  "instructions": ["Complete step 1 text", "Complete step 2 text"]
}

CRITICAL RULES — violating any of these will break downstream parsing:
- Return RAW JSON only. No markdown fences (```), no explanations, no comments.
- DISCARD all blog stories, personal anecdotes, SEO paragraphs, comments, ads.
- Each instruction must be a full, standalone, actionable sentence.
- Ingredient strings must preserve original quantities and units exactly.
- If a field is missing from the source text, use an empty string "" or empty list [].
"""

# ── Rich Terminal Styling ─────────────────────────────────────────────────────
# Centralised style tokens — change these to retheme the entire CLI.
THEME = {
    "title":     "bold magenta",
    "header":    "bold cyan",
    "time":      "bold yellow",
    "ingredient":"bright_green",
    "step_num":  "bold dodger_blue1",
    "step_text": "white",
    "prompt":    "bold yellow",
    "error":     "bold red",
    "success":   "bold green",
    "muted":     "dim white",
    "brand":     "bold white on dark_green",
}
