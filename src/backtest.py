"""Risk points, back-test and watchlist.

Design: weights are fixed in advance from the forensic literature and the course, NOT fitted
to this tiny sample, so there is nothing to overfit. Numbers-only uses the financial rules;
numbers+text adds points for verified text signals. Benford's MAD is reported but excluded
from points because it is computed over all of a firm's years (it would leak the future).

Evaluation window: for a flagged firm with event year E, fiscal years E-3..E-1 are positive
and the same years of its matched controls are negative. Year E itself is excluded.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .guards import keep_signal

SCORES = Path("results/scores.csv")
SIGNAL_DIR = Path("data/signals")
OUT_JSON = Path("results/backtest.json")
OUT_MD = Path("results/backtest.md")
WATCHLIST = Path("results/watchlist.csv")

THRESHOLD = 3  # points needed to raise a flag; fixed in advance

TEXT_WEIGHTS = {
    "auditor_qualified_opinion": 2,
    "going_concern_doubt": 2,
    "loan_or_fund_diversion_alleged": 2,
    "auditor_emphasis_of_matter": 1,
    "material_related_party_transactions": 1,
    "auditor_resigned_or_changed": 1,
    "delayed_or_restated_results": 1,
    "internal_control_weakness": 1,
}


def numeric_points(r) -> int:
    pts = 0
    if pd.notna(r.get("M")) and r["M"] > -1.78:
        pts += 2  # Beneish 8-variable cut-off
    if pd.notna(r.get("Z")) and r["Z"] < 1.1:
        pts += 1  # Altman Z-score distress zone
    if pd.notna(r.get("TATA")) and r["TATA"] > 0.031:
        pts += 1  # accruals above the manipulator mean in Beneish (1999)
    return pts


def text_points(signals: list[dict], strict: bool = False) -> tuple[int, list[str]]:
    """strict=True applies the post-hoc v2 meaning rules from src/guards.py."""
    flags = [s["type"] for s in signals if s.get("present") and s.get("type") in TEXT_WEIGHTS
             and (not strict or keep_signal(s))]
    return sum(TEXT_WEIGHTS[f] for f in flags), flags


def auc(pos, neg) -> float:
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def load_text(signal_dir: Path = SIGNAL_DIR) -> pd.DataFrame:
    rows = []
    for f in sorted(signal_dir.glob("*.json")):
        d = json.loads(f.read_text())
        pts, flags = text_points(d.get("signals", []))
        pts2, _ = text_points(d.get("signals", []), strict=True)
        quotes = [s["quote"] for s in d.get("signals", []) if s.get("present") and s.get("quote")]
        rows.append({"company": d["company"], "fy": d["report_fy"], "text_pts": pts, "text_pts_v2": pts2,
                     "flags": ";".join(flags), "quote": quotes[0] if quotes else ""})
    return pd.DataFrame(rows, columns=["company", "fy", "text_pts", "text_pts_v2", "flags", "quote"])


def build_table(scores: pd.DataFrame, text: pd.DataFrame) -> pd.DataFrame:
    t = scores.merge(text, on=["company", "fy"], how="left")
    if "text_pts_v2" not in t:
        t["text_pts_v2"] = 0
    t["text_pts"] = t["text_pts"].fillna(0).astype(int)
    t["text_pts_v2"] = t["text_pts_v2"].fillna(0).astype(int)
    t[["flags", "quote"]] = t[["flags", "quote"]].fillna("")
    t["num_pts"] = t.apply(numeric_points, axis=1)
    t["total_pts"] = t["num_pts"] + t["text_pts"]
    t["total_pts_v2"] = t["num_pts"] + t["text_pts_v2"]
    yb = pd.to_numeric(t["years_before_event"], errors="coerce")
    in_window = yb.between(1, 3)
    t["label"] = np.where(in_window & (t["group"] == "flagged"), 1.0,
                          np.where(in_window & (t["group"] == "control"), 0.0, np.nan))
    return t


def evaluate(t: pd.DataFrame) -> dict:
    ev = t[t["label"].notna()]
    out = {"threshold": THRESHOLD,
           "flagged_firms": int(ev.loc[ev.label == 1, "company"].nunique()),
           "control_firms": int(ev.loc[ev.label == 0, "company"].nunique()),
           "firm_years": int(len(ev))}
    for name, col in (("numbers_only", "num_pts"), ("numbers_plus_text", "total_pts"),
                      ("numbers_plus_text_v2", "total_pts_v2")):
        res = {"auc": auc(ev.loc[ev.label == 1, col], ev.loc[ev.label == 0, col])}
        by_firm = ev.groupby(["group", "company"])[col].max()
        flagged = by_firm.get("flagged", pd.Series(dtype=float))
        control = by_firm.get("control", pd.Series(dtype=float))
        res["detection_rate"] = float((flagged >= THRESHOLD).mean()) if len(flagged) else float("nan")
        res["false_positive_rate"] = float((control >= THRESHOLD).mean()) if len(control) else float("nan")
        leads = []
        for company, g in ev[ev.label == 1].groupby("company"):
            hit = g[g[col] >= THRESHOLD]
            if len(hit):
                leads.append(float(pd.to_numeric(hit["years_before_event"]).max()))
        res["median_lead_years"] = float(np.median(leads)) if leads else float("nan")
        out[name] = res
    return out


def watchlist(t: pd.DataFrame) -> pd.DataFrame:
    latest = t.sort_values("fy").groupby("company").tail(1)
    cols = ["company", "group", "fy", "num_pts", "text_pts", "total_pts", "M", "Z", "benford_mad", "flags", "quote"]
    return latest[cols].sort_values("total_pts", ascending=False).reset_index(drop=True)


def summary_md(res: dict) -> str:
    def f(x, pct=False):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "n/a"
        return f"{x:.0%}" if pct else f"{x:.2f}"

    lines = [
        "# Back-test summary", "",
        f"Sample actually evaluated: {res['flagged_firms']} flagged firms, {res['control_firms']} "
        f"control firms, {res['firm_years']} firm-years (window E-3..E-1). Flag threshold: {res['threshold']} points.",
        "", "| Method | Detection rate | False-alarm rate | Lead time (years) |", "|---|---|---|---|",
    ]
    for name, label in (("numbers_only", "Numbers only"), ("numbers_plus_text", "Numbers + text (v1, fixed in advance)"),
                        ("numbers_plus_text_v2", "Numbers + text (v2, post-hoc meaning rules)")):
        r = res[name]
        lines.append(f"| {label} | {f(r['detection_rate'], True)} | "
                     f"{f(r['false_positive_rate'], True)} | {f(r['median_lead_years'])} |")
    lines += ["", "Small-sample warning: with so few firms these figures are illustrative, not statistically "
              "reliable. v1 weights were fixed before seeing results. v2 applies keyword rules written after "
              "looking at v1's false positives on this same sample, so treat it as illustrative, not as a test."]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not SCORES.exists() or SCORES.stat().st_size < 5:
        OUT_MD.write_text("# Back-test summary\n\nNo scored data yet.\n")
        return
    t = build_table(pd.read_csv(SCORES), load_text())
    res = evaluate(t)
    OUT_JSON.write_text(json.dumps(res, indent=1))
    OUT_MD.write_text(summary_md(res))
    watchlist(t).to_csv(WATCHLIST, index=False)
    print(summary_md(res))


if __name__ == "__main__":
    main()
