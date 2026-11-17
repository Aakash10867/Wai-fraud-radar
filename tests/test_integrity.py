import numpy as np
import pandas as pd

from src.integrity import band, risk, score_company, score_year, text_risk


def test_risk_interpolates_both_directions():
    assert risk(0.0, 0.0, 0.10) == 0 and risk(0.10, 0.0, 0.10) == 100
    assert round(risk(0.05, 0.0, 0.10)) == 50
    assert risk(10, 5.0, 1.0) == 0 and risk(0.5, 5.0, 1.0) == 100  # lower is worse (interest cover)
    assert np.isnan(risk(np.nan, 0, 1))


def test_score_reweights_missing_pillars_and_reports_coverage():
    row = pd.Series({"TATA": 0.0, "M": -2.5, "Z": 2.6})  # perfect on the three measures given
    r = score_year(row)
    assert r["score"] == 100 and abs(r["coverage"] - 0.40) < 1e-9 and r["band"] == "Clear"
    bad = score_year(pd.Series({"TATA": 0.1, "M": -1.0, "Z": 1.1}))
    assert bad["score"] == 0 and bad["band"] == "Open forensic review"


def test_text_flags_lower_the_score():
    row = pd.Series({"TATA": 0.0, "M": -2.5, "Z": 2.6})
    assert score_year(row, 3)["score"] < score_year(row, 0)["score"]
    assert text_risk(5) == 100 and np.isnan(text_risk(np.nan))


def test_bands_are_ordered():
    assert band(80)[0] == "Clear" and band(65)[0] == "Monitor"
    assert band(50)[0] == "Targeted review" and band(10)[0] == "Open forensic review"


def test_score_company_runs_on_a_small_history():
    rows = []
    for fy in (2022, 2023, 2024):
        rows.append(dict(fy=fy, revenue=100 + fy - 2022, cogs=60, receivables=10, current_assets=50, ppe=40,
                         total_assets=100, depreciation=5, sga=np.nan, current_liabilities=30, long_term_debt=10,
                         net_income=8, cfo=9, retained_earnings=20, ebit=12, equity=50, total_liabilities=50,
                         interest_expense=2))
    out = score_company(pd.DataFrame(rows))
    assert list(out["fy"]) == [2022, 2023, 2024]
    assert out["score"].iloc[-1] > 60 and out["ICR"].iloc[-1] == 6
