"""Annual-report extraction with Gemini.

Design: the LLM is an extractor, never the judge. For each report it returns
(1) fixed-type text signals, each with a verbatim quote, and (2) the statements for the
report year and the prior year. Every quote is checked against the PDF text and
unverifiable signals are dropped (hallucination guard). Financials must pass a
balance-sheet identity check or they are flagged and not used for scoring.

Never fatal: failures are logged to data/extraction_log.csv.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import time
from pathlib import Path

import pandas as pd

from .collect import FIELDS

REPORTS = Path("config/reports.csv")  # optional manual overrides
DISCOVERED = Path("data/report_urls.csv")  # written by src/discover.py
SIGNAL_DIR = Path("data/signals")
FIN_DIR = Path("data/reports_fin")
LOG = Path("data/extraction_log.csv")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

SIGNAL_TYPES = [
    "auditor_qualified_opinion",
    "auditor_emphasis_of_matter",
    "going_concern_doubt",
    "material_related_party_transactions",
    "auditor_resigned_or_changed",
    "delayed_or_restated_results",
    "loan_or_fund_diversion_alleged",
    "internal_control_weakness",
]

UNIT_FACTOR = {"rupees": 1.0, "lakh": 1e5, "crore": 1e7, "million": 1e6}

KEYWORDS = [
    "independent auditor", "auditor's report", "auditors' report", "key audit matter",
    "emphasis of matter", "qualified opinion", "going concern", "related party",
    "balance sheet", "statement of profit and loss", "cash flow statement",
    "internal financial controls", "resignation of", "restate",
]

PROMPT = """You are extracting facts from an Indian listed company's annual report text.
Return ONLY JSON, no commentary, with this exact shape:
{{
 "fy": <fiscal year-end calendar year of THIS report, e.g. 2019 for FY2018-19>,
 "unit": "<rupees|lakh|crore|million - the unit the statements are presented in>",
 "signals": [{{"type": "<one of {types}>", "present": true/false, "quote": "<VERBATIM text copied from the report that proves it; empty if present is false>"}}],
 "current": {{{fields}}},
 "prior": {{{fields}}}
}}
Rules: include every signal type once. A quote must be copied exactly, never paraphrased.
"current" is the report year, "prior" the comparative year, using the standalone or consolidated
statements consistently. Use null for any field you cannot find; never guess. Costs and
liabilities are positive numbers. Fields: {field_list}.

