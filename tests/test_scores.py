import numpy as np
import pandas as pd
import pytest

from src.collect import tidy
from src.scores import altman_z, benford, beneish


def flat_firm():
    row = dict(revenue=1000, cogs=600, receivables=100, current_assets=500, ppe=300,
               total_assets=1000, depreciation=50, sga=100, current_liabilities=300,
               long_term_debt=200, net_income=80, cfo=80, retained_earnings=100,
               ebit=120, equity=400, total_liabilities=600)
    return pd.DataFrame([row, row], index=pd.Index([2023, 2024], name="fy"))


def test_beneish_flat_firm_equals_baseline():
    m = beneish(flat_firm())
    assert m.loc[2024, "M"] == pytest.approx(-2.48, abs=1e-9)
    assert np.isnan(m.loc[2023, "M"])


def test_beneish_flags_accrual_spike():
    df = flat_firm()
    df.loc[2024, "net_income"] = 300  # profit with no matching cash flow
    assert beneish(df).loc[2024, "M"] > -1.78


def test_beneish_sga_missing_is_flagged_and_neutral():
    df = flat_firm()
    df["sga"] = np.nan
    m = beneish(df)
    assert bool(m.loc[2024, "sgai_imputed"])
    assert m.loc[2024, "M"] == pytest.approx(-2.48 + 0.172 * 0 , abs=1e-9)


def test_altman_arithmetic():
    df = pd.DataFrame([dict(total_assets=100, current_assets=50, current_liabilities=30,
                            retained_earnings=10, ebit=8, equity=40, total_liabilities=60)])
    assert altman_z(df).iloc[0] == pytest.approx(6.1256, abs=1e-4)


def test_benford_conforming_vs_uniform():
    rng = np.random.default_rng(0)
    conforming = 10 ** rng.uniform(0, 6, 5000)
    uniform = rng.integers(100, 1000, 5000)
    assert benford(conforming)["mad"] < 0.006
    assert benford(uniform)["mad"] > 0.015


def test_benford_too_few_values():
    assert np.isnan(benford([123, 456])["mad"])


def test_tidy_maps_yahoo_labels():
    dates = pd.to_datetime(["2023-03-31", "2024-03-31"])
    inc = pd.DataFrame([[900, 1000], [500, 600]], index=["Total Revenue", "Cost Of Revenue"], columns=dates)
    bal = pd.DataFrame([[2000, 2100]], index=["Total Assets"], columns=dates)
    out = tidy(inc, bal, pd.DataFrame())
    assert list(out["fy"]) == [2023, 2024]
    assert out.loc[out["fy"] == 2024, "revenue"].iloc[0] == 1000
    assert out.loc[out["fy"] == 2024, "total_assets"].iloc[0] == 2100
    assert "cfo" in out.columns and out["cfo"].isna().all()
