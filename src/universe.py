"""Load config/universe.csv and resolve each firm's event year.

A control firm has no event of its own; it inherits the event year of the flagged firm
it is matched to (match_to), so both are scored over the same calendar window.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

UNIVERSE = Path("config/universe.csv")


def load_universe(path: Path = UNIVERSE) -> pd.DataFrame:
    u = pd.read_csv(path).fillna("")
    ev = pd.to_numeric(u["event_year"], errors="coerce")
    own = dict(zip(u["company"], ev))
    u["event_resolved"] = [e if pd.notna(e) else own.get(m, float("nan"))
                           for e, m in zip(ev, u["match_to"])]
    return u
