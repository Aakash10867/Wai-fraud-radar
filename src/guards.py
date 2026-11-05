"""Meaning checks for text signals ("v2", added AFTER seeing the v1 back-test).

The quote check proves a quote exists in the report; it cannot prove the quote means what the
model says. v1 results showed routine events (scheduled auditor rotation, the Ind AS changeover,
"arm's length" statements) being flagged. These plain keyword rules drop such cases. They were
written after looking at the sample, so v2 results are reported separately and labelled post-hoc.
"""
from __future__ import annotations

RULES = {
    # a real warning is a resignation or vacancy, not a scheduled rotation at the AGM
    "auditor_resigned_or_changed": (("resign", "casual vacancy", "removed", "disqualif"), ()),
    # a real warning is a restatement or delay, not the one-off Ind AS transition
    "delayed_or_restated_results": (("restate", "prior period error", "delay", "late filing", "not been filed"),
                                    ("transition", "ind as", "indian accounting standard")),
    # a real warning is a transaction that was not at arm's length or lacked approval
    "material_related_party_transactions": (("not at arm", "not been approved", "without approval",
                                             "not in the ordinary course", "contravention", "non-compliance"), ()),
}


def keep_signal(signal: dict) -> bool:
    """True if a present signal also passes the v2 meaning rule for its type."""
    rule = RULES.get(signal.get("type"))
    if rule is None:
        return True
    must_have, must_not = rule
    q = (signal.get("quote") or "").lower()
    return any(m in q for m in must_have) and not any(n in q for n in must_not)
