import pandas as pd

from src.notes import fallback, numbers_supported, rule_checks

FACTS = {"company": "X", "fiscal_year": 2024, "integrity_score": 39.9, "band": "Open forensic review",
         "coverage_pct": 85, "measures": {"M": -0.38, "LEV": 6.19}, "pillar_risk_0_to_100": {"Leverage": 90},
         "red_flags": []}


def test_numbers_must_come_from_the_facts():
    assert numbers_supported("Score 39.9 in 2024 with M-score of -0.38 and leverage 6.2", FACTS)
    assert not numbers_supported("Debt rose 45% to 9.1 times equity", FACTS)


def test_rule_checks_follow_weakest_pillars():
    row = pd.Series({"risk_leverage": 80.0, "risk_earnings_quality": 10.0, "LEV": 6.0, "ICR": 0.5, "CUR": 2.0})
    out = rule_checks(row, [])
    assert len(out) == 1 and "borrowings" in out[0] or "interest" in out[0]


def test_fallback_note_is_plain_and_has_no_new_numbers():
    note = fallback(FACTS, [])
    assert numbers_supported(note["headline"] + " " + note["summary"], FACTS)