REPORT TEXT:
{text}
"""


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def norm(s: str) -> str:
    s = re.sub(r"[‘’“”\"'`]", "", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def select_pages(pages: list[str], cap: int = 70) -> str:
    """Keep the pages most likely to hold the auditor report, statements and notes."""
    scored = []
    for i, p in enumerate(pages):
        low = p.lower()
        scored.append((sum(low.count(k) for k in KEYWORDS), i))
    keep = sorted(i for s, i in sorted(scored, reverse=True)[:cap] if s > 0)
    return "\n\n".join(f"[page {i + 1}]\n{pages[i]}" for i in keep)


def verify_signals(signals: list[dict], text: str) -> tuple[list[dict], int]:
    """Keep a present signal only if its quote really appears in the report text."""
    haystack = norm(text)
    kept, dropped = [], 0
    for s in signals or []:
        if s.get("type") not in SIGNAL_TYPES:
            dropped += 1
            continue
        if not s.get("present"):
            kept.append({"type": s["type"], "present": False, "quote": ""})
            continue
        q = norm(s.get("quote", ""))
        if len(q) >= 20 and q in haystack:
            kept.append({"type": s["type"], "present": True, "quote": s["quote"]})
        else:
            dropped += 1
    return kept, dropped


def balance_ok(year: dict, tol: float = 0.02) -> bool:
    ta, eq, tl = (year.get(k) for k in ("total_assets", "equity", "total_liabilities"))
    if not all(isinstance(v, (int, float)) for v in (ta, eq, tl)) or not ta:
        return False
    return abs(ta - (eq + tl)) / abs(ta) <= tol


def parse_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def to_rupees(year: dict, unit: str) -> dict:
    f = UNIT_FACTOR[unit]
    return {k: (v * f if isinstance(v, (int, float)) else None) for k, v in year.items() if k in FIELDS}


def build_prompt(text: str) -> str:
    fields = ", ".join(f'"{k}": <number|null>' for k in FIELDS)
    return PROMPT.format(types=", ".join(SIGNAL_TYPES), fields=fields,
                         field_list=", ".join(FIELDS), text=text[:600_000])


def call_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return resp.text


def download_pdf_pages(url: str) -> list[str]:
    import requests
    from pypdf import PdfReader

    buf, size = io.BytesIO(), 0
    with requests.get(url, timeout=120, stream=True,
                      headers={"User-Agent": "Mozilla/5.0 (academic research)"}) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1 << 20):
            size += len(chunk)
            if size > 60 << 20:
                raise ValueError("file too large")
            buf.write(chunk)
    if buf.getvalue()[:5] != b"%PDF-":
        raise ValueError("not a PDF")
    reader = PdfReader(buf)
    return [(p.extract_text() or "") for p in reader.pages]


def process(company: str, fy: int, url: str) -> dict:
    pages = download_pdf_pages(url)
    text = select_pages(pages)
    if not text.strip():
        raise ValueError("no readable text (scanned PDF?)")
    data = parse_response(call_gemini(build_prompt(text)))
    signals, dropped = verify_signals(data.get("signals", []), text)
    unit = data.get("unit") if data.get("unit") in UNIT_FACTOR else None
    result = {"company": company, "report_fy": fy, "url": url, "unit": unit,
              "signals": signals, "dropped_unverified": dropped, "financials": []}
    for key in ("current", "prior"):
        year = data.get(key) or {}
        fy_year = fy if key == "current" else fy - 1
        if unit and balance_ok(year):
            result["financials"].append({"fy": fy_year, **to_rupees(year, unit), "source": "annual_report"})
        else:
            result.setdefault("rejected", []).append(f"{key}: failed balance check or unit missing")
    return result


def rebuild_financials() -> None:
    FIN_DIR.mkdir(parents=True, exist_ok=True)
    by_company: dict[str, list[dict]] = {}
    for f in SIGNAL_DIR.glob("*.json"):
        d = json.loads(f.read_text())
        by_company.setdefault(slug(d["company"]), []).extend(d.get("financials", []))
    for name, rows in by_company.items():
        if rows:
            df = pd.DataFrame(rows).drop_duplicates("fy", keep="first").sort_values("fy")
            df.to_csv(FIN_DIR / f"{name}.csv", index=False)


def load_report_list() -> pd.DataFrame:
    """Manual overrides (config/reports.csv) first, then auto-discovered links."""
    frames = []
    if REPORTS.exists():
        frames.append(pd.read_csv(REPORTS))
    if DISCOVERED.exists():
        d = pd.read_csv(DISCOVERED)
        frames.append(d[d["status"] == "ok"][["company", "fy", "url"]])
    if not frames:
        return pd.DataFrame(columns=["company", "fy", "url"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(["company", "fy"], keep="first")


def main() -> None:
    reports = load_report_list()
    if reports.empty:
        return
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = []
    for _, r in reports.fillna("").iterrows():
        if not r["url"]:
            continue
        out = SIGNAL_DIR / f"{slug(r['company'])}_{int(r['fy'])}.json"
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if out.exists():
            status = "cached"
        else:
            try:
                out.write_text(json.dumps(process(r["company"], int(r["fy"]), r["url"]), indent=1))
                status = "ok"
            except Exception as exc:
                status = f"error: {type(exc).__name__}: {str(exc)[:120]}"
            time.sleep(2)
        log.append({"company": r["company"], "fy": r["fy"], "status": status, "checked_utc": stamp})
        print(log[-1])
    rebuild_financials()
    if log:
        pd.DataFrame(log).to_csv(LOG, index=False)


if __name__ == "__main__":
    main()
