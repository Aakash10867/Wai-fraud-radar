import numpy as np
import pandas as pd
import pytest

from src.extract import (balance_ok, build_prompt, norm, parse_response, select_pages,
                         slug, to_rupees, verify_signals)
from src.run import score_company

TEXT = "The Auditors have drawn attention to the “going concern” uncertainty relating to loans."


def test_quote_must_appear_in_report():
    sigs = [
        {"type": "going_concern_doubt", "present": True,
         "quote": "drawn attention to the going concern uncertainty"},
        {"type": "auditor_qualified_opinion", "present": True,
         "quote": "we qualify our opinion on receivables entirely"},  # invented
        {"type": "not_a_real_type", "present": True, "quote": "whatever whatever whatever"},
        {"type": "internal_control_weakness", "present": False, "quote": ""},
    ]
    kept, dropped = verify_signals(sigs, TEXT)
    assert dropped == 2
    assert {s["type"] for s in kept} == {"going_concern_doubt", "internal_control_weakness"}


def test_short_quote_rejected():
    kept, dropped = verify_signals([{"type": "going_concern_doubt", "present": True, "quote": "going"}], TEXT)
    assert kept == [] and dropped == 1


def test_balance_identity():
    assert balance_ok({"total_assets": 100, "equity": 40, "total_liabilities": 60})
    assert balance_ok({"total_assets": 100, "equity": 40, "total_liabilities": 61})
    assert not balance_ok({"total_assets": 100, "equity": 40, "total_liabilities": 80})
    assert not balance_ok({"total_assets": 100, "equity": None, "total_liabilities": 60})


def test_units_to_rupees():
    out = to_rupees({"revenue": 5, "cogs": None, "junk": 1}, "crore")
    assert out["revenue"] == 5e7 and out["cogs"] is None and "junk" not in out


def test_parse_response_strips_fences():
    assert parse_response('```json\n{"a": 1}\n```') == {"a": 1}


def test_select_pages_puts_statements_first_and_drops_irrelevant():
    pages = ["cover", "chairman message", "Independent Auditor's Report going concern",
             "Balance Sheet total assets total equity and liabilities non-current liabilities current liabilities", "Notes related party"]
    out = select_pages(pages, cap=3)
    assert "[page 1]" not in out and "[page 2]" not in out
    assert out.index("[page 4]") < out.index("[page 3]")  # statement page leads


def test_prompt_lists_every_field():
    p = build_prompt("x")
    assert "total_liabilities" in p and "going_concern_doubt" in p and "profit after tax" in p


def test_slug_and_norm():
    assert slug("Reliance Infrastructure Ltd.") == "reliance-infrastructure-ltd"
    assert norm("A  “B”\n c") == "a b c"


def test_gap_year_not_scored_against_non_adjacent_year():
    row = dict(revenue=1000, cogs=600, receivables=100, current_assets=500, ppe=300,
               total_assets=1000, depreciation=50, sga=100, current_liabilities=300,
               long_term_debt=200, net_income=80, cfo=80, retained_earnings=100,
               ebit=120, equity=400, total_liabilities=600)
    df = pd.DataFrame([{**row, "fy": 2020}, {**row, "fy": 2022}])  # 2021 missing
    out = score_company(df)
    assert list(out.index) == [2020, 2021, 2022]
    assert out["M"].isna().all()


def test_statement_pages_prefer_real_statements_over_repeating_notes():
    from src.extract import statement_pages

    notes = "total assets total assets total assets total assets"  # repeats one phrase
    balance = "Balance Sheet Non-current assets Total assets Equity and liabilities Current liabilities Total equity and liabilities"
    pages = ["cover", notes, balance, "cash flow statement operating activities investing activities financing activities net cash"]
    chosen = statement_pages(pages)
    assert 2 in chosen and 3 in chosen and 1 not in chosen
