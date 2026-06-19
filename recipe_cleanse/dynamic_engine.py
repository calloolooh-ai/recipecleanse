"""
dynamic_engine.py — AI semantic parsing layer.

Accepts raw, unstructured webpage text and returns a clean, validated
recipe dict by calling either the Google Gemini API or a local Ollama server.

The strict system prompt in config.py locks the model to return only
machine-parseable JSON — no prose, no fences, no apologies.
"""

import json
import re

from recipe_cleanse.config import (
    AI_BACKEND,
    AI_SYSTEM_PROMPT,
    GROQ_API_KEY,
    GROQ_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)


# ── Public Entry Point ────────────────────────────────────────────────────────

def parse_with_ai(raw_text: str) -> dict:
    """
    Send raw webpage text to the configured AI backend and return a
    structured recipe dict.

    Args:
        raw_text: Plain text extracted from a recipe page (stripped of HTML).

    Returns:
        dict with keys: title, prep_time, cook_time, total_time,
                        servings, ingredients (list), instructions (list)

    Raises:
        RuntimeError: AI call failed or returned unparseable output.
        ValueError:   Unknown AI_BACKEND configured.
    """
    if AI_BACKEND == "groq":
        return _parse_groq(raw_text)

    if AI_BACKEND == "openai":
        return _parse_openai(raw_text)

    if AI_BACKEND == "google":
        return _parse_google(raw_text)

    if AI_BACKEND == "ollama":
        return _parse_ollama(raw_text)

    raise ValueError(
        f"Unknown AI_BACKEND='{AI_BACKEND}'. "
        "Valid options: 'openai' (default), 'google', or 'ollama' (local dev)."
    )


# ── Groq Backend ─────────────────────────────────────────────────────────────

def _parse_groq(raw_text: str) -> dict:
    """
    Call Groq via the openai SDK pointed at Groq's base URL.
    Groq is OpenAI API-compatible — same SDK, different endpoint + key.
    Free tier: ~14,400 req/day at console.groq.com
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "Package 'openai' is not installed.\n"
            "Fix: pip install openai"
        )

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Add it to Vercel → Settings → Environment Variables.\n"
            "Get a free key at: https://console.groq.com"
        )

    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract the complete recipe from this webpage text:\n\n{raw_text}",
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise RuntimeError(f"Groq API error: {type(exc).__name__}: {exc}") from exc

    return _parse_and_validate_json(response.choices[0].message.content)


# ── OpenAI Backend ───────────────────────────────────────────────────────────

def _parse_openai(raw_text: str) -> dict:
    """
    Call OpenAI via the official openai SDK.
    Uses JSON mode to guarantee parseable output.
    Get a key at: https://platform.openai.com/api-keys
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "Package 'openai' is not installed.\n"
            "Fix: pip install openai"
        )

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Add it to Vercel → Settings → Environment Variables.\n"
            "Get a key at: https://platform.openai.com/api-keys"
        )

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract the complete recipe from this webpage text:\n\n{raw_text}",
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},  # OpenAI JSON mode
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI API error: {type(exc).__name__}: {exc}") from exc

    return _parse_and_validate_json(response.choices[0].message.content)


# ── Google GenAI Backend ──────────────────────────────────────────────────────

def _parse_google(raw_text: str) -> dict:
    """
    Call Google Gemini via the google-genai SDK (the current unified SDK).
    Free tier key: https://aistudio.google.com/app/apikey
    Install:       pip install google-genai
    """
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise RuntimeError(
            "Package 'google-genai' is not installed.\n"
            "Fix: pip install google-genai"
        )

    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. "
            "Add it to your .env file: GOOGLE_API_KEY=your_key_here\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )

    client = genai.Client(api_key=GOOGLE_API_KEY)

    prompt = f"Extract the complete recipe from this webpage text:\n\n{raw_text}"
    try:
        response = client.models.generate_content(
            model=GOOGLE_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=AI_SYSTEM_PROMPT,
                temperature=0,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        # Wrap Google API errors (PermissionDenied, quota, network, etc.)
        raise RuntimeError(f"Gemini API error: {type(exc).__name__}: {exc}") from exc

    return _parse_and_validate_json(response.text)


# ── Ollama (Local) Backend ────────────────────────────────────────────────────

def _parse_ollama(raw_text: str) -> dict:
    """
    Call a locally running Ollama server.
    Install Ollama: https://ollama.ai
    Pull model:     ollama pull llama3.2
    """
    try:
        import ollama
    except ImportError:
        raise RuntimeError(
            "Package 'ollama' is not installed.\n"
            "Fix: pip install ollama\n"
            "Then install Ollama server: https://ollama.ai"
        )

    client = ollama.Client(host=OLLAMA_BASE_URL)

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract the complete recipe from this webpage text:\n\n{raw_text}",
                },
            ],
            options={
                "temperature": 0,       # Deterministic structured output
                "num_predict": 2048,    # Enough tokens for a full recipe
            },
            format="json",              # Ollama JSON mode
        )
    except Exception as exc:
        raise RuntimeError(
            f"Ollama request failed: {exc}\n"
            f"Is Ollama running at {OLLAMA_BASE_URL}? "
            f"Is model '{OLLAMA_MODEL}' pulled? (ollama pull {OLLAMA_MODEL})"
        )

    return _parse_and_validate_json(response["message"]["content"])


# ── JSON Parsing & Validation ─────────────────────────────────────────────────

def _parse_and_validate_json(text: str) -> dict:
    """
    Robustly extract and validate a recipe JSON object from an LLM response.

    Models occasionally wrap JSON in markdown fences despite instructions.
    This handles that gracefully before raising on genuine parse errors.
    """
    cleaned = text.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n?```\s*$",          "", cleaned)
    cleaned = cleaned.strip()

    # Attempt direct parse first
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: find the first {...} block in the response
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise RuntimeError(
                "AI returned no parseable JSON. "
                f"Raw response (first 400 chars):\n{text[:400]}"
            )
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"AI JSON parse error: {exc}\nRaw: {text[:400]}")

    # ── Field validation & normalisation ─────────────────────────────────
    required = {"title", "ingredients", "instructions"}
    missing  = required - set(data.keys())
    if missing:
        raise RuntimeError(
            f"AI response is missing required fields: {missing}. "
            f"Got fields: {list(data.keys())}"
        )

    # Coerce list fields — some models return a single string instead of a list
    for list_field in ("ingredients", "instructions"):
        if isinstance(data[list_field], str):
            # Split on newlines as a best-effort recovery
            data[list_field] = [
                line.strip()
                for line in data[list_field].splitlines()
                if line.strip()
            ]
        elif not isinstance(data[list_field], list):
            data[list_field] = [str(data[list_field])]

    # Guarantee optional string fields exist
    for str_field in ("prep_time", "cook_time", "total_time", "servings"):
        data.setdefault(str_field, "")
        if data[str_field] is None:
            data[str_field] = ""

    return data
