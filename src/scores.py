"""Forensic scores used in the course: Beneish M-score, Altman Z'' (emerging markets),
accrual ratio and Benford's Law first-digit test.

Input convention: a DataFrame indexed by fiscal year (ascending) with the columns
named in FIELDS below. Every function is pure, so it can be unit-tested offline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BENFORD = np.log10(1 + 1 / np.arange(1, 10))


def beneish(df: pd.DataFrame) -> pd.DataFrame:
    """8-variable Beneish M-score for every year that has a prior year."""
    p = df.shift(1)
    out = pd.DataFrame(index=df.index)
    gm = (df["revenue"] - df["cogs"]) / df["revenue"]
    gm_p = (p["revenue"] - p["cogs"]) / p["revenue"]

    out["DSRI"] = (df["receivables"] / df["revenue"]) / (p["receivables"] / p["revenue"])
    out["GMI"] = gm_p / gm
    out["AQI"] = (1 - (df["current_assets"] + df["ppe"]) / df["total_assets"]) / (
        1 - (p["current_assets"] + p["ppe"]) / p["total_assets"]
    )
    out["SGI"] = df["revenue"] / p["revenue"]
    out["DEPI"] = (p["depreciation"] / (p["depreciation"] + p["ppe"])) / (
        df["depreciation"] / (df["depreciation"] + df["ppe"])
    )
    # Many Indian statements do not report SG&A; neutral value 1.0 and a flag.
    sgai = (df["sga"] / df["revenue"]) / (p["sga"] / p["revenue"])
    out["sgai_imputed"] = sgai.isna() & p["revenue"].notna()
    out["SGAI"] = sgai.fillna(1.0)
    out["LVGI"] = ((df["current_liabilities"] + df["long_term_debt"]) / df["total_assets"]) / (
        (p["current_liabilities"] + p["long_term_debt"]) / p["total_assets"]
    )
    out["TATA"] = (df["net_income"] - df["cfo"]) / df["total_assets"]

    out["M"] = (
        -4.84
        + 0.920 * out["DSRI"]
        + 0.528 * out["GMI"]
        + 0.404 * out["AQI"]
        + 0.892 * out["SGI"]
        + 0.115 * out["DEPI"]
        - 0.172 * out["SGAI"]
        + 4.679 * out["TATA"]
        - 0.327 * out["LVGI"]
    )
    return out


def altman_z(df: pd.DataFrame) -> pd.Series:
    """Altman Z'' score, emerging-market form (includes the +3.25 constant)."""
    ta = df["total_assets"]
    wc = df["current_assets"] - df["current_liabilities"]
    return (
        6.56 * wc / ta
        + 3.26 * df["retained_earnings"] / ta
        + 6.72 * df["ebit"] / ta
        + 1.05 * df["equity"] / df["total_liabilities"]
        + 3.25
    )


def benford(values, min_n: int = 30) -> dict:
    """First-digit conformity: mean absolute deviation (Nigrini) and chi-square.

    MAD rule of thumb: <0.006 close, <0.012 acceptable, <0.015 marginal, else non-conforming.
    """
    v = np.abs(np.asarray(values, dtype=float))
    v = v[np.isfinite(v) & (v > 0)]
    n = len(v)
    if n < min_n:
        return {"n": n, "mad": np.nan, "chi2": np.nan}
    first = np.clip(np.floor(v / 10 ** np.floor(np.log10(v))).astype(int), 1, 9)
    obs = np.bincount(first, minlength=10)[1:10] / n
    return {
        "n": n,
        "mad": float(np.mean(np.abs(obs - BENFORD))),
        "chi2": float(n * np.sum((obs - BENFORD) ** 2 / BENFORD)),
    }
