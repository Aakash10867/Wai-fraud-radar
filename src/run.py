"""Score every company and write results/scores.csv.

Financials come from Yahoo (data/financials) and from annual reports
(data/reports_fin). Yahoo wins where both cover a year; reports fill older years.
All values are in rupees so ratios stay consistent across sources.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .extract import slug
from .scores import altman_z, beneish, benford

UNIVERSE = Path("config/universe.csv")
YAHOO_DIR = Path("data/financials")
REPORT_DIR = Path("data/reports_fin")
OUT = Path("results/scores.csv")


def load_financials(ticker: str, company: str) -> pd.DataFrame | None:
    parts = []
    y = YAHOO_DIR / f"{ticker}.csv"
    if ticker and y.exists():
        parts.append(pd.read_csv(y).assign(source="yahoo"))
    r = REPORT_DIR / f"{slug(company)}.csv"
    if r.exists():
        parts.append(pd.read_csv(r))
    if not parts:
        return None
    df = pd.concat(parts, ignore_index=True)
    return df.drop_duplicates("fy", keep="first").sort_values("fy").reset_index(drop=True)


def score_company(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("fy").set_index("fy")
    # A missing year must not let M-score compare two non-adjacent years.
    df = df.reindex(range(int(df.index.min()), int(df.index.max()) + 1))
    m = beneish(df)
    out = pd.DataFrame(
        {"M": m["M"], "TATA": m["TATA"], "sgai_imputed": m["sgai_imputed"], "Z": altman_z(df)}
    )
    numeric = df.drop(columns=["source"], errors="ignore").select_dtypes("number")
    out["benford_mad"] = benford(numeric.to_numpy().ravel())["mad"]  # company-level
    return out


def main() -> None:
    universe = pd.read_csv(UNIVERSE).fillna("")
    parts = []
    for _, r in universe.iterrows():
        df = load_financials(str(r["yahoo_ticker"]).strip(), r["company"])
        if df is None:
            continue
        scored = score_company(df).reset_index()
        scored.insert(0, "company", r["company"])
        scored.insert(1, "group", r["group"])
        event = pd.to_numeric(r["event_year"], errors="coerce")
        scored["years_before_event"] = event - scored["fy"] if pd.notna(event) else pd.NA
        parts.append(scored)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()).to_csv(OUT, index=False)
    print(f"scored {len(parts)} companies -> {OUT}")


if __name__ == "__main__":
    main()
