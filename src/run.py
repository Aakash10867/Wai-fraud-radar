"""Score every company that has a data file and write results/scores.csv."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .scores import altman_z, beneish, benford

UNIVERSE = Path("config/universe.csv")
DATA_DIR = Path("data/financials")
OUT = Path("results/scores.csv")


def score_company(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("fy").set_index("fy")
    m = beneish(df)
    out = pd.DataFrame(
        {"M": m["M"], "TATA": m["TATA"], "sgai_imputed": m["sgai_imputed"], "Z": altman_z(df)}
    )
    out["benford_mad"] = benford(df.to_numpy().ravel())["mad"]  # company-level
    return out


def main() -> None:
    universe = pd.read_csv(UNIVERSE).fillna("")
    parts = []
    for _, r in universe.iterrows():
        path = DATA_DIR / f"{r['yahoo_ticker']}.csv"
        if not r["yahoo_ticker"] or not path.exists():
            continue
        scored = score_company(pd.read_csv(path)).reset_index()
        scored.insert(0, "company", r["company"])
        scored.insert(1, "group", r["group"])
        event = pd.to_numeric(r["event_year"], errors="coerce")
        scored["years_before_event"] = event - scored["fy"] if pd.notna(event) else pd.NA
        parts.append(scored)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(parts, ignore_index=True).to_csv(OUT, index=False) if parts else pd.DataFrame().to_csv(OUT, index=False)
    print(f"scored {len(parts)} companies -> {OUT}")


if __name__ == "__main__":
    main()
