"""Collect annual financial statements from Yahoo Finance for config/universe.csv.

Never fatal: every failure is written to data/collection_log.csv and an existing
data file is only replaced when a fresh download succeeds.
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pandas as pd

UNIVERSE = Path("config/universe.csv")
OUT_DIR = Path("data/financials")
LOG = Path("data/collection_log.csv")

# Our field name -> Yahoo row labels to try, in order (labels vary by company).
FIELDS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "cogs": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "receivables": ["Accounts Receivable", "Receivables", "Gross Accounts Receivable"],
    "current_assets": ["Current Assets", "Total Current Assets"],
    "ppe": ["Net PPE", "Property Plant Equipment Net"],
    "total_assets": ["Total Assets"],
    "depreciation": [
        "Depreciation And Amortization In Income Statement",
        "Reconciled Depreciation",
        "Depreciation Amortization Depletion",
        "Depreciation And Amortization",
    ],
    "sga": ["Selling General And Administration"],
    "current_liabilities": ["Current Liabilities", "Total Current Liabilities"],
    "long_term_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "retained_earnings": ["Retained Earnings"],
    "ebit": ["EBIT", "Operating Income"],
    "equity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
}


def _pick(frames, names):
    for frame in frames:
        if frame is None or frame.empty:
            continue
        for name in names:
            if name in frame.index:
                return frame.loc[name]
    return None


def tidy(income, balance, cashflow) -> pd.DataFrame:
    """Merge the three Yahoo statements into one table: one row per fiscal year-end."""
    frames = [income, balance, cashflow]
    cols = {}
    for field, names in FIELDS.items():
        series = _pick(frames, names)
        if series is not None:
            cols[field] = pd.to_numeric(series, errors="coerce")
    if not cols:
        return pd.DataFrame()
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.reindex(columns=list(FIELDS))
    df.insert(0, "fy", df.index.year)  # calendar year in which the fiscal year ends
    return df


def fetch(ticker: str) -> pd.DataFrame:
    import yfinance as yf  # imported here so tests run without network libraries

    t = yf.Ticker(ticker)
    return tidy(t.financials, t.balance_sheet, t.cashflow)


def main() -> None:
    universe = pd.read_csv(UNIVERSE).fillna("")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, r in universe.iterrows():
        ticker = str(r["yahoo_ticker"]).strip()
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        status, years = "no_ticker", 0
        if ticker:
            try:
                df = fetch(ticker)
                years = len(df)
                if years < 2:
                    status = "no_data"
                else:
                    df.to_csv(OUT_DIR / f"{ticker}.csv", index=False)
                    status = "ok"
            except Exception as exc:  # network blocks, Yahoo changes, bad ticker
                status = f"error: {type(exc).__name__}"
            time.sleep(1)
        rows.append({"company": r["company"], "ticker": ticker, "status": status,
                     "years": years, "checked_utc": stamp})
        print(rows[-1])
    pd.DataFrame(rows).to_csv(LOG, index=False)


if __name__ == "__main__":
    main()
