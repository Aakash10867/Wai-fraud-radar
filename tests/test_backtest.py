import json

import numpy as np
import pandas as pd
import pytest

from src.backtest import (auc, build_table, evaluate, load_text, numeric_points, summary_md,
                          text_points, watchlist)
from src.dashboard import render
from src.llm import log_call
from src.universe import load_universe


def test_numeric_points():
    assert numeric_points({"M": -1.0, "Z": 0.5, "TATA": 0.1}) == 4
    assert numeric_points({"M": -2.5, "Z": 3.0, "TATA": 0.0}) == 0
    assert numeric_points({"M": np.nan, "Z": np.nan, "TATA": np.nan}) == 0


def test_text_points_ignore_absent_and_unknown():
    sigs = [{"type": "going_concern_doubt", "present": True}, {"type": "auditor_emphasis_of_matter", "present": False},
            {"type": "made_up", "present": True}, {"type": "internal_control_weakness", "present": True}]
    assert text_points(sigs) == (3, ["going_concern_doubt", "internal_control_weakness"])


def test_auc_values():
    assert auc([3, 4], [1, 2]) == 1.0
    assert auc([1, 1], [1, 1]) == 0.5
    assert np.isnan(auc([], [1]))


def make_scores():
    rows = []
    # flagged firm: bad numbers 3,2,1 years before event 2020; control: clean numbers
    for fy, yb in ((2017, 3), (2018, 2), (2019, 1), (2020, 0)):
        rows.append(dict(company="Bad Co", group="flagged", fy=fy, M=-1.0, Z=0.5, TATA=0.1,
                         benford_mad=0.02, years_before_event=yb))
        rows.append(dict(company="Good Co", group="control", fy=fy, M=-3.0, Z=4.0, TATA=0.0,
                         benford_mad=0.005, years_before_event=yb))
    return pd.DataFrame(rows)


def test_window_excludes_event_year_and_text_adds_lead():
    text = pd.DataFrame([{"company": "Bad Co", "fy": 2018, "text_pts": 2, "flags": "going_concern_doubt", "quote": "q"}])
    t = build_table(make_scores(), text)
    assert t.loc[t.years_before_event == 0, "label"].isna().all()
    res = evaluate(t)
    assert res["flagged_firms"] == 1 and res["control_firms"] == 1 and res["firm_years"] == 6
    assert res["numbers_only"]["auc"] == 1.0
    assert res["numbers_only"]["detection_rate"] == 1.0 and res["numbers_only"]["false_positive_rate"] == 0.0
    assert res["numbers_only"]["median_lead_years"] == 3.0
    assert "Numbers + text" in summary_md(res)
    w = watchlist(t)
    assert w.iloc[0]["company"] == "Bad Co"


def test_evaluate_handles_no_labeled_data():
    t = build_table(make_scores().assign(years_before_event=pd.NA), pd.DataFrame(columns=["company", "fy", "text_pts", "flags", "quote"]))
    res = evaluate(t)
    assert res["firm_years"] == 0 and np.isnan(res["numbers_only"]["auc"])


def test_load_text_reads_signal_files(tmp_path):
    (tmp_path / "x_2019.json").write_text(json.dumps({"company": "X", "report_fy": 2019, "signals": [
        {"type": "going_concern_doubt", "present": True, "quote": "material uncertainty about going concern"}]}))
    out = load_text(tmp_path)
    assert out.iloc[0]["text_pts"] == 2 and "going concern" in out.iloc[0]["quote"]


def test_dashboard_escapes_html():
    w = pd.DataFrame([{"company": "<script>x</script>", "group": "flagged", "fy": 2019, "num_pts": 2, "text_pts": 1,
                       "total_pts": 3, "M": -1.0, "Z": 1.0, "benford_mad": 0.01, "flags": "a;b", "quote": "<b>q</b>"}])
    out = render(w, {"flagged_firms": 1, "control_firms": 1, "firm_years": 3})
    assert "<script>x" not in out and "&lt;script&gt;" in out


def test_controls_inherit_event_year(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("company,yahoo_ticker,group,event_year,match_to,evidence,status\n"
                 "A,A.NS,flagged,2019,,e,s\nB,B.NS,control,,A,e,s\nC,C.NS,flagged,,,e,s\n")
    u = load_universe(p).set_index("company")
    assert u.loc["B", "event_resolved"] == 2019 and np.isnan(u.loc["C", "event_resolved"])


def test_prompt_log_appends(tmp_path):
    p = tmp_path / "logs" / "p.jsonl"
    log_call("m", "purpose", "hello", "world", path=p)
    log_call("m", "purpose2", "a" * 5000, "b", path=p)
    lines = [json.loads(x) for x in p.read_text().splitlines()]
    assert len(lines) == 2 and lines[1]["prompt_chars"] == 5000 and len(lines[1]["prompt_head"]) == 1500
