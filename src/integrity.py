"""Fraud Radar Integrity Score (0-100, higher = cleaner).

Built for one user: a forensic analyst who must decide which borrowers or investees deserve
a forensic review, and what to check first. Six pillars, each scored from 0 (no concern) to
100 (maximum concern) by linear interpolation between a "good" and a "bad" level of each
measure. Pillar risks are combined with fixed weights; the score is 100 minus the weighted
risk. Where a measure is missing the pillar uses the measures it has, and where a whole
pillar is missing the remaining weights are rescaled; the share of weight that was actually
available is reported as coverage so a thin score is never mistaken for a full one.

The good/bad levels come from the course models (M-score cut-off, Z-score zones) and common
credit-analysis rules of thumb. They are judgement, set before looking at results, and are
all listed in THRESHOLDS so they can be challenged and changed in one place.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .scores import altman_z, beneish

# metric -> (good level, bad level, what it measures)
THRESHOLDS = {
    "TATA": (0.0, 0.10, "Total accruals / assets: profit not backed by cash"),
    "M": (-2.5, -1.0, "Beneish M-score; the course cut-off is -1.78"),
    "CFO_NI": (1.0, 0.2, "Operating cash flow / net profit (when profit is positive)"),
    "CFO_REV": (0.08, 0.0, "Operating cash flow / revenue"),
    "LEV": (1.0, 5.0, "Total liabilities / equity"),
    "ICR": (5.0, 1.0, "EBIT / interest expense (interest cover)"),
    "CUR": (1.5, 0.8, "Current assets / current liabilities"),
    "Z": (2.6, 1.1, "Altman Z-score; below 1.1 is the distress zone"),
    "ROA": (0.10, 0.0, "EBIT / total assets"),
    "GROWTH": (0.05, -0.15, "Year-on-year revenue growth"),
}

PILLARS = {
    "earnings_quality": ("Earnings quality", 25, ["TATA", "M"]),
    "cash_conversion": ("Cash conversion", 20, ["CFO_NI", "CFO_REV"]),
    "leverage": ("Leverage and coverage", 15, ["LEV", "ICR", "CUR"]),
    "distress": ("Financial distress", 15, ["Z"]),
    "operating": ("Operating performance", 10, ["ROA", "GROWTH"]),
    "audit_flags": ("Audit and governance red flags (AI)", 15, []),
}

TEXT_RISK_PER_POINT = 34  # one verified, context-filtered red-flag point = 34 risk (3 points = max)

BANDS = (  # lower bound of score, label, action for the analyst
    (75, "Clear", "No action; routine annual review"),
    (60, "Monitor", "Keep on the watchlist and re-score when the next results are filed"),
    (45, "Targeted review", "Ask management to explain the flagged items before the next credit decision"),
    (0, "Open forensic review", "Open a forensic review now and start with the items listed under 'check first'"),
)


def col(df: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(df[name], errors="coerce") if name in df else pd.Series(np.nan, index=df.index)


def metrics(df: pd.DataFrame) -> pd.DataFrame:
    """All measures for every year. df: indexed by consecutive fiscal years, ascending."""
    m = beneish(df)
    out = pd.DataFrame(index=df.index)
    out["M"], out["TATA"], out["Z"] = m["M"], m["TATA"], altman_z(df)
    ni, cfo, rev = col(df, "net_income"), col(df, "cfo"), col(df, "revenue")
    ratio = cfo / ni.where(ni > 0)
    ratio[(ni <= 0) & (cfo >= 0)] = 0.6   # loss but cash-positive: mild concern
    ratio[(ni <= 0) & (cfo < 0)] = 0.0    # loss and cash burn: maximum concern
    out["CFO_NI"] = ratio
    out["CFO_REV"] = cfo / rev
    out["LEV"] = col(df, "total_liabilities") / col(df, "equity").where(col(df, "equity") > 0)
    interest = col(df, "interest_expense").abs()
    out["ICR"] = (col(df, "ebit") / interest.where(interest > 0)).clip(upper=50)
    out["CUR"] = col(df, "current_assets") / col(df, "current_liabilities")
    out["ROA"] = col(df, "ebit") / col(df, "total_assets")
    out["GROWTH"] = rev / rev.shift(1) - 1
    return out


def risk(value: float, good: float, bad: float) -> float:
    """0 at the good level, 100 at the bad level, linear in between, clipped."""
    if pd.isna(value):
        return np.nan
    return float(np.clip((value - good) / (bad - good), 0, 1) * 100)


def text_risk(points) -> float:
    return np.nan if pd.isna(points) else float(min(100, TEXT_RISK_PER_POINT * points))


def band(score: float) -> tuple[str, str]:
    for floor, label, action in BANDS:
        if score >= floor:
            return label, action
    return BANDS[-1][1:]


def score_year(row: pd.Series, text_points=np.nan) -> dict:
    """Pillar risks, integrity score, coverage and band for one company-year."""
    res, used, total = {}, 0.0, 0.0
    for key, (label, weight, names) in PILLARS.items():
        if key == "audit_flags":
            r = text_risk(text_points)
        else:
            parts = [risk(row.get(n), *THRESHOLDS[n][:2]) for n in names]
            parts = [p for p in parts if not np.isnan(p)]
            r = float(np.mean(parts)) if parts else np.nan
        res[f"risk_{key}"] = r
        if not np.isnan(r):
            used += weight
            total += weight * r
    res["coverage"] = used / sum(w for _, w, _ in PILLARS.values())
    res["score"] = float(100 - total / used) if used else np.nan
    if used:
        res["band"], res["action"] = band(res["score"])
    else:
        res["band"], res["action"] = "No data", "Not enough data to score"
    return res


def score_company(df: pd.DataFrame, text_by_year: dict | None = None) -> pd.DataFrame:
    """df: one company's financials with an 'fy' column. text_by_year: {fy: context-filtered points}."""
    df = df.sort_values("fy").set_index("fy")
    df = df.reindex(range(int(df.index.min()), int(df.index.max()) + 1))
    met = metrics(df)
    rows = []
    for fy, r in met.iterrows():
        rows.append({"fy": fy, **r.to_dict(), **score_year(r, (text_by_year or {}).get(fy, np.nan))})
    return pd.DataFrame(rows)
