"""The only module that talks to Gemini.

Model names get retired, so the model is chosen at run time: list what the API key can
use, rank the newest Flash models first, and fall through to the next one if a model
reports "not found / no longer available". Set GEMINI_MODEL to force a specific model.
"""
from __future__ import annotations

import os
import re

SKIP = ("lite", "image", "tts", "live", "audio", "robotics", "embedding", "native",
        "computer", "imagen", "veo", "gemma", "learnlm", "aqa")
PREVIEW = ("preview", "exp", "thinking")

_cached: list[str] | None = None


def rank_models(models) -> list[str]:
    """models: iterable of (name, supported_actions). Newest Flash first; stable beats preview."""
    scored = []
    for name, actions in models:
        n = name.replace("models/", "")
        low = n.lower()
        if "flash" not in low or any(s in low for s in SKIP):
            continue
        if actions and "generateContent" not in actions:
            continue
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", low)
        version = float(m.group(1)) if m else 0.0
        scored.append((version, not any(p in low for p in PREVIEW), n))
    return [n for _, _, n in sorted(scored, reverse=True)]


def is_model_unavailable(exc: Exception) -> bool:
    s = str(exc)
    return "404" in s or "NOT_FOUND" in s or "no longer available" in s


def candidate_models(client) -> list[str]:
    global _cached
    forced = os.environ.get("GEMINI_MODEL")
    if forced:
        return [forced]
    if _cached is None:
        try:
            listed = [(m.name, list(getattr(m, "supported_actions", None) or []))
                      for m in client.models.list()]
            _cached = rank_models(listed)[:4]
        except Exception:
            _cached = []
        _cached = _cached or ["gemini-flash-latest"]
    return _cached


def generate(prompt: str, search: bool = False, json_out: bool = False) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg: dict = {"temperature": 0}
    if json_out:
        cfg["response_mime_type"] = "application/json"
    if search:
        cfg["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    last: Exception | None = None
    for model in candidate_models(client):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(**cfg))
            print("gemini model used:", model)
            return resp.text or ""
        except Exception as exc:
            last = exc
            if not is_model_unavailable(exc):
                raise
    raise last or RuntimeError("no Gemini model available")
