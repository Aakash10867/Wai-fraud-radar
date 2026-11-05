"""The only module that talks to Gemini.

Model names get retired, so the model is chosen at run time: list what the API key can
use, rank the newest Flash models first, and fall through to the next one if a model
reports "not found / no longer available". Set GEMINI_MODEL to force a specific model.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from pathlib import Path

PROMPT_LOG = Path("logs/prompt_log.jsonl")

SKIP = ("image", "tts", "live", "audio", "robotics", "embedding", "native",
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
        scored.append(("lite" not in low, version, not any(p in low for p in PREVIEW), n))
    return [n for *_, n in sorted(scored, reverse=True)]  # full-size models first, lite as fallback


def is_model_unavailable(exc: Exception) -> bool:
    s = str(exc)
    return "404" in s or "NOT_FOUND" in s or "no longer available" in s


_exhausted: set[str] = set()  # models whose DAILY quota is gone in this process


def is_daily_quota(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s and any(t in s for t in ("perday", "per day", "daily", "limit: 0"))


def is_transient(exc: Exception) -> bool:
    s = str(exc)
    return any(t in s for t in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "high demand", "overloaded",
                                "500 INTERNAL", "502", "504", "DEADLINE_EXCEEDED", "RemoteProtocolError",
                                "Server disconnected", "ReadTimeout", "ConnectError", "timed out", "Connection reset"))


def retry_delay(exc: Exception, default: float = 20.0, cap: float = 45.0) -> float:
    m = re.search(r"retry(?:Delay)?\D{0,12}?(\d+(?:\.\d+)?)\s*s", str(exc), re.I)
    return min(float(m.group(1)) + 1 if m else default, cap)


def candidate_models(client) -> list[str]:
    global _cached
    forced = os.environ.get("GEMINI_MODEL")
    if forced:
        return [forced]
    if _cached is None:
        try:
            listed = [(m.name, list(getattr(m, "supported_actions", None) or []))
                      for m in client.models.list()]
            _cached = rank_models(listed)[:6]
        except Exception as exc:
            print("model listing failed:", str(exc)[:200])
            _cached = []
        _cached = _cached or ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-latest"]
        print("candidate models:", _cached)
    return _cached


def log_call(model: str, purpose: str, prompt: str, response: str, path: Path = PROMPT_LOG) -> None:
    """Append-only prompt logbook (a required deliverable). Long inputs are truncated."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "model": model,
               "purpose": purpose, "prompt_chars": len(prompt), "prompt_head": prompt[:1500],
               "response_head": response[:3000]}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never break a run


def generate(prompt: str, search: bool = False, json_out: bool = False, purpose: str = "") -> str:
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
        if model in _exhausted:
            continue
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt, config=types.GenerateContentConfig(**cfg))
                print("gemini model used:", model)
                log_call(model, purpose, prompt, resp.text or "")
                return resp.text or ""
            except Exception as exc:
                last = exc
                if is_model_unavailable(exc):
                    break  # retired model: go straight to the next one
                if is_daily_quota(exc):
                    _exhausted.add(model)  # waiting will not help: use another model now
                    break
                if not is_transient(exc):
                    raise
                if attempt == 0:
                    time.sleep(retry_delay(exc))  # busy or rate-limited: wait once, then move on
                else:
                    break
    raise last or RuntimeError("no Gemini model available")
