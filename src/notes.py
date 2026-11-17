"""Analyst notes: what the score says, and what to check first.

Two layers. (1) Rules turn the weakest pillars into concrete checks; this always works and is
fully traceable. (2) Gemini writes a short stakeholder note from the same facts. The note is
accepted only if every number in it can be found in the facts it was given; otherwise the rule
based note is used. Notes are cached by a hash of their facts, so unchanged companies cost
nothing on later runs.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

import pandas as pd

from .guards import keep_signal
from .integrity import PILLARS, THRESHOLDS, risk

INTEGRITY = Path("results/integrity.csv")
SIGNALS = Path("data/signals")
OUT = Path("results/notes.json")

METRIC_LABEL = {k: v[2] for k, v in THRESHOLDS.items()}

CHECKS = {
    "TATA": "Reconcile reported profit to operating cash flow; list the non-cash gains and working-capital build-up behind the accruals",
    "M": "Review the Beneish indices (receivables, gross margin, asset quality, sales growth) and identify which one drives the score",
    "CFO_NI": "Trace why profit is not turning into cash: receivable ageing, unbilled revenue, inventory build-up, advances paid",
    "CFO_REV": "Check operating cash flow against revenue over five years and read the cash-flow statement notes",
    "LEV": "Map all borrowings, guarantees and off-balance-sheet obligations against equity; confirm lender-wise exposure",
    "ICR": "Test whether operating profit covers interest; check capitalised interest and rollover of short-term debt",
    "CUR": "Check short-term liquidity: maturities due within a year against cash and receivables that are actually collectable",
    "Z": "Assess distress risk: working capital, retained earnings and profitability trend behind the low Z-score",
    "ROA": "Check whether operating profit is falling and what the segment results say about it",
    "GROWTH": "Compare revenue growth with receivables and cash collection; large swings need a customer-level check",
    "audit_flags": "Read the auditor's report and notes on the flagged items; confirm what management did about each",
}

PILLAR_METRICS = {k: v[2] for k, v in PILLARS.items()}


def latest_row(df: pd.DataFrame) -> pd.Series:
    d = df[df["score"].notna() & (df["coverage"] >= 0.5)].sort_values("fy")
    return d.iloc[-1] if len(d) else df.sort_values("fy").iloc[-1]


def red_flags(company: str) -> list[dict]:
    """Verified, context-filtered flags from the newest extracted annual report."""
    best = None
    for f in SIGNALS.glob("*.json"):
        d = json.loads(f.read_text())
        if d.get("company") == company and (best is None or d["report_fy"] > best["report_fy"]):
            best = d
    if not best:
        return []
    return [{"type": s["type"], "quote": s.get("quote", ""), "report_fy": best["report_fy"]}
            for s in best.get("signals", []) if s.get("present") and keep_signal(s)]


def rule_checks(row: pd.Series, flags: list[dict], top: int = 3) -> list[str]:
    scored = []
    for key, (label, weight, names) in PILLARS.items():
        r = row.get(f"risk_{key}")
        if pd.notna(r) and r >= 25:
            if key == "audit_flags":
                scored.append((r, CHECKS["audit_flags"]))
            else:
                worst = max(names, key=lambda n: risk(row.get(n), *THRESHOLDS[n][:2]) if pd.notna(row.get(n)) else -1)
                scored.append((r, CHECKS[worst]))
    scored.sort(reverse=True)
    out = [c for _, c in scored[:top]]
    return out or ["Nothing above the concern level; keep to the routine annual review"]


def facts(company: str, row: pd.Series, flags: list[dict]) -> dict:
    keep = ["M", "TATA", "Z", "CFO_NI", "LEV", "ICR", "ROA", "GROWTH"]
    f = {"company": company, "fiscal_year": int(row["fy"]), "integrity_score": round(float(row["score"]), 1),
         "band": row["band"], "coverage_pct": round(float(row["coverage"]) * 100)}
    f["measures"] = {k: round(float(row[k]), 2) for k in keep if pd.notna(row.get(k))}
    f["pillar_risk_0_to_100"] = {PILLARS[k][0]: round(float(row[f"risk_{k}"])) for k in PILLARS
                                 if pd.notna(row.get(f"risk_{k}"))}
    f["red_flags"] = [{"type": x["type"], "quote": x["quote"][:200]} for x in flags]
    return f


def numbers_in(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", text)]


def numbers_supported(text: str, fact_obj: dict) -> bool:
    """Every number in the note must match some number in the facts (rounding allowed)."""
    pool: list[float] = []

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, (int, float)):
            pool.extend([float(o), float(o) * 100])
        elif isinstance(o, str):
            pool.extend(numbers_in(o))

    walk(fact_obj)
    return all(any(math.isclose(n, p, abs_tol=max(0.06, abs(p) * 0.02)) for p in pool)
               for n in numbers_in(text))


PROMPT = """You are writing a short note for a forensic analyst at a bank who must decide whether to open a forensic review of a borrower.
Use ONLY the facts below. Do not add any number that is not in the facts. Do not accuse the company of fraud; describe signals.
Return JSON: {{"headline": "<max 18 words>", "summary": "<max 80 words: what stands out, and why it matters for the decision>"}}.
Facts:
{facts}"""


def narrative(fact_obj: dict) -> dict | None:
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from .llm import generate

    try:
        raw = generate(PROMPT.format(facts=json.dumps(fact_obj, indent=1)), json_out=True, purpose="analyst note")
        d = json.loads(raw)
        d = d[0] if isinstance(d, list) and d else d
        text = f"{d.get('headline', '')} {d.get('summary', '')}"
        if d.get("headline") and d.get("summary") and numbers_supported(text, fact_obj):
            return {"headline": d["headline"], "summary": d["summary"]}
    except Exception as exc:  # quota or bad JSON: fall back to the rule-based note
        print("note skipped:", type(exc).__name__, str(exc)[:120])
    return None


def fallback(fact_obj: dict, checks: list[str]) -> dict:
    f = fact_obj
    weakest = sorted(f["pillar_risk_0_to_100"].items(), key=lambda kv: -kv[1])[:2]
    wk = " and ".join(f"{k.lower()} (risk {v})" for k, v in weakest) if weakest else "no pillar"
    return {"headline": f"{f['company']}: {f['band']} (score {f['integrity_score']})",
            "summary": f"Integrity score {f['integrity_score']} for FY{f['fiscal_year']}. The weakest areas are {wk}. "
                       f"Score covers {f['coverage_pct']}% of the weighted evidence."}


def main() -> None:
    if not INTEGRITY.exists() or INTEGRITY.stat().st_size < 5:
        return
    cache = json.loads(OUT.read_text()) if OUT.exists() else {}
    df = pd.read_csv(INTEGRITY)
    notes = {}
    start, misses = time.time(), 0   # stop asking Gemini after 3 misses in a row or 8 minutes
    for company, g in df.groupby("company"):
        row = latest_row(g)
        flags = red_flags(company)
        f = facts(company, row, flags)
        key = hashlib.sha1(json.dumps(f, sort_keys=True).encode()).hexdigest()[:12]
        old = cache.get(company)
        if old and old.get("key") == key:
            notes[company] = old
            continue
        ai = narrative(f) if misses < 3 and time.time() - start < 480 else None
        misses = 0 if ai else misses + 1
        base = ai or fallback(f, [])
        notes[company] = {"key": key, "fy": f["fiscal_year"], "ai_written": ai is not None, **base,
                          "check_first": rule_checks(row, flags), "red_flags": flags}
        print(company, "AI note" if ai else "rule note")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({**cache, **notes}, indent=1, ensure_ascii=False))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(notes, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
